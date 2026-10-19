import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.integrations.mercado_pago import (
    MercadoPagoGateway,
    MercadoPagoIntegrationError,
    MercadoPagoResponse,
)
from app.models.anuncio import Anuncio
from app.models.categoria import Categoria
from app.models.conta_pagamento import ContaPagamento
from app.models.endereco import Endereco
from app.models.enums import (
    AnuncioStatus,
    CategoriaStatus,
    ContaPagamentoStatus,
    EventoProcessamentoStatus,
    ModalidadeEntrega,
    PagamentoStatus,
    PedidoStatus,
    ReembolsoStatus,
)
from app.models.evento_provedor import EventoProvedor
from app.models.pagamento import Pagamento
from app.models.pedido import Pedido
from app.models.reembolso import Reembolso
from app.models.repasse import Repasse
from app.models.usuario import Usuario
from app.services.conta_pagamento import ContaPagamentoService
from app.services.pedido import PedidoService
from app.services.reembolso import ReembolsoService
from app.services.webhook_mercado_pago import WebhookMercadoPagoService


@dataclass
class Compra:
    pedido_id: UUID
    pagamento_id: UUID
    anuncio_id: UUID
    comprador_id: UUID
    conta_externa_id: str


@pytest.fixture
async def compra(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> Compra:
    monkeypatch.setattr(
        ContaPagamentoService, "obter_access_token", AsyncMock(return_value=(None, "token-fake"))
    )
    async with db_session.begin():
        vendedor = Usuario(nome="Vendedor", email=f"{uuid4()}@test.invalid", senha_hash="hash")
        comprador = Usuario(nome="Comprador", email=f"{uuid4()}@test.invalid", senha_hash="hash")
        categoria = Categoria(nome=str(uuid4()), status=CategoriaStatus.ATIVA)
        db_session.add_all([vendedor, comprador, categoria])
        await db_session.flush()
        endereco = Endereco(
            usuario_id=vendedor.id,
            cep="01001000",
            logradouro="Rua",
            numero="1",
            bairro="Centro",
            cidade="São Paulo",
            estado="SP",
        )
        db_session.add(endereco)
        await db_session.flush()
        anuncio = Anuncio(
            vendedor_id=vendedor.id,
            categoria_id=categoria.id,
            endereco_id=endereco.id,
            titulo="Material",
            descricao="Material para teste",
            preco=Decimal("25.00"),
            quantidade=0,
            status=AnuncioStatus.ESGOTADO,
        )
        conta = ContaPagamento(
            usuario_id=vendedor.id,
            conta_externa_id=str(uuid4()),
            status=ContaPagamentoStatus.ATIVA,
            access_token_criptografado="fake",
            refresh_token_criptografado="fake",
        )
        db_session.add_all([anuncio, conta])
        await db_session.flush()
        pedido = Pedido(
            comprador_id=comprador.id,
            anuncio_id=anuncio.id,
            modalidade_entrega=ModalidadeEntrega.RETIRADA,
            quantidade=2,
            preco_unitario=Decimal("25.00"),
            valor_total=Decimal("50.00"),
            status=PedidoStatus.AGUARDANDO_PAGAMENTO,
            estoque_reservado_em=datetime.now(UTC),
            reserva_expira_em=datetime.now(UTC) + timedelta(minutes=30),
        )
        db_session.add(pedido)
        await db_session.flush()
        pagamento = Pagamento(
            pedido_id=pedido.id,
            idempotency_key=str(uuid4()),
            valor=Decimal("50.00"),
            status=PagamentoStatus.PENDENTE,
            preferencia_externa_id=str(uuid4()),
        )
        db_session.add(pagamento)
        await db_session.flush()
        return Compra(pedido.id, pagamento.id, anuncio.id, comprador.id, conta.conta_externa_id)


class GatewayConciliacao(MercadoPagoGateway):
    def __init__(self, compra: Compra) -> None:
        super().__init__("https://unused.invalid")
        self.dados = {
            "id": f"mp-{uuid4()}",
            "external_reference": str(compra.pedido_id),
            "metadata": {"pagamento_id": str(compra.pagamento_id)},
            "transaction_amount": "50.00",
            "status": "approved",
            "live_mode": False,
            "payment_method_id": "pix",
            "payment_type_id": "bank_transfer",
        }
        self.falhar = False
        self.interromper = False
        self.status_reembolso = "approved"
        self.chaves: list[str] = []

    async def obter_pagamento(
        self, *, access_token: str, pagamento_externo_id: str
    ) -> MercadoPagoResponse:
        return MercadoPagoResponse(data=dict(self.dados))

    async def reembolsar_pagamento(
        self, *, access_token: str, pagamento_externo_id: str, idempotency_key: str
    ) -> MercadoPagoResponse:
        self.chaves.append(idempotency_key)
        if self.interromper:
            raise asyncio.CancelledError()
        if self.falhar:
            raise MercadoPagoIntegrationError("timeout")
        return MercadoPagoResponse(
            data={"id": "refund-" + pagamento_externo_id, "status": self.status_reembolso}
        )


async def _evento(
    servico: WebhookMercadoPagoService, compra: Compra, gateway: GatewayConciliacao
) -> UUID:
    evento = await servico._registrar_evento(
        str(uuid4()),
        str(gateway.dados["id"]),
        {
            "type": "payment",
            "user_id": compra.conta_externa_id,
            "data": {"id": gateway.dados["id"]},
        },
    )
    return evento.id


async def test_aprovacao_apos_cancelamento_reembolsa_sem_consumir_estoque(
    db_session: AsyncSession,
    compra: Compra,
) -> None:
    await PedidoService(db_session).cancelar(compra.pedido_id, compra.comprador_id)
    gateway = GatewayConciliacao(compra)
    servico = WebhookMercadoPagoService(db_session, gateway=gateway)
    evento_id = await _evento(servico, compra, gateway)
    assert await servico.reprocessar_evento(evento_id)
    # Repetir a notificação não faz outra devolução, nem cria outro repasse.
    assert not await servico.reprocessar_evento(evento_id)
    segundo_id = await _evento(servico, compra, gateway)
    assert await servico.reprocessar_evento(segundo_id)
    async with db_session.begin():
        pedido = await db_session.get(Pedido, compra.pedido_id)
        pagamento = await db_session.get(Pagamento, compra.pagamento_id)
        anuncio = await db_session.get(Anuncio, compra.anuncio_id)
        reembolso = await db_session.scalar(
            select(Reembolso).where(Reembolso.pedido_id == compra.pedido_id)
        )
        assert pedido is not None and pedido.status == PedidoStatus.REEMBOLSADO
        assert pagamento is not None and pagamento.status == PagamentoStatus.REEMBOLSADO
        assert anuncio is not None and anuncio.quantidade == 2
        assert reembolso is not None and reembolso.status == ReembolsoStatus.CONCLUIDO
        assert (
            await db_session.scalar(
                select(func.count())
                .select_from(Repasse)
                .where(Repasse.pedido_id == compra.pedido_id)
            )
            == 1
        )
        assert len(gateway.chaves) == 1


async def test_falha_na_devolucao_preserva_cobranca_e_reutiliza_chave(
    db_session: AsyncSession,
    compra: Compra,
) -> None:
    await PedidoService(db_session).cancelar(compra.pedido_id, compra.comprador_id)
    gateway = GatewayConciliacao(compra)
    gateway.falhar = True
    servico = WebhookMercadoPagoService(db_session, gateway=gateway)
    evento_id = await _evento(servico, compra, gateway)
    assert await servico.reprocessar_evento(evento_id)
    async with db_session.begin():
        evento = await db_session.get(EventoProvedor, evento_id)
        pagamento = await db_session.get(Pagamento, compra.pagamento_id)
        assert (
            evento is not None and evento.status_processamento == EventoProcessamentoStatus.FALHOU
        )
        assert evento.proxima_tentativa_em is not None
        assert pagamento is not None and pagamento.status == PagamentoStatus.APROVADO
        evento.proxima_tentativa_em = datetime.now(UTC) - timedelta(seconds=1)
    gateway.falhar = False
    assert await servico.reprocessar_evento(evento_id)
    assert len(gateway.chaves) == 2 and gateway.chaves[0] == gateway.chaves[1]
    resposta = await PedidoService(db_session).buscar(compra.pedido_id, compra.comprador_id)
    assert resposta.status == PedidoStatus.REEMBOLSADO
    assert resposta.reembolso is not None and resposta.reembolso.status == ReembolsoStatus.CONCLUIDO


async def test_reembolso_assincrono_e_concluido_por_consulta_do_provedor(
    db_session: AsyncSession,
    compra: Compra,
) -> None:
    await PedidoService(db_session).cancelar(compra.pedido_id, compra.comprador_id)
    gateway = GatewayConciliacao(compra)
    gateway.status_reembolso = "pending"
    servico = WebhookMercadoPagoService(db_session, gateway=gateway)
    evento_id = await _evento(servico, compra, gateway)
    await servico.reprocessar_evento(evento_id)
    async with db_session.begin():
        evento = await db_session.get(EventoProvedor, evento_id)
        assert evento is not None and evento.proxima_tentativa_em is not None
        evento.proxima_tentativa_em = datetime.now(UTC) - timedelta(seconds=1)
    gateway.dados["status"] = "refunded"
    await servico.reprocessar_evento(evento_id)
    resposta = await PedidoService(db_session).buscar(compra.pedido_id, compra.comprador_id)
    assert resposta.reembolso is not None and resposta.reembolso.status == ReembolsoStatus.CONCLUIDO
    assert resposta.status == PedidoStatus.REEMBOLSADO
    assert len(gateway.chaves) == 1


async def test_resposta_atrasada_nao_regride_pagamento_aprovado(
    db_session: AsyncSession,
    compra: Compra,
) -> None:
    gateway = GatewayConciliacao(compra)
    servico = WebhookMercadoPagoService(db_session, gateway=gateway)
    await servico.reprocessar_evento(await _evento(servico, compra, gateway))
    gateway.dados["status"] = "pending"
    await servico.reprocessar_evento(await _evento(servico, compra, gateway))
    resposta = await PedidoService(db_session).buscar(compra.pedido_id, compra.comprador_id)
    assert resposta.status == PedidoStatus.PAGAMENTO_APROVADO
    assert resposta.pagamento is not None and resposta.pagamento.status == PagamentoStatus.APROVADO


async def test_pedido_de_outro_comprador_nao_expoe_reembolso(
    db_session: AsyncSession,
    compra: Compra,
) -> None:
    with pytest.raises(AppError) as erro:
        await PedidoService(db_session).buscar(compra.pedido_id, uuid4())
    assert erro.value.status_code == 404


async def test_queda_apos_conciliacao_retoma_devolucao_sem_duplicar_repasse(
    db_session: AsyncSession,
    compra: Compra,
) -> None:
    await PedidoService(db_session).cancelar(compra.pedido_id, compra.comprador_id)
    gateway = GatewayConciliacao(compra)
    gateway.interromper = True
    servico = WebhookMercadoPagoService(db_session, gateway=gateway)
    evento_id = await _evento(servico, compra, gateway)
    with pytest.raises(asyncio.CancelledError):
        await servico.reprocessar_evento(evento_id)
    async with db_session.begin():
        evento = await db_session.get(EventoProvedor, evento_id)
        assert (
            evento is not None and evento.status_processamento == EventoProcessamentoStatus.PENDENTE
        )
        evento.bloqueado_ate = datetime.now(UTC) - timedelta(seconds=1)
        pagamento = await db_session.get(Pagamento, compra.pagamento_id)
        assert pagamento is not None and pagamento.status == PagamentoStatus.APROVADO
    gateway.interromper = False
    assert await servico.reprocessar_evento(evento_id)
    assert len(gateway.chaves) == 2 and gateway.chaves[0] == gateway.chaves[1]
    async with db_session.begin():
        assert (
            await db_session.scalar(
                select(func.count())
                .select_from(Repasse)
                .where(Repasse.pedido_id == compra.pedido_id)
            )
            == 1
        )
        anuncio = await db_session.get(Anuncio, compra.anuncio_id)
        assert anuncio is not None and anuncio.quantidade == 2


async def test_erro_atrasado_nao_reabre_reembolso_confirmado(
    db_session: AsyncSession,
    compra: Compra,
) -> None:
    await PedidoService(db_session).cancelar(compra.pedido_id, compra.comprador_id)
    gateway = GatewayConciliacao(compra)
    servico = WebhookMercadoPagoService(db_session, gateway=gateway)
    await servico.reprocessar_evento(await _evento(servico, compra, gateway))
    async with db_session.begin():
        reembolso = await db_session.scalar(
            select(Reembolso).where(Reembolso.pedido_id == compra.pedido_id)
        )
        assert reembolso is not None
        reembolso_id = reembolso.id
    await ReembolsoService(db_session)._marcar_falha(reembolso_id)
    async with db_session.begin():
        await db_session.refresh(reembolso)
        assert reembolso.status == ReembolsoStatus.CONCLUIDO

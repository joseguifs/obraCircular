from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.mercado_pago import (
    MercadoPagoGateway,
    MercadoPagoIntegrationError,
    MercadoPagoResponse,
)
from app.integrations.payouts import PayoutsGateway
from app.models.administrador import Administrador
from app.models.contestacao import Contestacao
from app.models.entrega import Entrega
from app.models.enums import (
    ContestacaoMotivo,
    ContestacaoStatus,
    PagamentoStatus,
    PedidoStatus,
    RepasseStatus,
)
from app.models.operacao_repasse import EventoRepasse, InstrucaoRepasse
from app.models.pagamento import Pagamento
from app.models.pedido import Pedido
from app.models.reembolso import Reembolso
from app.models.repasse import Repasse
from app.models.usuario import Usuario
from app.schemas.repasse import DestinoRepasseCreate
from app.services.repasse import RepasseService
from app.services.webhook_mercado_pago import WebhookMercadoPagoService
from tests.test_contestacao import CompraEntregue
from tests.test_contestacao import compra_entregue as compra_entregue

pytestmark = pytest.mark.parametrize("compra_entregue", [True], indirect=True)


def configuracao() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        mp_access_token=SecretStr("token-marketplace"),
        mp_marketplace_user_id="marketplace-test",
        marketplace_fee_percent=Decimal("20.00"),
        mp_payouts_enabled=True,
        mp_payouts_test_mode=True,
        mp_live_mode=False,
        mp_payouts_notification_url="https://example.test/webhooks/payouts",
        mp_token_encryption_key=SecretStr("segredo-para-testar-criptografia-12345678"),
    )


class GatewayPagamentos(MercadoPagoGateway):
    def __init__(self) -> None:
        super().__init__("https://unused.invalid")
        self.status = "approved"
        self.coletor = "marketplace-test"
        self.valor = "100.00"
        self.liberado = True

    async def obter_pagamento(
        self, *, access_token: str, pagamento_externo_id: str
    ) -> MercadoPagoResponse:
        assert access_token == "token-marketplace"
        return MercadoPagoResponse(
            data={
                "status": self.status,
                "collector_id": self.coletor,
                "transaction_amount": self.valor,
                "money_release_status": "released" if self.liberado else "pending",
            }
        )


class GatewayRepasses(PayoutsGateway):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.criacoes: list[tuple[dict[str, Any], str]] = []
        self.status = "success"
        self.detalhe = "accredited"
        self.falhar = False
        self.divergir = False

    async def criar(self, corpo: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        self.criacoes.append((corpo, idempotency_key))
        if self.falhar:
            raise MercadoPagoIntegrationError("timeout")
        return {"id": "payout-1", "status": "approved"}

    async def consultar(self, payout_id: str) -> dict[str, Any]:
        assert payout_id == "payout-1"
        transacao = dict(self.criacoes[-1][0]["transactions"][0])
        if self.divergir:
            transacao["amount"] = {"currency": "BRL", "value": 1}
        return {
            "transactions": [
                {
                    **transacao,
                    "id": "transferencia-1",
                    "status": self.status,
                    "status_detail": self.detalhe,
                }
            ]
        }


@pytest.fixture
async def operacao(
    db_session: AsyncSession, compra_entregue: CompraEntregue
) -> tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID]:
    async with db_session.begin():
        admin = Usuario(nome="Financeiro", email=f"{uuid4()}@test.invalid", senha_hash="hash")
        db_session.add(admin)
        await db_session.flush()
        db_session.add(Administrador(usuario_id=admin.id))
        entrega = await db_session.get(Entrega, compra_entregue.entrega_id)
        pagamento = await db_session.get(Pagamento, compra_entregue.pagamento_id)
        assert entrega is not None and pagamento is not None
        entrega.confirmado_em = datetime.now(UTC) - timedelta(days=8)
        entrega.prazo_contestacao_em = datetime.now(UTC) - timedelta(days=1)
        pagamento.pagamento_externo_id = str(uuid4())
        admin_id = admin.id
    settings = configuracao()
    gateway = GatewayRepasses(settings)
    pagamentos = GatewayPagamentos()
    service = RepasseService(
        db_session, settings=settings, gateway=gateway, pagamentos_gateway=pagamentos
    )
    await service.cadastrar_destino(
        compra_entregue.vendedor_id,
        DestinoRepasseCreate(
            tipo_chave="EMAIL",
            chave="vendedor@test.invalid",
            titularidade_conferida=True,
        ),
        admin_id,
    )
    return service, gateway, pagamentos, admin_id


async def test_payout_por_email_usa_conta_sem_pix_e_preserva_destino_na_retomada(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
) -> None:
    service, gateway, _, admin = operacao
    service.settings.mp_payouts_test_account_max_amount = Decimal("100.00")
    await service.cadastrar_destino(
        compra_entregue.vendedor_id,
        DestinoRepasseCreate(
            tipo_chave="CONTA_MP_TESTE",
            chave="test_user_destino@testuser.com",
            titularidade_conferida=True,
        ),
        admin,
    )
    gateway.falhar = True
    with pytest.raises(AppError):
        await service.liberar(compra_entregue.repasse_id, admin)
    transacao = gateway.criacoes[0][0]["transactions"][0]
    assert transacao["type"] == "account"
    assert transacao["account"] == {"email": "test_user_destino@testuser.com"}
    assert "pix" not in transacao
    async with db_session.begin():
        instrucao = await db_session.scalar(
            select(InstrucaoRepasse).where(
                InstrucaoRepasse.repasse_id == compra_entregue.repasse_id
            )
        )
        assert instrucao is not None
        instrucao.lease_ate = datetime.now(UTC) - timedelta(seconds=1)
    await service.cadastrar_destino(
        compra_entregue.vendedor_id,
        DestinoRepasseCreate(
            tipo_chave="CONTA_MP_TESTE",
            chave="outro_destino@testuser.com",
            titularidade_conferida=True,
        ),
        admin,
    )
    gateway.falhar = False
    resultado = await service.liberar(compra_entregue.repasse_id, admin)
    assert resultado.status == RepasseStatus.PAGO
    assert resultado.destino_tipo == "CONTA_MP_TESTE"
    assert gateway.criacoes[0] == gateway.criacoes[1]


@pytest.mark.parametrize(
    "environment,test_mode,live_mode",
    [("production", False, True), ("staging", True, False), ("local", False, True)],
)
async def test_conta_por_email_recusada_fora_de_teste(
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
    environment: str,
    test_mode: bool,
    live_mode: bool,
) -> None:
    service, gateway, _, admin = operacao
    service.settings = service.settings.model_copy(
        update={
            "environment": environment,
            "mp_payouts_test_mode": test_mode,
            "mp_live_mode": live_mode,
        }
    )
    with pytest.raises(AppError) as erro:
        await service.cadastrar_destino(
            compra_entregue.vendedor_id,
            DestinoRepasseCreate(
                tipo_chave="CONTA_MP_TESTE",
                chave="destino@testuser.com",
                titularidade_conferida=True,
            ),
            admin,
        )
    assert erro.value.code == "PAYOUT_TEST_ACCOUNT_ONLY"
    assert gateway.criacoes == []


async def test_instrucao_por_email_nao_escapa_da_restricao_apos_trocar_destino(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
) -> None:
    service, gateway, _, admin = operacao
    service.settings.mp_payouts_test_account_max_amount = Decimal("100.00")
    await service.cadastrar_destino(
        compra_entregue.vendedor_id,
        DestinoRepasseCreate(
            tipo_chave="CONTA_MP_TESTE",
            chave="destino@testuser.com",
            titularidade_conferida=True,
        ),
        admin,
    )
    gateway.falhar = True
    with pytest.raises(AppError):
        await service.liberar(compra_entregue.repasse_id, admin)
    async with db_session.begin():
        instrucao = await db_session.scalar(
            select(InstrucaoRepasse).where(
                InstrucaoRepasse.repasse_id == compra_entregue.repasse_id
            )
        )
        assert instrucao is not None
        instrucao.lease_ate = datetime.now(UTC) - timedelta(seconds=1)
    await service.cadastrar_destino(
        compra_entregue.vendedor_id,
        DestinoRepasseCreate(
            tipo_chave="EMAIL", chave="destino@example.com", titularidade_conferida=True
        ),
        admin,
    )
    service.settings = service.settings.model_copy(update={"environment": "staging"})
    gateway.falhar = False
    with pytest.raises(AppError) as erro:
        await service.liberar(compra_entregue.repasse_id, admin)
    assert erro.value.code == "PAYOUT_TEST_ACCOUNT_ONLY"
    assert len(gateway.criacoes) == 1


async def test_teto_do_repasse_por_email_impede_envio(
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
) -> None:
    service, gateway, _, admin = operacao
    await service.cadastrar_destino(
        compra_entregue.vendedor_id,
        DestinoRepasseCreate(
            tipo_chave="CONTA_MP_TESTE",
            chave="destino@testuser.com",
            titularidade_conferida=True,
        ),
        admin,
    )
    with pytest.raises(AppError, match="limite configurado"):
        await service.liberar(compra_entregue.repasse_id, admin)
    assert gateway.criacoes == []


async def test_repasse_preserva_80_porcento_e_so_paga_depois_da_confirmacao(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
) -> None:
    service, gateway, _, admin = operacao
    service.settings.marketplace_fee_percent = Decimal("50.00")
    gateway.status, gateway.detalhe = "approved", ""
    resultado = await service.liberar(compra_entregue.repasse_id, admin)
    assert resultado.status == RepasseStatus.PROCESSANDO
    assert resultado.pago_em is None
    assert resultado.valor_liquido == Decimal("80.00")
    assert resultado.percentual_marketplace == Decimal("20.00")
    assert gateway.criacoes[0][0]["transactions"][0]["amount"]["value"] == 80.0
    gateway.status, gateway.detalhe = "success", "accredited"
    resultado = await service.conciliar(compra_entregue.repasse_id, admin)
    assert resultado.status == RepasseStatus.PAGO
    assert resultado.pago_em is not None
    resultado = await service.conciliar(compra_entregue.repasse_id, admin)
    assert resultado.status == RepasseStatus.PAGO
    assert len(gateway.criacoes) == 1
    async with db_session.begin():
        pedido = await db_session.get(Pedido, compra_entregue.pedido_id)
        assert pedido is not None and pedido.status == PedidoStatus.CONCLUIDO
        assert (
            await db_session.scalar(
                select(func.count())
                .select_from(InstrucaoRepasse)
                .where(InstrucaoRepasse.repasse_id == compra_entregue.repasse_id)
            )
            == 1
        )
        eventos = list(
            await db_session.scalars(
                select(EventoRepasse).where(EventoRepasse.repasse_id == compra_entregue.repasse_id)
            )
        )
        assert len(eventos) >= 2
        assert all(e.operador_id == admin for e in eventos)


@pytest.mark.parametrize(
    "status,detalhe",
    [
        ("approved", ""),
        ("created", ""),
        ("success", "in_progress"),
        ("transaction_in_process", "pending_bank"),
    ],
)
async def test_status_intermediarios_nao_confirmam_repasse(
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
    status: str,
    detalhe: str,
) -> None:
    service, gateway, _, admin = operacao
    gateway.status, gateway.detalhe = status, detalhe
    resultado = await service.liberar(compra_entregue.repasse_id, admin)
    assert resultado.status == RepasseStatus.PROCESSANDO
    assert resultado.pago_em is None


async def test_timeout_reutiliza_corpo_destino_valor_e_chave(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
) -> None:
    service, gateway, _, admin = operacao
    gateway.falhar = True
    with pytest.raises(AppError, match="Repasse sem confirmação"):
        await service.liberar(compra_entregue.repasse_id, admin)
    with pytest.raises(AppError) as erro:
        await service.liberar(compra_entregue.repasse_id, admin)
    assert erro.value.code == "PAYOUT_IN_PROGRESS"
    async with db_session.begin():
        instrucao = await db_session.scalar(
            select(InstrucaoRepasse).where(
                InstrucaoRepasse.repasse_id == compra_entregue.repasse_id
            )
        )
        assert instrucao is not None
        instrucao.lease_ate = datetime.now(UTC) - timedelta(seconds=1)
    await service.cadastrar_destino(
        compra_entregue.vendedor_id,
        DestinoRepasseCreate(
            tipo_chave="EMAIL",
            chave="destino-novo@test.invalid",
            titularidade_conferida=True,
        ),
        admin,
    )
    gateway.falhar = False
    await service.liberar(compra_entregue.repasse_id, admin)
    assert len(gateway.criacoes) == 2
    assert gateway.criacoes[0] == gateway.criacoes[1]


async def test_erro_de_acesso_mostra_causa_e_retomada_preserva_instrucao(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service, gateway, _, admin = operacao
    criar_original = gateway.criar

    async def criar_sem_permissao(corpo: dict[str, Any], key: str) -> dict[str, Any]:
        gateway.criacoes.append((corpo, key))
        raise MercadoPagoIntegrationError(
            "Recusa",
            status_code=403,
            payload={"code": "PA_UNAUTHORIZED_RESULT_FROM_POLICIES", "message": "segredo-bancario"},
        )

    monkeypatch.setattr(gateway, "criar", criar_sem_permissao)
    with pytest.raises(AppError) as erro:
        await service.liberar(compra_entregue.repasse_id, admin)
    assert erro.value.code == "PAYOUT_PROVIDER_ERROR"
    assert "HTTP 403" in erro.value.detail
    assert "PA_UNAUTHORIZED_RESULT_FROM_POLICIES" in erro.value.detail
    assert "segredo-bancario" not in erro.value.detail + caplog.text
    async with db_session.begin():
        instrucao = await db_session.scalar(
            select(InstrucaoRepasse).where(
                InstrucaoRepasse.repasse_id == compra_entregue.repasse_id
            )
        )
        repasse = await db_session.get(Repasse, compra_entregue.repasse_id)
        pedido = await db_session.get(Pedido, compra_entregue.pedido_id)
        assert instrucao is not None and repasse is not None and pedido is not None
        instrucao_id, key = instrucao.id, instrucao.idempotency_key
        assert instrucao.recurso_externo_id is None
        assert repasse.status == RepasseStatus.PROCESSANDO and repasse.pago_em is None
        resposta = await service._resposta(repasse, pedido)
        assert not resposta.pode_consultar and not resposta.pode_liberar
        assert resposta.motivo_bloqueio is not None and "dois minutos" in resposta.motivo_bloqueio
        assert (
            await db_session.scalar(
                select(EventoRepasse.id).where(
                    EventoRepasse.repasse_id == repasse.id,
                    EventoRepasse.acao == "ERRO_ENVIO_HTTP_403",
                )
            )
            is not None
        )
        instrucao.lease_ate = datetime.now(UTC) - timedelta(seconds=1)
        resposta = await service._resposta(repasse, pedido)
        assert resposta.pode_liberar and not resposta.pode_consultar

    with pytest.raises(AppError) as consulta:
        await service.conciliar(compra_entregue.repasse_id, admin)
    assert consulta.value.code == "PAYOUT_REMOTE_ID_PENDING"
    assert "mesma instrução" in consulta.value.detail
    monkeypatch.setattr(gateway, "criar", criar_original)
    resultado = await service.liberar(compra_entregue.repasse_id, admin)
    assert resultado.status == RepasseStatus.PAGO and resultado.pode_consultar
    assert gateway.criacoes[0] == gateway.criacoes[1]
    async with db_session.begin():
        instrucao = await db_session.get(InstrucaoRepasse, instrucao_id, populate_existing=True)
        assert instrucao is not None and instrucao.idempotency_key == key


async def test_erro_recebimento_informa_etapa_sem_chamar_transferencia(
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
) -> None:
    service, gateway, pagamentos, admin = operacao
    pagamentos.liberado = False
    with pytest.raises(AppError) as erro:
        await service.liberar(compra_entregue.repasse_id, admin)
    assert erro.value.code == "PAYOUT_RECEIPT_CHECK_FAILED"
    assert "O provedor ainda não liberou o recebimento" in erro.value.detail
    assert gateway.criacoes == []


async def test_erro_na_consulta_nao_apaga_identificadores_nem_confirma_credito(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, gateway, _, admin = operacao
    gateway.status, gateway.detalhe = "created", ""
    await service.liberar(compra_entregue.repasse_id, admin)

    async def consultar_sem_permissao(recurso: str) -> dict[str, Any]:
        raise MercadoPagoIntegrationError("Recusa", status_code=403, payload={"code": "forbidden"})

    monkeypatch.setattr(gateway, "consultar", consultar_sem_permissao)
    with pytest.raises(AppError) as erro:
        await service.conciliar(compra_entregue.repasse_id, admin)
    assert erro.value.code == "PAYOUT_PROVIDER_ERROR" and "HTTP 403" in erro.value.detail
    async with db_session.begin():
        repasse = await db_session.get(Repasse, compra_entregue.repasse_id, populate_existing=True)
        instrucao = await db_session.scalar(
            select(InstrucaoRepasse).where(
                InstrucaoRepasse.repasse_id == compra_entregue.repasse_id
            )
        )
        assert repasse is not None and repasse.status == RepasseStatus.PROCESSANDO
        assert repasse.pago_em is None
        assert instrucao is not None and instrucao.recurso_externo_id == "payout-1"


@pytest.mark.parametrize(
    "bloqueio",
    [
        "prazo",
        "contestacao",
        "reembolso",
        "vendedor",
        "pagamento",
        "confirmacao",
        "prazo_menor_que_sete_dias",
    ],
)
async def test_bloqueios_impedem_saida_de_dinheiro(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
    bloqueio: str,
) -> None:
    service, gateway, _, admin = operacao
    async with db_session.begin():
        if bloqueio in {"prazo", "confirmacao", "prazo_menor_que_sete_dias"}:
            entrega = await db_session.get(Entrega, compra_entregue.entrega_id)
            assert entrega is not None
            if bloqueio == "confirmacao":
                entrega.confirmado_por = compra_entregue.comprador_id
            elif bloqueio == "prazo_menor_que_sete_dias":
                entrega.confirmado_em = datetime.now(UTC) - timedelta(days=1)
                entrega.prazo_contestacao_em = datetime.now(UTC) - timedelta(seconds=1)
            else:
                entrega.prazo_contestacao_em = datetime.now(UTC) + timedelta(seconds=10)
        elif bloqueio == "contestacao":
            db_session.add(
                Contestacao(
                    pedido_id=compra_entregue.pedido_id,
                    comprador_id=compra_entregue.comprador_id,
                    motivo=ContestacaoMotivo.OUTRO,
                    descricao="Reclamação ativa",
                    status=ContestacaoStatus.ACEITA,
                )
            )
        elif bloqueio == "reembolso":
            db_session.add(
                Reembolso(
                    pedido_id=compra_entregue.pedido_id,
                    pagamento_id=compra_entregue.pagamento_id,
                    valor=Decimal("100.00"),
                    idempotency_key=str(uuid4()),
                    motivo="Teste",
                    solicitado_por=admin,
                )
            )
        elif bloqueio == "vendedor":
            vendedor = await db_session.get(Usuario, compra_entregue.vendedor_id)
            assert vendedor is not None
            vendedor.status = "BLOQUEADO"
        else:
            pagamento = await db_session.get(Pagamento, compra_entregue.pagamento_id)
            assert pagamento is not None
            pagamento.status = PagamentoStatus.REEMBOLSADO
    with pytest.raises(AppError) as erro:
        await service.liberar(compra_entregue.repasse_id, admin)
    assert erro.value.code == "PAYOUT_NOT_ELIGIBLE"
    assert gateway.criacoes == []


async def test_dispensa_temporaria_libera_entrega_recente_e_preserva_prazo_original(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
) -> None:
    service, gateway, _, admin = operacao
    confirmado = datetime.now(UTC) - timedelta(minutes=1)
    prazo = confirmado + timedelta(days=7)
    async with db_session.begin():
        entrega = await db_session.get(Entrega, compra_entregue.entrega_id)
        assert entrega is not None
        entrega.confirmado_em = confirmado
        entrega.prazo_contestacao_em = prazo
    with pytest.raises(AppError) as erro:
        await service.liberar(compra_entregue.repasse_id, admin)
    assert erro.value.code == "PAYOUT_NOT_ELIGIBLE"
    service.settings.mp_payouts_test_skip_wait = True
    assert await service.atualizar_estados() == 1
    lista = await service.listar()
    item = next(r for r in lista.items if r.id == compra_entregue.repasse_id)
    assert item.status == RepasseStatus.PRONTO_PARA_LIBERACAO
    assert item.pode_liberar
    await db_session.rollback()
    service.settings.mp_payouts_test_skip_wait = False
    with pytest.raises(AppError) as erro:
        await service.liberar(compra_entregue.repasse_id, admin)
    assert erro.value.code == "PAYOUT_NOT_ELIGIBLE"
    service.settings.mp_payouts_test_skip_wait = True
    resultado = await service.liberar(compra_entregue.repasse_id, admin)
    assert resultado.status == RepasseStatus.PAGO
    assert resultado.valor_liquido == Decimal("80.00")
    assert len(gateway.criacoes) == 1
    async with db_session.begin():
        entrega = await db_session.get(Entrega, compra_entregue.entrega_id)
        assert entrega is not None
        assert entrega.confirmado_em == confirmado
        assert entrega.prazo_contestacao_em == prazo
        assert await db_session.scalar(
            select(EventoRepasse.id).where(
                EventoRepasse.repasse_id == compra_entregue.repasse_id,
                EventoRepasse.acao == "PRAZO_DISPENSADO_EM_TESTE",
            )
        )


@pytest.mark.parametrize(
    "environment,autorizado,esperado",
    [
        ("local", True, True),
        ("test", True, True),
        ("local", False, False),
        ("staging", True, False),
        ("production", True, False),
    ],
)
async def test_excecao_por_pedido_com_conta_real_preserva_datas_e_escopo(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
    environment: str,
    autorizado: bool,
    esperado: bool,
) -> None:
    service, gateway, _, admin = operacao
    service.settings = service.settings.model_copy(
        update={"environment": environment, "mp_live_mode": True, "mp_payouts_test_mode": False}
    )
    confirmado = datetime.now(UTC) - timedelta(minutes=1)
    prazo = confirmado + timedelta(days=7)
    async with db_session.begin():
        entrega = await db_session.get(Entrega, compra_entregue.entrega_id)
        repasse = await db_session.get(Repasse, compra_entregue.repasse_id)
        assert entrega is not None and repasse is not None
        entrega.confirmado_em = confirmado
        entrega.prazo_contestacao_em = prazo
        if autorizado:
            service._auditar(repasse, "AUTORIZACAO_PRAZO_PEDIDO_TESTE", admin)
    await service.atualizar_estados()
    pedido = await db_session.get(Pedido, compra_entregue.pedido_id)
    repasse = await db_session.get(Repasse, compra_entregue.repasse_id)
    assert pedido is not None and repasse is not None
    resposta = await service._resposta(repasse, pedido)
    assert resposta.pode_liberar is esperado
    assert (repasse.status == RepasseStatus.PRONTO_PARA_LIBERACAO) is esperado
    assert not await service._dispensar_prazo_pedido_teste(uuid4())
    entrega = await db_session.get(Entrega, compra_entregue.entrega_id)
    assert entrega is not None
    assert entrega.confirmado_em == confirmado
    assert entrega.prazo_contestacao_em == prazo
    assert gateway.criacoes == []
    await db_session.rollback()
    if esperado:
        async with db_session.begin():
            db_session.add(
                EventoRepasse(
                    repasse_id=compra_entregue.repasse_id,
                    operador_id=admin,
                    acao="REVOGACAO_PRAZO_PEDIDO_TESTE",
                    status=RepasseStatus.PRONTO_PARA_LIBERACAO,
                    criado_em=datetime.now(UTC) + timedelta(seconds=1),
                )
            )
        await service.atualizar_estados()
        pedido = await db_session.get(Pedido, compra_entregue.pedido_id)
        repasse = await db_session.get(Repasse, compra_entregue.repasse_id)
        assert pedido is not None and repasse is not None
        assert not (await service._resposta(repasse, pedido)).pode_liberar


@pytest.mark.parametrize("excecao_por_pedido", [False, True])
@pytest.mark.parametrize("bloqueio", ["entrega", "confirmacao", "contestacao", "reembolso"])
async def test_dispensa_de_prazo_mantem_demais_bloqueios(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
    bloqueio: str,
    excecao_por_pedido: bool,
) -> None:
    service, gateway, _, admin = operacao
    service.settings.mp_payouts_test_skip_wait = not excecao_por_pedido
    async with db_session.begin():
        if excecao_por_pedido:
            repasse = await db_session.get(Repasse, compra_entregue.repasse_id)
            assert repasse is not None
            service._auditar(repasse, "AUTORIZACAO_PRAZO_PEDIDO_TESTE", admin)
        entrega = await db_session.get(Entrega, compra_entregue.entrega_id)
        assert entrega is not None
        entrega.confirmado_em = datetime.now(UTC) - timedelta(minutes=1)
        entrega.prazo_contestacao_em = datetime.now(UTC) + timedelta(days=7)
        if bloqueio == "entrega":
            pedido = await db_session.get(Pedido, compra_entregue.pedido_id)
            assert pedido is not None
            pedido.status = PedidoStatus.PAGAMENTO_APROVADO
        elif bloqueio == "confirmacao":
            entrega.confirmado_por = compra_entregue.comprador_id
        elif bloqueio == "contestacao":
            db_session.add(
                Contestacao(
                    pedido_id=compra_entregue.pedido_id,
                    comprador_id=compra_entregue.comprador_id,
                    motivo=ContestacaoMotivo.OUTRO,
                    descricao="Contestacao durante teste sem espera",
                    status=ContestacaoStatus.ABERTA,
                )
            )
        else:
            db_session.add(
                Reembolso(
                    pedido_id=compra_entregue.pedido_id,
                    pagamento_id=compra_entregue.pagamento_id,
                    valor=Decimal("100.00"),
                    idempotency_key=str(uuid4()),
                    motivo="Teste",
                    solicitado_por=admin,
                )
            )
    with pytest.raises(AppError) as erro:
        await service.liberar(compra_entregue.repasse_id, admin)
    assert erro.value.code == "PAYOUT_NOT_ELIGIBLE"
    assert gateway.criacoes == []


@pytest.mark.parametrize(
    "status_repasse", [RepasseStatus.AGUARDANDO_ENTREGA, RepasseStatus.EM_PERIODO_CONTESTACAO]
)
async def test_abertura_pela_api_bloqueia_liberacao_mesmo_apos_o_prazo(
    client: AsyncClient,
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
    monkeypatch: pytest.MonkeyPatch,
    status_repasse: RepasseStatus,
) -> None:
    service, gateway, _, admin = operacao
    agora = datetime.now(UTC)
    monkeypatch.setattr("app.services.contestacao.datetime", datetime)
    async with db_session.begin():
        entrega = await db_session.get(Entrega, compra_entregue.entrega_id)
        repasse = await db_session.get(Repasse, compra_entregue.repasse_id)
        assert entrega is not None and repasse is not None
        entrega.confirmado_em = agora - timedelta(days=1)
        entrega.prazo_contestacao_em = agora + timedelta(days=6)
        repasse.status = status_repasse

    resposta = await client.post(
        compra_entregue.url,
        headers=compra_entregue.headers(),
        json={"motivo": "PRODUTO_DANIFICADO", "descricao": "Material chegou quebrado."},
    )
    assert resposta.status_code == 201, resposta.text

    class RelogioAposPrazo(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return agora + timedelta(days=8)

    monkeypatch.setattr("app.services.repasse.datetime", RelogioAposPrazo)
    assert await service.atualizar_estados() == 0
    with pytest.raises(AppError) as erro:
        await service.liberar(compra_entregue.repasse_id, admin)
    assert erro.value.code == "PAYOUT_NOT_ELIGIBLE"
    assert gateway.criacoes == []

    async with db_session.begin():
        pedido = await db_session.get(Pedido, compra_entregue.pedido_id, populate_existing=True)
        repasse = await db_session.get(Repasse, compra_entregue.repasse_id, populate_existing=True)
        assert pedido is not None and pedido.status == PedidoStatus.EM_CONTESTACAO
        assert repasse is not None and repasse.status == RepasseStatus.BLOQUEADO
        assert repasse.valor_liquido == Decimal("80.00")
        assert repasse.pago_em is None and repasse.repasse_externo_id is None
        assert (
            await db_session.scalar(
                select(func.count())
                .select_from(InstrucaoRepasse)
                .where(InstrucaoRepasse.repasse_id == compra_entregue.repasse_id)
            )
            == 0
        )


async def test_operador_comum_nao_pode_liberar(
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
) -> None:
    service, gateway, _, _ = operacao
    with pytest.raises(AppError) as erro:
        await service.liberar(compra_entregue.repasse_id, compra_entregue.comprador_id)
    assert erro.value.status_code == 403
    assert gateway.criacoes == []


@pytest.mark.parametrize("divergencia", ["valor", "coletor", "saldo", "status"])
async def test_consulta_recebimento_antes_de_enviar_transferencia(
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
    divergencia: str,
) -> None:
    service, gateway, pagamentos, admin = operacao
    if divergencia == "valor":
        pagamentos.valor = "99.00"
    elif divergencia == "coletor":
        pagamentos.coletor = "outra-conta"
    elif divergencia == "saldo":
        pagamentos.liberado = False
    else:
        pagamentos.status = "refunded"
    with pytest.raises(AppError):
        await service.liberar(compra_entregue.repasse_id, admin)
    assert gateway.criacoes == []


async def test_divergencia_na_transferencia_nao_marca_como_pago(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
) -> None:
    service, gateway, _, admin = operacao
    gateway.divergir = True
    with pytest.raises(AppError):
        await service.liberar(compra_entregue.repasse_id, admin)
    async with db_session.begin():
        repasse = await db_session.get(Repasse, compra_entregue.repasse_id, populate_existing=True)
        assert repasse is not None and repasse.status == RepasseStatus.PROCESSANDO
        assert repasse.pago_em is None


async def test_calculo_e_protegido_tambem_no_banco(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
) -> None:
    with pytest.raises(DBAPIError, match="imutavel"):
        async with db_session.begin():
            await db_session.execute(
                text("UPDATE pedidos SET percentual_marketplace=30 WHERE id=:id"),
                {"id": compra_entregue.pedido_id},
            )


async def test_aprovacao_centralizada_usa_comissao_congelada_e_nao_paga_vendedor(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
) -> None:
    async with db_session.begin():
        repasse = await db_session.get(Repasse, compra_entregue.repasse_id)
        assert repasse is not None
        await db_session.delete(repasse)
        pedido = await db_session.get(Pedido, compra_entregue.pedido_id)
        pagamento = await db_session.get(Pagamento, compra_entregue.pagamento_id)
        assert pedido is not None and pagamento is not None
        pedido.status = PedidoStatus.AGUARDANDO_PAGAMENTO
        pagamento.status = PagamentoStatus.PENDENTE
    settings = configuracao()
    settings.marketplace_fee_percent = Decimal("40.00")
    service = WebhookMercadoPagoService(db_session, settings=settings)
    evento = await service._registrar_evento(str(uuid4()), "mp-pagamento", {"type": "payment"})
    await service._aplicar_pagamento(
        evento.id,
        {
            "id": "mp-pagamento",
            "external_reference": str(compra_entregue.pedido_id),
            "collector_id": "marketplace-test",
            "transaction_amount": "100.00",
            "status": "approved",
            "fee_details": [{"type": "mercadopago_fee", "amount": 5}],
        },
        None,
    )
    async with db_session.begin():
        repasse = await db_session.scalar(
            select(Repasse).where(Repasse.pedido_id == compra_entregue.pedido_id)
        )
        assert repasse is not None
        assert repasse.status == RepasseStatus.AGUARDANDO_ENTREGA
        assert repasse.valor_liquido == Decimal("80.00")
        assert repasse.taxa_marketplace == Decimal("20.00")
        assert repasse.taxa_provedor == Decimal("5.00")
        assert repasse.pago_em is None and repasse.repasse_externo_id is None


async def test_split_legado_nunca_gera_segundo_pagamento(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
) -> None:
    service, gateway, _, admin = operacao
    async with db_session.begin():
        pedido = Pedido(
            comprador_id=compra_entregue.comprador_id,
            anuncio_id=compra_entregue.anuncio_id,
            modalidade_entrega="RETIRADA",
            quantidade=1,
            preco_unitario=Decimal("100"),
            valor_total=Decimal("100"),
            status=PedidoStatus.ENTREGUE,
        )
        db_session.add(pedido)
        await db_session.flush()
        pagamento = Pagamento(
            pedido_id=pedido.id,
            idempotency_key=str(uuid4()),
            valor=Decimal("100"),
            status=PagamentoStatus.APROVADO,
        )
        db_session.add(pagamento)
        await db_session.flush()
        repasse = Repasse(
            pedido_id=pedido.id,
            pagamento_id=pagamento.id,
            vendedor_id=compra_entregue.vendedor_id,
            valor_bruto=Decimal("100"),
            taxa_marketplace=Decimal("25"),
            taxa_provedor=Decimal("5"),
            valor_liquido=Decimal("70"),
            percentual_marketplace=Decimal("25"),
            status=RepasseStatus.EM_PERIODO_CONTESTACAO,
        )
        db_session.add(repasse)
        await db_session.flush()
        repasse_id = repasse.id
    with pytest.raises(AppError, match="split legado"):
        await service.liberar(repasse_id, admin)
    assert gateway.criacoes == []


async def test_job_atualiza_elegibilidade_sem_transferir_dinheiro(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
) -> None:
    service, gateway, _, _ = operacao
    assert await service.atualizar_estados() == 1
    assert await service.atualizar_estados() == 0
    async with db_session.begin():
        repasse = await db_session.get(Repasse, compra_entregue.repasse_id, populate_existing=True)
        assert repasse is not None and repasse.status == RepasseStatus.PRONTO_PARA_LIBERACAO
    assert gateway.criacoes == []


async def test_api_exige_admin_e_nao_aceita_valor_ou_destino_do_navegador(
    client: Any,
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings
    from app.core.security import criar_par_tokens

    service, gateway, _, admin = operacao
    monkeypatch.setattr("app.api.routes.repasses.RepasseService", lambda session: service)
    url = f"/api/v1/admin/payouts/{compra_entregue.repasse_id}/release"
    sem_auth = await client.post(url)
    assert sem_auth.status_code == 401
    token = criar_par_tokens(compra_entregue.comprador_id, get_settings()).access_token
    negada = await client.post(url, headers={"Authorization": "Bearer " + token})
    assert negada.status_code == 403
    token = criar_par_tokens(admin, get_settings()).access_token
    headers = {"Authorization": "Bearer " + token}
    lista = await client.get("/api/v1/admin/payouts", headers=headers)
    assert lista.status_code == 200
    assert lista.json()["items"]
    liberada = await client.post(
        url, headers=headers, json={"amount": 1, "pix_key": "fraude@teste.com"}
    )
    assert liberada.status_code == 200, liberada.text
    transferencia = gateway.criacoes[0][0]["transactions"][0]
    assert transferencia["amount"]["value"] == 80
    assert transferencia["pix"]["chave"] == "vendedor@test.invalid"
    historico = await client.get(url.replace("/release", "/events"), headers=headers)
    assert historico.status_code == 200
    assert historico.json()


async def test_auditoria_e_instrucao_nao_podem_ser_reescritas(
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    operacao: tuple[RepasseService, GatewayRepasses, GatewayPagamentos, UUID],
) -> None:
    service, _, _, admin = operacao
    await service.liberar(compra_entregue.repasse_id, admin)
    with pytest.raises(DBAPIError, match="imutavel"):
        async with db_session.begin():
            await db_session.execute(
                text("UPDATE instrucoes_repasse SET idempotency_key='outra' WHERE repasse_id=:id"),
                {"id": compra_entregue.repasse_id},
            )
    with pytest.raises(DBAPIError, match="auditoria"):
        async with db_session.begin():
            await db_session.execute(
                text("DELETE FROM eventos_repasse WHERE repasse_id=:id"),
                {"id": compra_entregue.repasse_id},
            )

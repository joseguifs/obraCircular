from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.mercado_pago import MercadoPagoGateway, MercadoPagoResponse
from app.models.anuncio import Anuncio
from app.models.categoria import Categoria
from app.models.destaque_anuncio import DestaqueAnuncio
from app.models.endereco import Endereco
from app.models.enums import (
    AnuncioStatus,
    CategoriaStatus,
    DestaqueAnuncioStatus,
    EventoProcessamentoStatus,
    MetodoPagamento,
    PagamentoStatus,
    ProvedorPagamento,
    UsuarioStatus,
)
from app.models.evento_provedor import EventoProvedor
from app.models.usuario import Usuario
from app.repositories.anuncio import AnuncioRepository
from app.schemas.anuncio import AnuncioFilters, AnuncioResponse
from app.services.destaque_anuncio import DestaqueAnuncioService
from app.services.webhook_mercado_pago import WebhookMercadoPagoService

MARKETPLACE = "marketplace-test"
TRABALHADOR = "worker-teste"


class FakeGateway:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []
        self.preferencias_consultadas = 0
        self.pagamentos: dict[str, dict[str, Any]] = {}

    async def criar_preferencia(
        self, *, access_token: str, payload: dict[str, Any]
    ) -> MercadoPagoResponse:
        assert access_token == "token-marketplace"
        self.payloads.append(payload)
        numero = len(self.payloads)
        return MercadoPagoResponse(
            data={"id": f"PREF-D{numero}", "init_point": f"https://mp.test/checkout/{numero}"}
        )

    async def obter_preferencia(
        self, *, access_token: str, preferencia_id: str
    ) -> MercadoPagoResponse:
        self.preferencias_consultadas += 1
        return MercadoPagoResponse(
            data={"id": preferencia_id, "init_point": "https://mp.test/checkout/retomado"}
        )

    async def obter_pagamento(
        self, *, access_token: str, pagamento_externo_id: str
    ) -> MercadoPagoResponse:
        assert access_token == "token-marketplace"
        return MercadoPagoResponse(data=self.pagamentos[pagamento_externo_id])


def _settings() -> Settings:
    return Settings(
        environment="test",
        mp_webhook_url="https://example.test/webhook",
        mp_public_base_url="https://example.test",
        mp_access_token=SecretStr("token-marketplace"),
        mp_marketplace_user_id=MARKETPLACE,
        mp_live_mode=False,
        featured_ad_price=Decimal("10.00"),
        featured_ad_duration_days=7,
    )


async def _cenario(db_session: AsyncSession, sufixo: str) -> tuple[Usuario, Anuncio, Anuncio]:
    async with db_session.begin():
        vendedor = Usuario(
            nome="Vendedor Destaque",
            email=f"vendedor-destaque-{sufixo}@example.com",
            senha_hash="hash",
            telefone=None,
            status=UsuarioStatus.ATIVO,
        )
        categoria = Categoria(
            nome=f"Categoria destaque {sufixo}", descricao=None, status=CategoriaStatus.ATIVA
        )
        db_session.add_all([vendedor, categoria])
        await db_session.flush()
        endereco = Endereco(
            usuario_id=vendedor.id,
            cep="01310100",
            logradouro="Avenida Paulista",
            numero="1",
            complemento=None,
            bairro="Bela Vista",
            cidade="São Paulo",
            estado="SP",
            deletado_em=None,
        )
        db_session.add(endereco)
        await db_session.flush()
        anuncios = [
            Anuncio(
                titulo=titulo,
                descricao="Material de obra para testar o destaque.",
                categoria_id=categoria.id,
                vendedor_id=vendedor.id,
                endereco_id=endereco.id,
                preco=Decimal("50.00"),
                imagem_url=None,
                quantidade=3,
                status=AnuncioStatus.ATIVO,
                postado_em=postado_em,
            )
            for titulo, postado_em in (
                (f"Anúncio antigo {sufixo}", datetime.now(UTC) - timedelta(days=3)),
                (f"Anúncio recente {sufixo}", datetime.now(UTC)),
            )
        ]
        db_session.add_all(anuncios)
        await db_session.flush()
    for objeto in (vendedor, *anuncios):
        db_session.expunge(objeto)
    return vendedor, anuncios[0], anuncios[1]


async def _webhook_pagamento(
    db_session: AsyncSession,
    servico: WebhookMercadoPagoService,
    gateway: FakeGateway,
    *,
    pagamento_id: str,
    destaque_id: UUID,
    status: str,
    valor: str = "10.00",
    evento_externo_id: str | None = None,
) -> UUID:
    gateway.pagamentos[pagamento_id] = {
        "id": pagamento_id,
        "external_reference": f"destaque:{destaque_id}",
        "metadata": {"destaque_id": str(destaque_id)},
        "collector_id": MARKETPLACE,
        "transaction_amount": valor,
        "status": status,
        "status_detail": "accredited" if status == "approved" else status,
        "payment_type_id": "bank_transfer",
        "payment_method_id": "pix",
        "live_mode": False,
    }
    payload = {"type": "payment", "user_id": MARKETPLACE, "data": {"id": pagamento_id}}
    async with db_session.begin():
        evento = EventoProvedor(
            provedor=ProvedorPagamento.MERCADO_PAGO,
            evento_externo_id=evento_externo_id or f"evt-{pagamento_id}-{status}",
            tipo="payment",
            recurso_externo_id=pagamento_id,
            payload=payload,
            status_processamento=EventoProcessamentoStatus.PENDENTE,
            tentativas=1,
            bloqueado_por=TRABALHADOR,
        )
        db_session.add(evento)
        await db_session.flush()
        evento_id = evento.id
    await servico._executar_evento(evento_id, payload, pagamento_id, TRABALHADOR)
    return evento_id


async def test_checkout_destaque_cria_preferencia_com_valor_fixo_e_retoma(
    db_session: AsyncSession,
) -> None:
    vendedor, anuncio, _ = await _cenario(db_session, "checkout")
    gateway = FakeGateway()
    servico = DestaqueAnuncioService(
        db_session, settings=_settings(), gateway=cast(MercadoPagoGateway, gateway)
    )

    resposta = await servico.criar_checkout(
        anuncio.id, vendedor_id=vendedor.id, vendedor_email=vendedor.email, vendedor_nome="Ana Lima"
    )

    assert resposta.valor == Decimal("10.00")
    assert resposta.duracao_dias == 7
    assert resposta.init_point == "https://mp.test/checkout/1"
    payload = gateway.payloads[0]
    assert payload["external_reference"] == f"destaque:{resposta.destaque_id}"
    assert payload["items"][0]["unit_price"] == 10.0
    assert payload["items"][0]["quantity"] == 1
    assert payload["metadata"]["destaque_id"] == str(resposta.destaque_id)
    assert payload["notification_url"] == "https://example.test/webhook"

    retomada = await servico.criar_checkout(
        anuncio.id, vendedor_id=vendedor.id, vendedor_email=vendedor.email
    )
    assert retomada.destaque_id == resposta.destaque_id
    assert retomada.init_point == "https://mp.test/checkout/retomado"
    assert len(gateway.payloads) == 1

    async with db_session.begin():
        destaque = await db_session.get(DestaqueAnuncio, resposta.destaque_id)
        assert destaque is not None
        assert destaque.status == DestaqueAnuncioStatus.AGUARDANDO_PAGAMENTO
        assert destaque.status_pagamento == PagamentoStatus.PENDENTE
        assert destaque.preferencia_externa_id == "PREF-D1"


async def test_checkout_destaque_recusa_anuncio_de_outro_vendedor_ou_indisponivel(
    db_session: AsyncSession,
) -> None:
    vendedor, anuncio, outro = await _cenario(db_session, "regras")
    async with db_session.begin():
        alvo = await db_session.get(Anuncio, outro.id)
        assert alvo is not None
        alvo.status = AnuncioStatus.ENCERRADO
    servico = DestaqueAnuncioService(
        db_session, settings=_settings(), gateway=cast(MercadoPagoGateway, FakeGateway())
    )

    with pytest.raises(AppError) as erro:
        await servico.criar_checkout(
            anuncio.id, vendedor_id=UUID(int=1), vendedor_email="x@example.com"
        )
    assert erro.value.status_code == 403

    with pytest.raises(AppError) as erro:
        await servico.criar_checkout(
            outro.id, vendedor_id=vendedor.id, vendedor_email=vendedor.email
        )
    assert erro.value.code == "AD_NOT_AVAILABLE_FOR_FEATURE"


async def test_webhook_aprova_destaque_estende_e_ordena_listagem(
    db_session: AsyncSession,
) -> None:
    vendedor, antigo, recente = await _cenario(db_session, "webhook")
    settings = _settings()
    gateway = FakeGateway()
    destaques = DestaqueAnuncioService(
        db_session, settings=settings, gateway=cast(MercadoPagoGateway, gateway)
    )
    webhook = WebhookMercadoPagoService(
        db_session, settings=settings, gateway=cast(MercadoPagoGateway, gateway)
    )

    checkout = await destaques.criar_checkout(
        antigo.id, vendedor_id=vendedor.id, vendedor_email=vendedor.email
    )
    antes = datetime.now(UTC)
    evento_id = await _webhook_pagamento(
        db_session,
        webhook,
        gateway,
        pagamento_id="PAY-D1",
        destaque_id=checkout.destaque_id,
        status="approved",
    )
    # Reprocessar o mesmo evento não estende o destaque outra vez.
    payload = {"type": "payment", "user_id": MARKETPLACE, "data": {"id": "PAY-D1"}}
    await webhook._executar_evento(evento_id, payload, "PAY-D1", TRABALHADOR)
    # Um novo evento com o mesmo estado também é idempotente.
    await _webhook_pagamento(
        db_session,
        webhook,
        gateway,
        pagamento_id="PAY-D1",
        destaque_id=checkout.destaque_id,
        status="approved",
        evento_externo_id="evt-repetido",
    )

    async with db_session.begin():
        destaque = await db_session.get(DestaqueAnuncio, checkout.destaque_id)
        anuncio = await db_session.get(Anuncio, antigo.id)
        evento = await db_session.get(EventoProvedor, evento_id)
        assert destaque is not None and anuncio is not None and evento is not None
        assert destaque.status == DestaqueAnuncioStatus.ATIVO
        assert destaque.status_pagamento == PagamentoStatus.APROVADO
        assert destaque.metodo == MetodoPagamento.PIX
        assert destaque.expira_em is not None and destaque.inicia_em is not None
        assert destaque.expira_em - destaque.inicia_em == timedelta(days=7)
        assert anuncio.destaque_ate == destaque.expira_em
        assert anuncio.destaque_ate >= antes + timedelta(days=7)
        assert evento.status_processamento == EventoProcessamentoStatus.PROCESSADO
        primeiro_fim = anuncio.destaque_ate

    async with db_session.begin():
        itens, _ = await AnuncioRepository(db_session).listar(
            AnuncioFilters(search="webhook"), vendedor_id=vendedor.id
        )
        assert [item.id for item in itens] == [antigo.id, recente.id]
        assert AnuncioResponse.model_validate(itens[0]).em_destaque is True
        assert AnuncioResponse.model_validate(itens[1]).em_destaque is False

    # Uma segunda compra durante a vigência estende o destaque atual.
    segundo = await destaques.criar_checkout(
        antigo.id, vendedor_id=vendedor.id, vendedor_email=vendedor.email
    )
    assert segundo.destaque_id != checkout.destaque_id
    await _webhook_pagamento(
        db_session,
        webhook,
        gateway,
        pagamento_id="PAY-D2",
        destaque_id=segundo.destaque_id,
        status="approved",
    )
    async with db_session.begin():
        anuncio = await db_session.get(Anuncio, antigo.id)
        assert anuncio is not None
        assert anuncio.destaque_ate == primeiro_fim + timedelta(days=7)

    # O estorno remove somente o período ainda não usufruído daquela compra.
    await _webhook_pagamento(
        db_session,
        webhook,
        gateway,
        pagamento_id="PAY-D2",
        destaque_id=segundo.destaque_id,
        status="refunded",
    )
    async with db_session.begin():
        anuncio = await db_session.get(Anuncio, antigo.id)
        revogado = await db_session.get(DestaqueAnuncio, segundo.destaque_id)
        assert anuncio is not None and revogado is not None
        assert anuncio.destaque_ate == primeiro_fim
        assert revogado.status == DestaqueAnuncioStatus.REEMBOLSADO


async def test_webhook_destaque_recusa_valor_divergente(db_session: AsyncSession) -> None:
    vendedor, anuncio, _ = await _cenario(db_session, "divergente")
    settings = _settings()
    gateway = FakeGateway()
    checkout = await DestaqueAnuncioService(
        db_session, settings=settings, gateway=cast(MercadoPagoGateway, gateway)
    ).criar_checkout(anuncio.id, vendedor_id=vendedor.id, vendedor_email=vendedor.email)
    webhook = WebhookMercadoPagoService(
        db_session, settings=settings, gateway=cast(MercadoPagoGateway, gateway)
    )

    with pytest.raises(AppError) as erro:
        await _webhook_pagamento(
            db_session,
            webhook,
            gateway,
            pagamento_id="PAY-D9",
            destaque_id=checkout.destaque_id,
            status="approved",
            valor="1.00",
        )
    assert erro.value.code == "PAYMENT_AMOUNT_MISMATCH"

    async with db_session.begin():
        anuncio_atual = await db_session.get(Anuncio, anuncio.id)
        destaque = await db_session.scalar(
            select(DestaqueAnuncio).where(DestaqueAnuncio.id == checkout.destaque_id)
        )
        assert anuncio_atual is not None and destaque is not None
        assert anuncio_atual.destaque_ate is None
        assert destaque.status == DestaqueAnuncioStatus.AGUARDANDO_PAGAMENTO


async def test_preco_do_destaque_vem_da_configuracao(client: Any) -> None:
    resposta = await client.get("/api/v1/featured-ads/pricing")
    assert resposta.status_code == 200
    assert Decimal(resposta.json()["valor"]) == Decimal("10.00")
    assert resposta.json()["duracao_dias"] == 7

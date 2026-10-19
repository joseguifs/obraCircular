import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.enums import EventoProcessamentoStatus, ProvedorPagamento
from app.models.evento_provedor import EventoProvedor
from app.services.webhook_mercado_pago import WebhookMercadoPagoService


def _assinatura(*, data_id: str, request_id: str, secret: str, timestamp: str) -> str:
    manifesto = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(secret.encode("utf-8"), manifesto.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={timestamp},v1={digest}"


async def test_endpoint_de_monitoramento_expoe_somente_contadores(
    client: AsyncClient,
) -> None:
    resposta = await client.get("/api/v1/health/webhooks")

    corpo = resposta.json()
    assert resposta.status_code == (200 if corpo["status"] == "ok" else 503)
    assert set(corpo) == {
        "status",
        "pendentes",
        "falhas_agendadas",
        "falhas_sem_retentativa",
        "em_processamento",
        "abandonados",
        "processados",
        "ignorados",
        "mais_antigo_nao_finalizado_em",
    }
    assert corpo["status"] in {"ok", "degraded", "critical"}


async def test_recebimento_valido_persiste_evento_sem_processar(
    db_session: AsyncSession,
) -> None:
    segredo = "segredo-webhook"
    request_id = "request-1"
    data_id = "payment-123"
    payload = {
        "id": "notification-123",
        "type": "payment",
        "user_id": "seller-1",
        "data": {"id": data_id},
    }
    settings = Settings(mp_webhook_secret=SecretStr(segredo))
    servico = WebhookMercadoPagoService(db_session, settings=settings)

    evento_id = await servico.receber(
        payload=payload,
        data_id=data_id,
        x_request_id=request_id,
        x_signature=_assinatura(
            data_id=data_id,
            request_id=request_id,
            secret=segredo,
            timestamp="1720000000",
        ),
    )
    evento_repetido_id = await servico.receber(
        payload=payload,
        data_id=data_id,
        x_request_id=request_id,
        x_signature=_assinatura(
            data_id=data_id,
            request_id=request_id,
            secret=segredo,
            timestamp="1720000000",
        ),
    )

    evento = await db_session.get(EventoProvedor, evento_id)
    assert evento is not None
    assert evento_repetido_id == evento_id
    assert evento.status_processamento == EventoProcessamentoStatus.PENDENTE
    assert evento.tentativas == 0
    assert evento.proxima_tentativa_em is not None
    assert evento.ultima_tentativa_em is None


async def test_falha_transitoria_libera_lease_e_aplica_backoff(
    db_session: AsyncSession,
) -> None:
    agora = datetime.now(UTC)
    evento = EventoProvedor(
        provedor=ProvedorPagamento.MERCADO_PAGO,
        evento_externo_id="retry-event-1",
        tipo="payment",
        recurso_externo_id="payment-retry-1",
        payload={"type": "payment", "data": {"id": "payment-retry-1"}},
        status_processamento=EventoProcessamentoStatus.FALHOU,
        tentativas=0,
        ultima_tentativa_em=None,
        proxima_tentativa_em=agora - timedelta(seconds=1),
        bloqueado_ate=None,
        bloqueado_por=None,
        processado_em=None,
        erro="indisponível",
    )
    async with db_session.begin():
        db_session.add(evento)
        await db_session.flush()
        evento_id = evento.id

    settings = Settings(
        webhook_retry_max_attempts=3,
        webhook_retry_base_seconds=10,
        webhook_retry_max_seconds=40,
        webhook_processing_lease_seconds=60,
    )
    servico = WebhookMercadoPagoService(db_session, settings=settings)
    reivindicado = await servico._reivindicar_evento(
        evento_id=evento_id,
        trabalhador="worker-test",
        forcar=False,
    )

    assert reivindicado is not None
    evento_reivindicado = await db_session.get(EventoProvedor, evento_id)
    assert evento_reivindicado is not None
    assert evento_reivindicado.tentativas == 1
    assert evento_reivindicado.bloqueado_por == "worker-test"
    assert evento_reivindicado.bloqueado_ate is not None

    antes_da_falha = datetime.now(UTC)
    await servico._marcar_evento(
        evento_id,
        EventoProcessamentoStatus.FALHOU,
        erro="timeout",
        reprocessavel=True,
        trabalhador="worker-test",
    )

    evento_falho = await db_session.get(EventoProvedor, evento_id)
    assert evento_falho is not None
    assert evento_falho.status_processamento == EventoProcessamentoStatus.FALHOU
    assert evento_falho.bloqueado_ate is None
    assert evento_falho.bloqueado_por is None
    assert evento_falho.proxima_tentativa_em is not None
    assert evento_falho.proxima_tentativa_em >= antes_da_falha + timedelta(seconds=10)
    await db_session.rollback()
    assert not await servico.reprocessar_evento(evento_id)


async def test_limite_de_tentativas_exige_reprocessamento_manual(
    db_session: AsyncSession,
) -> None:
    agora = datetime.now(UTC)
    evento = EventoProvedor(
        provedor=ProvedorPagamento.MERCADO_PAGO,
        evento_externo_id="retry-event-exhausted",
        tipo="unknown",
        recurso_externo_id="resource-exhausted",
        payload={"type": "unknown", "data": {"id": "resource-exhausted"}},
        status_processamento=EventoProcessamentoStatus.FALHOU,
        tentativas=2,
        ultima_tentativa_em=agora,
        proxima_tentativa_em=None,
        bloqueado_ate=None,
        bloqueado_por=None,
        processado_em=None,
        erro="limite atingido",
    )
    async with db_session.begin():
        db_session.add(evento)
        await db_session.flush()
        evento_id = evento.id

    settings = Settings(webhook_retry_max_attempts=2)
    servico = WebhookMercadoPagoService(db_session, settings=settings)

    assert not await servico.reprocessar_evento(evento_id)
    resumo = await servico.obter_monitoramento()
    assert resumo.status == "critical"
    assert resumo.falhas_sem_retentativa >= 1

    assert await servico.reprocessar_evento(evento_id, forcar=True)
    evento_processado = await db_session.get(EventoProvedor, evento_id)
    assert evento_processado is not None
    assert evento_processado.status_processamento == EventoProcessamentoStatus.IGNORADO
    assert evento_processado.bloqueado_ate is None


async def test_lease_expirado_e_retomado_sem_agendamento(db_session: AsyncSession) -> None:
    servico = WebhookMercadoPagoService(db_session)
    evento = await servico._registrar_evento(
        str(uuid4()), "resource", {"type": "unknown", "data": {"id": "resource"}}
    )
    evento_id = evento.id
    assert (
        await servico._reivindicar_evento(
            evento_id=evento_id, trabalhador="worker-morto", forcar=False
        )
        is not None
    )
    async with db_session.begin():
        evento.bloqueado_ate = datetime.now(UTC) - timedelta(seconds=1)
    resumo = await servico.obter_monitoramento()
    assert resumo.abandonados >= 1
    assert resumo.status == "critical"
    assert await servico.reprocessar_evento(evento_id)
    async with db_session.begin():
        await db_session.refresh(evento)
        assert evento.status_processamento == EventoProcessamentoStatus.IGNORADO
        assert evento.tentativas == 2
        assert evento.bloqueado_ate is None


async def test_queda_na_ultima_tentativa_e_visivel_como_falha(
    db_session: AsyncSession,
) -> None:
    servico = WebhookMercadoPagoService(db_session, settings=Settings(webhook_retry_max_attempts=1))
    evento = await servico._registrar_evento(str(uuid4()), "resource", {"type": "unknown"})
    evento_id = evento.id
    await servico._reivindicar_evento(evento_id=evento_id, trabalhador="worker-morto", forcar=False)
    async with db_session.begin():
        evento.bloqueado_ate = datetime.now(UTC) - timedelta(seconds=1)
    assert not await servico.reprocessar_evento(evento_id)
    async with db_session.begin():
        await db_session.refresh(evento)
        assert evento.status_processamento == EventoProcessamentoStatus.FALHOU
        assert evento.tentativas == 1
        assert evento.bloqueado_por is None
    assert (await servico.obter_monitoramento()).falhas_sem_retentativa >= 1


async def test_worker_antigo_nao_sobrescreve_lease_do_novo(db_session: AsyncSession) -> None:
    servico = WebhookMercadoPagoService(db_session)
    evento = await servico._registrar_evento(str(uuid4()), "resource", {"type": "unknown"})
    evento_id = evento.id
    await servico._reivindicar_evento(evento_id=evento_id, trabalhador="worker-a", forcar=False)
    assert (
        await servico._reivindicar_evento(evento_id=evento_id, trabalhador="worker-b", forcar=False)
        is None
    )
    async with db_session.begin():
        evento.bloqueado_ate = datetime.now(UTC) - timedelta(seconds=1)
    assert (
        await servico._reivindicar_evento(evento_id=evento_id, trabalhador="worker-b", forcar=False)
        is not None
    )
    await servico._marcar_evento(
        evento_id,
        EventoProcessamentoStatus.FALHOU,
        erro="worker antigo",
        reprocessavel=True,
        trabalhador="worker-a",
    )
    async with db_session.begin():
        await db_session.refresh(evento)
        assert evento.bloqueado_por == "worker-b"
        assert evento.status_processamento == EventoProcessamentoStatus.PENDENTE

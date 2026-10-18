import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

import app.main as principal
from app.jobs import reprocessar_webhooks, webhook_worker
from app.services.webhook_mercado_pago import WebhookMercadoPagoService, WebhookMonitoramento


def _resumo(status: str) -> WebhookMonitoramento:
    return WebhookMonitoramento(
        status=status,
        pendentes=0,
        falhas_agendadas=0,
        falhas_sem_retentativa=0,
        em_processamento=0,
        abandonados=int(status == "critical"),
        processados=0,
        ignorados=0,
        mais_antigo_nao_finalizado_em=None,
    )


@pytest.mark.parametrize("status,esperado", [("ok", 0), ("degraded", 1), ("critical", 1)])
async def test_job_sinaliza_backlog_e_abandono(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    esperado: int,
) -> None:
    fabrica = MagicMock()
    servico = MagicMock()
    servico.reprocessar_pendentes = AsyncMock(return_value=0)
    servico.obter_monitoramento = AsyncMock(return_value=_resumo(status))
    monkeypatch.setattr(reprocessar_webhooks, "SessionLocal", fabrica)
    monkeypatch.setattr(reprocessar_webhooks, "WebhookMercadoPagoService", lambda _: servico)
    assert await reprocessar_webhooks.executar(evento_id=None, forcar=False) == esperado


async def test_endpoint_critical_retorna_503_sem_payloads(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        WebhookMercadoPagoService,
        "obter_monitoramento",
        AsyncMock(return_value=_resumo("critical")),
    )
    resposta = await client.get("/api/v1/health/webhooks")
    assert resposta.status_code == 503
    assert resposta.json()["abandonados"] == 1
    assert "payload" not in resposta.json()


async def test_worker_executa_novo_ciclo_apos_erro(monkeypatch: pytest.MonkeyPatch) -> None:
    servico = MagicMock()
    servico.reprocessar_pendentes = AsyncMock(side_effect=[RuntimeError("db indisponível"), 1])
    servico.obter_monitoramento = AsyncMock(return_value=_resumo("ok"))
    fabrica = MagicMock()
    pausa = AsyncMock(side_effect=[None, asyncio.CancelledError()])
    monkeypatch.setattr(webhook_worker, "SessionLocal", fabrica)
    monkeypatch.setattr(webhook_worker, "WebhookMercadoPagoService", lambda _: servico)
    # Substituir somente o namespace deste módulo, preservando asyncio dos testes.
    monkeypatch.setattr(webhook_worker, "asyncio", MagicMock(sleep=pausa))
    with pytest.raises(asyncio.CancelledError):
        await webhook_worker.executar_worker_webhooks()
    assert servico.reprocessar_pendentes.await_count == 2
    assert servico.obter_monitoramento.await_count == 1


async def test_lifespan_inicia_e_encerra_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    iniciou, encerrou = asyncio.Event(), asyncio.Event()

    async def worker() -> None:
        iniciou.set()
        try:
            await asyncio.Future()
        finally:
            encerrou.set()

    monkeypatch.setattr(principal.settings, "webhook_worker_enabled", True)
    monkeypatch.setattr(principal, "executar_worker_webhooks", worker)
    monkeypatch.setattr(principal, "engine", MagicMock(dispose=AsyncMock()))
    async with principal.lifespan(principal.app):
        await asyncio.wait_for(iniciou.wait(), timeout=1)
    assert encerrou.is_set()

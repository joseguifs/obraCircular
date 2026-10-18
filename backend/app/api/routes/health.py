from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Response

from app.api.dependencies import DatabaseSession
from app.services.webhook_mercado_pago import WebhookMercadoPagoService

router = APIRouter(tags=["health"])


@router.get("/health", summary="Verifica se a API está disponível")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/webhooks", summary="Monitora o processamento dos webhooks")
async def webhook_health_check(session: DatabaseSession, response: Response) -> dict[str, Any]:
    resumo = await WebhookMercadoPagoService(session).obter_monitoramento()
    if resumo.status != "ok":
        response.status_code = 503
    return asdict(resumo)

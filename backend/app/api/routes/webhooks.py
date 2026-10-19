import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Header, Query, Request, Response, status

from app.api.dependencies import DatabaseSession
from app.core.database import SessionLocal
from app.core.exceptions import AppError
from app.services.webhook_mercado_pago import WebhookMercadoPagoService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


async def processar_webhook_em_segundo_plano(evento_id: UUID) -> None:
    try:
        async with SessionLocal() as session:
            await WebhookMercadoPagoService(session).reprocessar_evento(evento_id)
    except Exception:
        logger.exception("Falha inesperada no worker imediato de webhook: evento_id=%s", evento_id)


@router.post("/mercado-pago", status_code=status.HTTP_200_OK)
async def webhook_mercado_pago(
    request: Request,
    session: DatabaseSession,
    background_tasks: BackgroundTasks,
    data_id: Annotated[str, Query(alias="data.id", min_length=1)],
    x_signature: Annotated[str | None, Header()] = None,
    x_request_id: Annotated[str | None, Header()] = None,
) -> Response:
    if not x_signature or not x_request_id:
        raise AppError(
            status_code=401,
            detail="Cabeçalhos de assinatura do webhook ausentes.",
            code="MP_WEBHOOK_SIGNATURE_MISSING",
        )
    try:
        payload: Any = await request.json()
    except ValueError as exc:
        raise AppError(
            status_code=400,
            detail="Payload do webhook inválido.",
            code="MP_WEBHOOK_PAYLOAD_INVALID",
        ) from exc
    if not isinstance(payload, dict):
        raise AppError(
            status_code=400,
            detail="Payload do webhook inválido.",
            code="MP_WEBHOOK_PAYLOAD_INVALID",
        )
    evento_id = await WebhookMercadoPagoService(session).receber(
        payload=payload,
        data_id=data_id,
        x_signature=x_signature,
        x_request_id=x_request_id,
    )
    background_tasks.add_task(processar_webhook_em_segundo_plano, evento_id)
    return Response(status_code=status.HTTP_200_OK)

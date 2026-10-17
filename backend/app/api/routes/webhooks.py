from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request, Response, status

from app.api.dependencies import DatabaseSession
from app.core.exceptions import AppError
from app.services.webhook_mercado_pago import WebhookMercadoPagoService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/mercado-pago", status_code=status.HTTP_200_OK)
async def webhook_mercado_pago(
    request: Request,
    session: DatabaseSession,
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
    await WebhookMercadoPagoService(session).receber(
        payload=payload,
        data_id=data_id,
        x_signature=x_signature,
        x_request_id=x_request_id,
    )
    return Response(status_code=status.HTTP_200_OK)

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.mercado_pago import MercadoPagoGateway
from app.models.pedido import Pedido
from app.services.conta_pagamento import ContaPagamentoService


def token_marketplace(settings: Settings) -> str:
    if not settings.mp_access_token or not settings.mp_marketplace_user_id:
        raise AppError(
            status_code=503,
            detail="Configure a conta recebedora e o access token da Obra Circular.",
            code="MP_MARKETPLACE_NOT_CONFIGURED",
        )
    return settings.mp_access_token.get_secret_value()


async def token_do_pedido(
    session: AsyncSession,
    pedido_id: UUID,
    vendedor_id: UUID,
    settings: Settings,
    gateway: MercadoPagoGateway,
) -> str:
    pedido = await session.scalar(select(Pedido).where(Pedido.id == pedido_id))
    if pedido is None:
        raise AppError(status_code=404, detail="Pedido não encontrado.", code="ORDER_NOT_FOUND")
    centralizado = pedido.modelo_financeiro == "REPASSE_POSTERIOR"
    recebedor = pedido.recebedor_externo_id
    await session.rollback()
    if centralizado:
        if recebedor != settings.mp_marketplace_user_id:
            raise AppError(
                status_code=409,
                detail="A conta recebedora deste pedido não está configurada.",
                code="MP_COLLECTOR_CONFIGURATION_MISMATCH",
            )
        return token_marketplace(settings)
    _, token = await ContaPagamentoService(
        session, settings=settings, gateway=gateway
    ).obter_access_token(vendedor_id)
    return token

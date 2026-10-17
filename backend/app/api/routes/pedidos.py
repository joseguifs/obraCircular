from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.pedido import (
    CheckoutCreate,
    CheckoutResponse,
    PedidoListResponse,
    PedidoResponse,
    ReembolsoResponse,
)
from app.services.pedido import PedidoService
from app.services.reembolso import ReembolsoService

router = APIRouter(prefix="/orders", tags=["pedidos"])


@router.post("/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
async def criar_checkout(
    dados: CheckoutCreate, session: DatabaseSession, comprador: CurrentUser
) -> CheckoutResponse:
    return await PedidoService(session).criar_checkout(
        dados, comprador_id=comprador.id, comprador_email=comprador.email
    )


@router.get("", response_model=PedidoListResponse)
async def listar_pedidos(session: DatabaseSession, comprador: CurrentUser) -> PedidoListResponse:
    return await PedidoService(session).listar(comprador.id)


@router.get("/{pedido_id}", response_model=PedidoResponse)
async def consultar_pedido(
    pedido_id: UUID, session: DatabaseSession, comprador: CurrentUser
) -> PedidoResponse:
    return await PedidoService(session).buscar(pedido_id, comprador.id)


@router.post("/{pedido_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancelar_pedido(
    pedido_id: UUID, session: DatabaseSession, comprador: CurrentUser
) -> Response:
    await PedidoService(session).cancelar(pedido_id, comprador.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{pedido_id}/refund", response_model=ReembolsoResponse)
async def solicitar_reembolso(
    pedido_id: UUID, session: DatabaseSession, comprador: CurrentUser
) -> ReembolsoResponse:
    return await ReembolsoService(session).solicitar(pedido_id, comprador.id)

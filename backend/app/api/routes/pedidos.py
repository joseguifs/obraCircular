from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.contestacao import (
    ContestacaoCreate,
    ContestacaoListResponse,
    ContestacaoResponse,
)
from app.schemas.entrega import EntregaConfirmacaoCreate, EntregaPinResponse, EntregaResponse
from app.schemas.pedido import (
    CheckoutCreate,
    CheckoutResponse,
    PedidoListResponse,
    PedidoResponse,
    ReembolsoResponse,
)
from app.services.contestacao import ContestacaoService
from app.services.entrega import EntregaService
from app.services.pedido import PedidoService
from app.services.reembolso import ReembolsoService

router = APIRouter(prefix="/orders", tags=["pedidos"])


@router.post("/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
async def criar_checkout(
    dados: CheckoutCreate, session: DatabaseSession, comprador: CurrentUser
) -> CheckoutResponse:
    return await PedidoService(session).criar_checkout(
        dados,
        comprador_id=comprador.id,
        comprador_email=comprador.email,
        comprador_nome=comprador.nome,
        comprador_criado_em=comprador.criado_em,
    )


@router.get("", response_model=PedidoListResponse)
async def listar_pedidos(session: DatabaseSession, comprador: CurrentUser) -> PedidoListResponse:
    return await PedidoService(session).listar(comprador.id)


@router.get("/sales", response_model=PedidoListResponse)
async def listar_vendas(session: DatabaseSession, vendedor: CurrentUser) -> PedidoListResponse:
    return await PedidoService(session).listar_vendas(vendedor.id)


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


@router.post(
    "/{pedido_id}/delivery/pin",
    response_model=EntregaPinResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gera o PIN de confirmação da entrega (comprador)",
)
async def gerar_pin_entrega(
    pedido_id: UUID, session: DatabaseSession, comprador: CurrentUser
) -> EntregaPinResponse:
    """Cada chamada gera um novo PIN e invalida o anterior; o PIN só é exibido aqui."""
    return await EntregaService(session).gerar_pin(pedido_id, comprador.id)


@router.post(
    "/{pedido_id}/delivery/confirm",
    response_model=EntregaResponse,
    summary="Confirma a entrega com o PIN informado pelo comprador (vendedor)",
)
async def confirmar_entrega(
    pedido_id: UUID,
    dados: EntregaConfirmacaoCreate,
    session: DatabaseSession,
    vendedor: CurrentUser,
) -> EntregaResponse:
    return await EntregaService(session).confirmar(pedido_id, vendedor.id, dados.pin)


@router.post(
    "/{pedido_id}/disputes",
    response_model=ContestacaoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def abrir_contestacao(
    pedido_id: UUID,
    dados: ContestacaoCreate,
    session: DatabaseSession,
    comprador: CurrentUser,
) -> ContestacaoResponse:
    return await ContestacaoService(session).abrir(pedido_id, dados, comprador.id)


@router.get("/{pedido_id}/disputes", response_model=ContestacaoListResponse)
async def listar_contestacoes(
    pedido_id: UUID, session: DatabaseSession, comprador: CurrentUser
) -> ContestacaoListResponse:
    return await ContestacaoService(session).listar(pedido_id, comprador.id)

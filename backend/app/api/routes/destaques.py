from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.destaque_anuncio import (
    DestaqueAnuncioListResponse,
    DestaqueAnuncioResponse,
    DestaqueCheckoutCreate,
    DestaqueCheckoutResponse,
    DestaquePrecoResponse,
)
from app.services.destaque_anuncio import DestaqueAnuncioService

router = APIRouter(prefix="/featured-ads", tags=["destaques"])


@router.get(
    "/pricing",
    response_model=DestaquePrecoResponse,
    summary="Consulta o preço e a duração do destaque de anúncio",
)
async def consultar_preco(session: DatabaseSession) -> DestaquePrecoResponse:
    return DestaqueAnuncioService(session).preco()


@router.post(
    "/checkout",
    response_model=DestaqueCheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inicia o pagamento do destaque de um anúncio do vendedor",
)
async def criar_checkout_destaque(
    dados: DestaqueCheckoutCreate, session: DatabaseSession, vendedor: CurrentUser
) -> DestaqueCheckoutResponse:
    return await DestaqueAnuncioService(session).criar_checkout(
        dados.anuncio_id,
        vendedor_id=vendedor.id,
        vendedor_email=vendedor.email,
        vendedor_nome=vendedor.nome,
        vendedor_criado_em=vendedor.criado_em,
    )


@router.get(
    "",
    response_model=DestaqueAnuncioListResponse,
    summary="Lista as compras de destaque de um anúncio do vendedor",
)
async def listar_destaques(
    anuncio_id: Annotated[UUID, Query()],
    session: DatabaseSession,
    vendedor: CurrentUser,
) -> DestaqueAnuncioListResponse:
    return await DestaqueAnuncioService(session).listar(anuncio_id, vendedor.id)


@router.get(
    "/{destaque_id}",
    response_model=DestaqueAnuncioResponse,
    summary="Consulta uma compra de destaque do vendedor",
)
async def consultar_destaque(
    destaque_id: UUID, session: DatabaseSession, vendedor: CurrentUser
) -> DestaqueAnuncioResponse:
    return await DestaqueAnuncioService(session).buscar(destaque_id, vendedor.id)

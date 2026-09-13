from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.anuncio import (
    AnuncioCreate,
    AnuncioFilters,
    AnuncioListResponse,
    AnuncioResponse,
    AnuncioUpdate,
)
from app.services.anuncio import AnuncioService

router = APIRouter(prefix="/ads", tags=["anúncios"])
user_router = APIRouter(prefix="/users", tags=["anúncios"])


@router.post(
    "",
    response_model=AnuncioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria um anúncio para o vendedor autenticado",
)
async def criar_anuncio(
    dados: AnuncioCreate,
    session: DatabaseSession,
    vendedor: CurrentUser,
) -> AnuncioResponse:
    anuncio = await AnuncioService(session).criar(dados, vendedor.id)
    return AnuncioResponse.model_validate(anuncio)


@router.get(
    "",
    response_model=AnuncioListResponse,
    summary="Lista e filtra anúncios",
)
async def listar_anuncios(
    session: DatabaseSession,
    filtros: Annotated[AnuncioFilters, Query()],
) -> AnuncioListResponse:
    return await AnuncioService(session).listar(filtros)


@router.get(
    "/{anuncio_id}",
    response_model=AnuncioResponse,
    summary="Consulta um anúncio",
)
async def buscar_anuncio(anuncio_id: UUID, session: DatabaseSession) -> AnuncioResponse:
    anuncio = await AnuncioService(session).buscar(anuncio_id)
    return AnuncioResponse.model_validate(anuncio)


@router.patch(
    "/{anuncio_id}",
    response_model=AnuncioResponse,
    summary="Atualiza um anúncio do vendedor",
)
async def atualizar_anuncio(
    anuncio_id: UUID,
    dados: AnuncioUpdate,
    session: DatabaseSession,
    vendedor: CurrentUser,
) -> AnuncioResponse:
    anuncio = await AnuncioService(session).atualizar(anuncio_id, dados, vendedor.id)
    return AnuncioResponse.model_validate(anuncio)


@router.delete(
    "/{anuncio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui logicamente um anúncio do vendedor",
)
async def excluir_anuncio(
    anuncio_id: UUID,
    session: DatabaseSession,
    vendedor: CurrentUser,
) -> Response:
    await AnuncioService(session).excluir(anuncio_id, vendedor.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@user_router.get(
    "/{vendedor_id}/ads",
    response_model=AnuncioListResponse,
    summary="Lista os anúncios de um vendedor",
)
async def listar_anuncios_do_vendedor(
    vendedor_id: UUID,
    session: DatabaseSession,
    filtros: Annotated[AnuncioFilters, Query()],
) -> AnuncioListResponse:
    return await AnuncioService(session).listar(filtros, vendedor_id=vendedor_id)

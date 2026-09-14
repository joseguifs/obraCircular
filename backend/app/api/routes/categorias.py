from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.categoria import (
    CategoriaCreate,
    CategoriaFilters,
    CategoriaListResponse,
    CategoriaResponse,
    CategoriaUpdate,
)
from app.services.categoria import CategoriaService

router = APIRouter(prefix="/categories", tags=["categorias"])


@router.post(
    "",
    response_model=CategoriaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria uma categoria",
)
async def criar_categoria(
    dados: CategoriaCreate,
    session: DatabaseSession,
    _usuario: CurrentUser,
) -> CategoriaResponse:
    categoria = await CategoriaService(session).criar(dados)
    return CategoriaResponse.model_validate(categoria)


@router.get(
    "",
    response_model=CategoriaListResponse,
    summary="Lista e filtra categorias",
)
async def listar_categorias(
    session: DatabaseSession,
    filtros: Annotated[CategoriaFilters, Query()],
) -> CategoriaListResponse:
    return await CategoriaService(session).listar(filtros)


@router.get(
    "/{categoria_id}",
    response_model=CategoriaResponse,
    summary="Consulta uma categoria",
)
async def buscar_categoria(categoria_id: UUID, session: DatabaseSession) -> CategoriaResponse:
    categoria = await CategoriaService(session).buscar(categoria_id)
    return CategoriaResponse.model_validate(categoria)


@router.patch(
    "/{categoria_id}",
    response_model=CategoriaResponse,
    summary="Atualiza uma categoria",
)
async def atualizar_categoria(
    categoria_id: UUID,
    dados: CategoriaUpdate,
    session: DatabaseSession,
    _usuario: CurrentUser,
) -> CategoriaResponse:
    categoria = await CategoriaService(session).atualizar(categoria_id, dados)
    return CategoriaResponse.model_validate(categoria)


@router.delete(
    "/{categoria_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Inativa uma categoria (exclusão lógica)",
)
async def excluir_categoria(
    categoria_id: UUID,
    session: DatabaseSession,
    _usuario: CurrentUser,
) -> Response:
    await CategoriaService(session).excluir(categoria_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

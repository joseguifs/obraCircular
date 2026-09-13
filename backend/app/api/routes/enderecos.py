from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.schemas.endereco import (
    EnderecoCreate,
    EnderecoFilters,
    EnderecoListResponse,
    EnderecoResponse,
    EnderecoUpdate,
)
from app.services.endereco import EnderecoService

router = APIRouter(prefix="/users/me/addresses", tags=["endereços"])


@router.post(
    "",
    response_model=EnderecoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra um endereço para o usuário atual",
)
async def criar_endereco(
    dados: EnderecoCreate,
    session: DatabaseSession,
    usuario_id: CurrentUserId,
) -> EnderecoResponse:
    endereco = await EnderecoService(session).criar(dados, usuario_id)
    return EnderecoResponse.model_validate(endereco)


@router.get(
    "",
    response_model=EnderecoListResponse,
    summary="Lista os endereços do usuário atual",
)
async def listar_enderecos(
    session: DatabaseSession,
    usuario_id: CurrentUserId,
    filtros: Annotated[EnderecoFilters, Query()],
) -> EnderecoListResponse:
    return await EnderecoService(session).listar(filtros, usuario_id)


@router.get(
    "/{endereco_id}",
    response_model=EnderecoResponse,
    summary="Consulta um endereço do usuário atual",
)
async def buscar_endereco(
    endereco_id: UUID,
    session: DatabaseSession,
    usuario_id: CurrentUserId,
) -> EnderecoResponse:
    endereco = await EnderecoService(session).buscar(endereco_id, usuario_id)
    return EnderecoResponse.model_validate(endereco)


@router.patch(
    "/{endereco_id}",
    response_model=EnderecoResponse,
    summary="Atualiza um endereço do usuário atual",
)
async def atualizar_endereco(
    endereco_id: UUID,
    dados: EnderecoUpdate,
    session: DatabaseSession,
    usuario_id: CurrentUserId,
) -> EnderecoResponse:
    endereco = await EnderecoService(session).atualizar(endereco_id, dados, usuario_id)
    return EnderecoResponse.model_validate(endereco)


@router.delete(
    "/{endereco_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui logicamente um endereço do usuário atual",
)
async def excluir_endereco(
    endereco_id: UUID,
    session: DatabaseSession,
    usuario_id: CurrentUserId,
) -> Response:
    await EnderecoService(session).excluir(endereco_id, usuario_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

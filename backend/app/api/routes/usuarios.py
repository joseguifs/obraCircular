from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser
from app.core.database import get_db_session
from app.core.errors import AuthorizationError
from app.models.enums import UsuarioStatus
from app.schemas.usuario import (
    UsuarioCreate,
    UsuarioListResponse,
    UsuarioRead,
    UsuarioUpdate,
)
from app.services.usuario import UsuarioService

router = APIRouter(prefix="/users", tags=["usuarios"])


def get_usuario_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UsuarioService:
    return UsuarioService(session)


ServicoDep = Annotated[UsuarioService, Depends(get_usuario_service)]


@router.post("", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
async def criar_usuario(dados: UsuarioCreate, servico: ServicoDep) -> UsuarioRead:
    usuario = await servico.criar(dados)
    return UsuarioRead.model_validate(usuario)


@router.get("", response_model=UsuarioListResponse)
async def listar_usuarios(
    servico: ServicoDep,
    _usuario_atual: CurrentUser,
    status_filtro: Annotated[UsuarioStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UsuarioListResponse:
    usuarios, total = await servico.listar(status_filtro=status_filtro, limit=limit, offset=offset)
    return UsuarioListResponse(
        items=[UsuarioRead.model_validate(usuario) for usuario in usuarios],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{usuario_id}", response_model=UsuarioRead)
async def obter_usuario(
    usuario_id: UUID,
    servico: ServicoDep,
    usuario_atual: CurrentUser,
) -> UsuarioRead:
    _validar_proprio_usuario(usuario_id, usuario_atual.id)
    usuario = await servico.obter(usuario_id)
    return UsuarioRead.model_validate(usuario)


@router.patch("/{usuario_id}", response_model=UsuarioRead)
async def atualizar_usuario(
    usuario_id: UUID,
    dados: UsuarioUpdate,
    servico: ServicoDep,
    usuario_atual: CurrentUser,
) -> UsuarioRead:
    _validar_proprio_usuario(usuario_id, usuario_atual.id)
    usuario = await servico.atualizar(usuario_id, dados)
    return UsuarioRead.model_validate(usuario)


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_usuario(
    usuario_id: UUID,
    servico: ServicoDep,
    usuario_atual: CurrentUser,
) -> None:
    _validar_proprio_usuario(usuario_id, usuario_atual.id)
    await servico.excluir(usuario_id)


def _validar_proprio_usuario(usuario_id: UUID, usuario_atual_id: UUID) -> None:
    if usuario_id != usuario_atual_id:
        raise AuthorizationError("Você não tem permissão para acessar este usuário.")

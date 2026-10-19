from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import CurrentAdmin, DatabaseSession
from app.schemas.admin import (
    AdminAnuncioFilters,
    AdminAnuncioListResponse,
    AdminResumoResponse,
    AdminUsuarioFilters,
    AdminUsuarioListResponse,
    AdminUsuarioResponse,
    AdminUsuarioStatusUpdate,
)
from app.services.admin import AdminService

router = APIRouter(prefix="/admin", tags=["administração"])


@router.get(
    "/summary",
    response_model=AdminResumoResponse,
    summary="Resumo de usuários, anúncios e categorias",
)
async def obter_resumo(session: DatabaseSession, _admin: CurrentAdmin) -> AdminResumoResponse:
    return await AdminService(session).resumo()


@router.get(
    "/users",
    response_model=AdminUsuarioListResponse,
    summary="Lista e filtra usuários",
)
async def listar_usuarios(
    session: DatabaseSession,
    _admin: CurrentAdmin,
    filtros: Annotated[AdminUsuarioFilters, Query()],
) -> AdminUsuarioListResponse:
    return await AdminService(session).listar_usuarios(filtros)


@router.patch(
    "/users/{usuario_id}/status",
    response_model=AdminUsuarioResponse,
    summary="Altera o status de um usuário",
)
async def alterar_status_usuario(
    usuario_id: UUID,
    dados: AdminUsuarioStatusUpdate,
    session: DatabaseSession,
    admin: CurrentAdmin,
) -> AdminUsuarioResponse:
    return await AdminService(session).alterar_status_usuario(usuario_id, dados.status, admin.id)


@router.put(
    "/users/{usuario_id}/admin",
    response_model=AdminUsuarioResponse,
    summary="Concede o perfil de administrador",
)
async def conceder_administrador(
    usuario_id: UUID,
    session: DatabaseSession,
    admin: CurrentAdmin,
) -> AdminUsuarioResponse:
    return await AdminService(session).conceder_administrador(usuario_id, admin.id)


@router.delete(
    "/users/{usuario_id}/admin",
    response_model=AdminUsuarioResponse,
    summary="Remove o perfil de administrador",
)
async def revogar_administrador(
    usuario_id: UUID,
    session: DatabaseSession,
    admin: CurrentAdmin,
) -> AdminUsuarioResponse:
    return await AdminService(session).revogar_administrador(usuario_id, admin.id)


@router.get(
    "/ads",
    response_model=AdminAnuncioListResponse,
    summary="Lista e filtra anúncios de todos os vendedores",
)
async def listar_anuncios(
    session: DatabaseSession,
    _admin: CurrentAdmin,
    filtros: Annotated[AdminAnuncioFilters, Query()],
) -> AdminAnuncioListResponse:
    return await AdminService(session).listar_anuncios(filtros)


@router.post(
    "/ads/{anuncio_id}/close",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Encerra um anúncio (moderação)",
)
async def encerrar_anuncio(
    anuncio_id: UUID,
    session: DatabaseSession,
    _admin: CurrentAdmin,
) -> Response:
    await AdminService(session).encerrar_anuncio(anuncio_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/ads/{anuncio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui logicamente um anúncio (moderação)",
)
async def excluir_anuncio(
    anuncio_id: UUID,
    session: DatabaseSession,
    _admin: CurrentAdmin,
) -> Response:
    await AdminService(session).excluir_anuncio(anuncio_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

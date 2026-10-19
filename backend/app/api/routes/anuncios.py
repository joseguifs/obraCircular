from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.anuncio import (
    AnuncioCreate,
    AnuncioFilters,
    AnuncioListResponse,
    AnuncioResponse,
    AnuncioUpdate,
)
from app.schemas.anuncio_imagem import AnuncioImagemListResponse
from app.schemas.anuncio_pergunta import (
    AnuncioPerguntaCreate,
    AnuncioPerguntaFilters,
    AnuncioPerguntaListResponse,
    AnuncioPerguntaResponse,
    AnuncioRespostaCreate,
)
from app.services.anuncio import AnuncioService
from app.services.anuncio_imagem import AnuncioImagemService
from app.services.anuncio_pergunta import AnuncioPerguntaService

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


@router.post(
    "/{anuncio_id}/images",
    response_model=AnuncioImagemListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adiciona imagens a um anúncio do vendedor",
)
async def adicionar_imagens(
    anuncio_id: UUID,
    session: DatabaseSession,
    vendedor: CurrentUser,
    files: Annotated[list[UploadFile], File(description="Imagens JPEG, PNG ou WebP")],
) -> AnuncioImagemListResponse:
    return await AnuncioImagemService(session).adicionar(anuncio_id, vendedor.id, files)


@router.get(
    "/{anuncio_id}/images",
    response_model=AnuncioImagemListResponse,
    summary="Lista as imagens de um anúncio",
)
async def listar_imagens(
    anuncio_id: UUID,
    session: DatabaseSession,
) -> AnuncioImagemListResponse:
    return await AnuncioImagemService(session).listar(anuncio_id)


@router.get(
    "/{anuncio_id}/questions",
    response_model=AnuncioPerguntaListResponse,
    summary="Lista as perguntas públicas de um anúncio",
)
async def listar_perguntas(
    anuncio_id: UUID,
    session: DatabaseSession,
    filtros: Annotated[AnuncioPerguntaFilters, Query()],
) -> AnuncioPerguntaListResponse:
    return await AnuncioPerguntaService(session).listar(anuncio_id, filtros)


@router.post(
    "/{anuncio_id}/questions",
    response_model=AnuncioPerguntaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Faz uma pergunta ao vendedor do anúncio",
)
async def criar_pergunta(
    anuncio_id: UUID,
    dados: AnuncioPerguntaCreate,
    session: DatabaseSession,
    usuario: CurrentUser,
) -> AnuncioPerguntaResponse:
    pergunta = await AnuncioPerguntaService(session).perguntar(anuncio_id, dados, usuario.id)
    return AnuncioPerguntaResponse.model_validate(pergunta)


@router.post(
    "/{anuncio_id}/questions/{pergunta_id}/answer",
    response_model=AnuncioPerguntaResponse,
    summary="Responde uma pergunta do anúncio (somente o vendedor)",
)
async def responder_pergunta(
    anuncio_id: UUID,
    pergunta_id: UUID,
    dados: AnuncioRespostaCreate,
    session: DatabaseSession,
    vendedor: CurrentUser,
) -> AnuncioPerguntaResponse:
    pergunta = await AnuncioPerguntaService(session).responder(
        anuncio_id, pergunta_id, dados, vendedor.id
    )
    return AnuncioPerguntaResponse.model_validate(pergunta)


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

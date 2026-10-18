from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.anuncio import Anuncio
from app.models.anuncio_pergunta import AnuncioPergunta
from app.models.enums import AnuncioStatus, UsuarioStatus
from app.repositories.anuncio import AnuncioRepository
from app.repositories.anuncio_pergunta import AnuncioPerguntaRepository
from app.schemas.anuncio_pergunta import (
    AnuncioPerguntaCreate,
    AnuncioPerguntaFilters,
    AnuncioPerguntaListResponse,
    AnuncioPerguntaResponse,
    AnuncioRespostaCreate,
)


class AnuncioPerguntaService:
    def __init__(
        self,
        session: AsyncSession,
        repository: AnuncioPerguntaRepository | None = None,
        anuncio_repository: AnuncioRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or AnuncioPerguntaRepository(session)
        self.anuncio_repository = anuncio_repository or AnuncioRepository(session)

    async def perguntar(
        self,
        anuncio_id: UUID,
        dados: AnuncioPerguntaCreate,
        autor_id: UUID,
    ) -> AnuncioPergunta:
        async with self.session.begin():
            anuncio = await self._buscar_anuncio(anuncio_id)

            if anuncio.vendedor_id == autor_id:
                raise AppError(
                    status_code=403,
                    detail="Você não pode fazer perguntas no seu próprio anúncio.",
                    code="QUESTION_OWN_AD",
                )
            if anuncio.status == AnuncioStatus.ENCERRADO:
                raise AppError(
                    status_code=400,
                    detail="Anúncios encerrados não recebem novas perguntas.",
                    code="AD_CLOSED",
                )
            await self._validar_usuario_ativo(autor_id)

            pergunta = AnuncioPergunta(
                anuncio_id=anuncio.id,
                autor_id=autor_id,
                pergunta=dados.pergunta,
            )
            return await self.repository.criar(pergunta)

    async def responder(
        self,
        anuncio_id: UUID,
        pergunta_id: UUID,
        dados: AnuncioRespostaCreate,
        vendedor_id: UUID,
    ) -> AnuncioPergunta:
        async with self.session.begin():
            anuncio = await self._buscar_anuncio(anuncio_id)

            if anuncio.vendedor_id != vendedor_id:
                raise AppError(
                    status_code=403,
                    detail="Somente o vendedor do anúncio pode responder perguntas.",
                    code="QUESTION_ANSWER_FORBIDDEN",
                )
            await self._validar_usuario_ativo(vendedor_id)

            # O bloqueio impede que duas respostas simultâneas sobrescrevam uma à outra.
            pergunta = await self.repository.buscar_por_id(
                pergunta_id,
                anuncio_id,
                bloquear=True,
            )
            if pergunta is None:
                raise AppError(
                    status_code=404,
                    detail="Pergunta não encontrada.",
                    code="QUESTION_NOT_FOUND",
                )
            if pergunta.resposta is not None:
                raise AppError(
                    status_code=409,
                    detail="Esta pergunta já foi respondida.",
                    code="QUESTION_ALREADY_ANSWERED",
                )

            pergunta.resposta = dados.resposta
            pergunta.respondido_em = datetime.now(UTC)
            await self.session.flush()
            await self.session.refresh(pergunta)
            return pergunta

    async def listar(
        self,
        anuncio_id: UUID,
        filtros: AnuncioPerguntaFilters,
    ) -> AnuncioPerguntaListResponse:
        await self._buscar_anuncio(anuncio_id)
        perguntas, total = await self.repository.listar(
            anuncio_id,
            offset=filtros.offset,
            limit=filtros.limit,
        )
        return AnuncioPerguntaListResponse(
            items=[AnuncioPerguntaResponse.model_validate(item) for item in perguntas],
            total=total,
            offset=filtros.offset,
            limit=filtros.limit,
        )

    async def _buscar_anuncio(self, anuncio_id: UUID) -> Anuncio:
        anuncio = await self.anuncio_repository.buscar_por_id(anuncio_id)
        if anuncio is None:
            raise AppError(
                status_code=404,
                detail="Anúncio não encontrado.",
                code="AD_NOT_FOUND",
            )
        return anuncio

    async def _validar_usuario_ativo(self, usuario_id: UUID) -> None:
        usuario = await self.anuncio_repository.buscar_usuario(usuario_id)
        if usuario is None or usuario.status != UsuarioStatus.ATIVO:
            raise AppError(
                status_code=403,
                detail="Sua conta precisa estar ativa para realizar esta ação.",
                code="USER_NOT_ACTIVE",
            )

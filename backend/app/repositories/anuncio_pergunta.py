from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anuncio import Anuncio
from app.models.anuncio_pergunta import AnuncioPergunta
from app.models.enums import AnuncioStatus
from app.schemas.anuncio_pergunta import TipoPerguntaUsuario


class AnuncioPerguntaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def criar(self, pergunta: AnuncioPergunta) -> AnuncioPergunta:
        self.session.add(pergunta)
        await self.session.flush()
        await self.session.refresh(pergunta)
        return pergunta

    async def buscar_por_id(
        self,
        pergunta_id: UUID,
        anuncio_id: UUID,
        *,
        bloquear: bool = False,
    ) -> AnuncioPergunta | None:
        query = select(AnuncioPergunta).where(
            AnuncioPergunta.id == pergunta_id,
            AnuncioPergunta.anuncio_id == anuncio_id,
        )
        if bloquear:
            query = query.with_for_update()
        return cast(AnuncioPergunta | None, await self.session.scalar(query))

    async def listar(
        self,
        anuncio_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[AnuncioPergunta], int]:
        resultado = await self.session.scalars(
            select(AnuncioPergunta)
            .where(AnuncioPergunta.anuncio_id == anuncio_id)
            .order_by(AnuncioPergunta.criado_em.desc(), AnuncioPergunta.id.desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self.session.scalar(
            select(func.count())
            .select_from(AnuncioPergunta)
            .where(AnuncioPergunta.anuncio_id == anuncio_id)
        )
        return list(resultado.all()), int(total or 0)

    async def listar_do_usuario(
        self,
        usuario_id: UUID,
        *,
        tipo: TipoPerguntaUsuario,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[AnuncioPergunta, Anuncio]], int]:
        """Perguntas feitas pelo usuário ou recebidas nos anúncios dele.

        Anúncios indisponíveis (excluídos ou encerrados) ficam de fora.
        """
        condicoes = [
            Anuncio.deletado_em.is_(None),
            Anuncio.status != AnuncioStatus.ENCERRADO,
            AnuncioPergunta.autor_id == usuario_id
            if tipo == TipoPerguntaUsuario.FEITAS
            else Anuncio.vendedor_id == usuario_id,
        ]
        resultado = await self.session.execute(
            select(AnuncioPergunta, Anuncio)
            .join(Anuncio, Anuncio.id == AnuncioPergunta.anuncio_id)
            .where(*condicoes)
            .order_by(AnuncioPergunta.criado_em.desc(), AnuncioPergunta.id.desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self.session.scalar(
            select(func.count())
            .select_from(AnuncioPergunta)
            .join(Anuncio, Anuncio.id == AnuncioPergunta.anuncio_id)
            .where(*condicoes)
        )
        linhas = [(pergunta, anuncio) for pergunta, anuncio in resultado.all()]
        return linhas, int(total or 0)

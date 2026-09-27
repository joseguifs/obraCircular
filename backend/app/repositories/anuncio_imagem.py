from collections.abc import Collection
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anuncio_imagem import AnuncioImagem


class AnuncioImagemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def proxima_ordem(self, anuncio_id: UUID) -> int:
        maior_ordem = await self.session.scalar(
            select(func.max(AnuncioImagem.ordem)).where(
                AnuncioImagem.anuncio_id == anuncio_id
            )
        )
        return int(maior_ordem) + 1 if maior_ordem is not None else 0

    async def listar(self, anuncio_id: UUID) -> list[AnuncioImagem]:
        resultado = await self.session.scalars(
            select(AnuncioImagem)
            .where(AnuncioImagem.anuncio_id == anuncio_id)
            .order_by(AnuncioImagem.ordem.asc())
        )
        return list(resultado.all())

    async def listar_capas(self, anuncio_ids: Collection[UUID]) -> dict[UUID, str]:
        if not anuncio_ids:
            return {}
        resultado = await self.session.execute(
            select(AnuncioImagem.anuncio_id, AnuncioImagem.chave_objeto).where(
                AnuncioImagem.anuncio_id.in_(anuncio_ids),
                AnuncioImagem.ordem == 0,
            )
        )
        return {
            anuncio_id: chave_objeto
            for anuncio_id, chave_objeto in resultado.tuples().all()
        }

    async def criar_varias(self, imagens: list[AnuncioImagem]) -> list[AnuncioImagem]:
        self.session.add_all(imagens)
        await self.session.flush()
        for imagem in imagens:
            await self.session.refresh(imagem)
        return imagens

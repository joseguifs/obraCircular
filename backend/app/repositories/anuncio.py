from typing import cast
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.anuncio import Anuncio
from app.models.categoria import Categoria
from app.models.endereco import Endereco
from app.models.usuario import Usuario
from app.schemas.anuncio import AnuncioFilters


class AnuncioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def buscar_por_id(self, anuncio_id: UUID, *, bloquear: bool = False) -> Anuncio | None:
        query = select(Anuncio).where(
            Anuncio.id == anuncio_id,
            Anuncio.deletado_em.is_(None),
        )
        if bloquear:
            query = query.with_for_update()
        return cast(Anuncio | None, await self.session.scalar(query))

    async def buscar_usuario(self, usuario_id: UUID) -> Usuario | None:
        usuario = await self.session.scalar(
            select(Usuario).where(Usuario.id == usuario_id, Usuario.deletado_em.is_(None))
        )
        return usuario

    async def buscar_categoria(self, categoria_id: UUID) -> Categoria | None:
        return await self.session.get(Categoria, categoria_id)

    async def buscar_endereco(self, endereco_id: UUID) -> Endereco | None:
        return await self.session.get(Endereco, endereco_id)

    async def criar(self, anuncio: Anuncio) -> Anuncio:
        self.session.add(anuncio)
        await self.session.flush()
        await self.session.refresh(anuncio)
        return anuncio

    async def listar(
        self,
        filtros: AnuncioFilters,
        *,
        vendedor_id: UUID | None = None,
    ) -> tuple[list[Anuncio], int]:
        condicoes: list[ColumnElement[bool]] = [Anuncio.deletado_em.is_(None)]

        if filtros.category_id is not None:
            condicoes.append(Anuncio.categoria_id == filtros.category_id)
        if filtros.status is not None:
            condicoes.append(Anuncio.status == filtros.status)
        if filtros.min_price is not None:
            condicoes.append(Anuncio.preco >= filtros.min_price)
        if filtros.max_price is not None:
            condicoes.append(Anuncio.preco <= filtros.max_price)
        if vendedor_id is not None:
            condicoes.append(Anuncio.vendedor_id == vendedor_id)
        if filtros.search is not None:
            termo = self._escapar_like(filtros.search)
            padrao = f"%{termo}%"
            condicoes.append(
                or_(
                    Anuncio.titulo.ilike(padrao, escape="\\"),
                    Anuncio.descricao.ilike(padrao, escape="\\"),
                )
            )

        consulta = (
            self._consulta_base()
            .where(*condicoes)
            .order_by(Anuncio.postado_em.desc(), Anuncio.id.desc())
            .offset(filtros.offset)
            .limit(filtros.limit)
        )
        consulta_total = select(func.count()).select_from(Anuncio).where(*condicoes)

        resultado = await self.session.scalars(consulta)
        total = await self.session.scalar(consulta_total)
        return list(resultado.all()), int(total or 0)

    @staticmethod
    def _consulta_base() -> Select[tuple[Anuncio]]:
        return select(Anuncio)

    @staticmethod
    def _escapar_like(valor: str) -> str:
        return valor.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

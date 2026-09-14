from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.categoria import Categoria
from app.schemas.categoria import CategoriaFilters


class CategoriaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def buscar_por_id(
        self,
        categoria_id: UUID,
        *,
        bloquear: bool = False,
    ) -> Categoria | None:
        query = select(Categoria).where(Categoria.id == categoria_id)
        if bloquear:
            query = query.with_for_update()
        return cast(Categoria | None, await self.session.scalar(query))

    async def buscar_por_nome(
        self,
        nome: str,
        *,
        excluir_id: UUID | None = None,
    ) -> Categoria | None:
        """Busca uma categoria pelo nome exato (o nome é único, conforme
        `docs/domain/categoria.md` e a `UniqueConstraint` do model)."""
        query = select(Categoria).where(Categoria.nome == nome)
        if excluir_id is not None:
            query = query.where(Categoria.id != excluir_id)
        return cast(Categoria | None, await self.session.scalar(query))

    async def criar(self, categoria: Categoria) -> Categoria:
        self.session.add(categoria)
        await self.session.flush()
        await self.session.refresh(categoria)
        return categoria

    async def listar(self, filtros: CategoriaFilters) -> tuple[list[Categoria], int]:
        condicoes = []
        if filtros.status is not None:
            condicoes.append(Categoria.status == filtros.status)

        consulta = (
            select(Categoria)
            .where(*condicoes)
            .order_by(Categoria.nome.asc())
            .offset(filtros.offset)
            .limit(filtros.limit)
        )
        consulta_total = select(func.count()).select_from(Categoria).where(*condicoes)

        resultado = await self.session.scalars(consulta)
        total = await self.session.scalar(consulta_total)
        return list(resultado.all()), int(total or 0)

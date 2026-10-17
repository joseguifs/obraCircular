from typing import Any, cast
from uuid import UUID

from sqlalchemy import ColumnElement, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models.administrador import Administrador
from app.models.anuncio import Anuncio
from app.models.categoria import Categoria
from app.models.usuario import Usuario
from app.schemas.admin import AdminAnuncioFilters, AdminUsuarioFilters


class AdministradorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def eh_administrador(self, usuario_id: UUID) -> bool:
        return await self.session.get(Administrador, usuario_id) is not None

    async def filtrar_administradores(self, usuario_ids: list[UUID]) -> set[UUID]:
        if not usuario_ids:
            return set()
        resultado = await self.session.scalars(
            select(Administrador.usuario_id).where(Administrador.usuario_id.in_(usuario_ids))
        )
        return set(resultado.all())

    async def adicionar(self, usuario_id: UUID, concedido_por_id: UUID) -> None:
        self.session.add(Administrador(usuario_id=usuario_id, concedido_por_id=concedido_por_id))
        await self.session.flush()

    async def remover(self, usuario_id: UUID) -> None:
        await self.session.execute(
            delete(Administrador).where(Administrador.usuario_id == usuario_id)
        )

    async def contar_administradores(self) -> int:
        total = await self.session.scalar(select(func.count()).select_from(Administrador))
        return int(total or 0)

    async def contar_por_status(
        self,
        coluna: InstrumentedAttribute[Any],
        *condicoes: ColumnElement[bool],
    ) -> dict[str, int]:
        resultado = await self.session.execute(
            select(coluna, func.count()).where(*condicoes).group_by(coluna)
        )
        return {str(status): int(total) for status, total in resultado.all()}

    async def buscar_usuario(self, usuario_id: UUID, *, bloquear: bool = False) -> Usuario | None:
        query = select(Usuario).where(Usuario.id == usuario_id, Usuario.deletado_em.is_(None))
        if bloquear:
            query = query.with_for_update()
        return cast(Usuario | None, await self.session.scalar(query))

    async def listar_usuarios(self, filtros: AdminUsuarioFilters) -> tuple[list[Usuario], int]:
        condicoes: list[ColumnElement[bool]] = []
        if not filtros.incluir_excluidos:
            condicoes.append(Usuario.deletado_em.is_(None))
        if filtros.status is not None:
            condicoes.append(Usuario.status == filtros.status)
        if filtros.search is not None:
            padrao = f"%{_escapar_like(filtros.search)}%"
            condicoes.append(
                or_(
                    Usuario.nome.ilike(padrao, escape="\\"),
                    Usuario.email.ilike(padrao, escape="\\"),
                )
            )

        consulta = (
            select(Usuario)
            .where(*condicoes)
            .order_by(Usuario.criado_em.desc(), Usuario.id.desc())
            .offset(filtros.offset)
            .limit(filtros.limit)
        )
        total = await self.session.scalar(
            select(func.count()).select_from(Usuario).where(*condicoes)
        )
        resultado = await self.session.scalars(consulta)
        return list(resultado.all()), int(total or 0)

    async def buscar_anuncio(self, anuncio_id: UUID, *, bloquear: bool = False) -> Anuncio | None:
        query = select(Anuncio).where(Anuncio.id == anuncio_id, Anuncio.deletado_em.is_(None))
        if bloquear:
            query = query.with_for_update()
        return cast(Anuncio | None, await self.session.scalar(query))

    async def listar_anuncios(
        self, filtros: AdminAnuncioFilters
    ) -> tuple[list[tuple[Anuncio, Usuario, Categoria]], int]:
        condicoes: list[ColumnElement[bool]] = []
        if not filtros.incluir_excluidos:
            condicoes.append(Anuncio.deletado_em.is_(None))
        if filtros.status is not None:
            condicoes.append(Anuncio.status == filtros.status)
        if filtros.category_id is not None:
            condicoes.append(Anuncio.categoria_id == filtros.category_id)
        if filtros.vendedor_id is not None:
            condicoes.append(Anuncio.vendedor_id == filtros.vendedor_id)
        if filtros.search is not None:
            padrao = f"%{_escapar_like(filtros.search)}%"
            condicoes.append(
                or_(
                    Anuncio.titulo.ilike(padrao, escape="\\"),
                    Usuario.nome.ilike(padrao, escape="\\"),
                    Usuario.email.ilike(padrao, escape="\\"),
                )
            )

        consulta = (
            select(Anuncio, Usuario, Categoria)
            .join(Usuario, Usuario.id == Anuncio.vendedor_id)
            .join(Categoria, Categoria.id == Anuncio.categoria_id)
            .where(*condicoes)
            .order_by(Anuncio.postado_em.desc(), Anuncio.id.desc())
            .offset(filtros.offset)
            .limit(filtros.limit)
        )
        consulta_total = (
            select(func.count())
            .select_from(Anuncio)
            .join(Usuario, Usuario.id == Anuncio.vendedor_id)
            .where(*condicoes)
        )
        resultado = await self.session.execute(consulta)
        total = await self.session.scalar(consulta_total)
        linhas = [(anuncio, usuario, categoria) for anuncio, usuario, categoria in resultado.all()]
        return linhas, int(total or 0)


def _escapar_like(valor: str) -> str:
    return valor.replace("\\", "\\\\").replace("%", "\%").replace("_", "\_")

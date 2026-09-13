from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.endereco import Endereco
from app.models.usuario import Usuario
from app.schemas.endereco import EnderecoFilters


class EnderecoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def buscar_por_id(
        self,
        endereco_id: UUID,
        usuario_id: UUID,
        *,
        bloquear: bool = False,
    ) -> Endereco | None:
        """Busca um endereço não excluído que pertença ao usuário informado.

        O filtro por `usuario_id` faz parte da consulta para que um endereço de
        outro usuário seja indistinguível de um inexistente (ambos viram 404).
        """
        query = select(Endereco).where(
            Endereco.id == endereco_id,
            Endereco.usuario_id == usuario_id,
            Endereco.deletado_em.is_(None),
        )
        if bloquear:
            query = query.with_for_update()
        return cast(Endereco | None, await self.session.scalar(query))

    async def buscar_usuario(self, usuario_id: UUID) -> Usuario | None:
        usuario = await self.session.scalar(
            select(Usuario).where(Usuario.id == usuario_id, Usuario.deletado_em.is_(None))
        )
        return usuario

    async def criar(self, endereco: Endereco) -> Endereco:
        self.session.add(endereco)
        await self.session.flush()
        await self.session.refresh(endereco)
        return endereco

    async def listar(
        self,
        usuario_id: UUID,
        filtros: EnderecoFilters,
    ) -> tuple[list[Endereco], int]:
        condicoes = (
            Endereco.usuario_id == usuario_id,
            Endereco.deletado_em.is_(None),
        )

        consulta = (
            select(Endereco)
            .where(*condicoes)
            .order_by(Endereco.criado_em.desc(), Endereco.id.desc())
            .offset(filtros.offset)
            .limit(filtros.limit)
        )
        consulta_total = select(func.count()).select_from(Endereco).where(*condicoes)

        resultado = await self.session.scalars(consulta)
        total = await self.session.scalar(consulta_total)
        return list(resultado.all()), int(total or 0)

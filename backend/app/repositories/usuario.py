from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UsuarioStatus
from app.models.usuario import Usuario


class UsuarioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obter_por_id(self, usuario_id: UUID) -> Usuario | None:
        """Retorna o usuário ativo (não excluído) com o id informado."""
        stmt = select(Usuario).where(
            Usuario.id == usuario_id,
            Usuario.deletado_em.is_(None),
        )
        usuario: Usuario | None = await self._session.scalar(stmt)
        return usuario

    async def obter_por_email(
        self, email: str, *, excluir_id: UUID | None = None
    ) -> Usuario | None:
        """Busca por e-mail (case-insensitive) considerando também excluídos.

        O índice único `uq_usuarios_email_normalizado` não é parcial: um
        e-mail usado por um usuário excluído continua reservado no banco.
        Por isso a checagem de unicidade aqui não filtra `deletado_em`.
        """
        stmt = select(Usuario).where(func.lower(Usuario.email) == email.lower())
        if excluir_id is not None:
            stmt = stmt.where(Usuario.id != excluir_id)
        usuario: Usuario | None = await self._session.scalar(stmt)
        return usuario

    async def listar(
        self,
        *,
        status_filtro: UsuarioStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Usuario], int]:
        """Lista usuários ativos (não excluídos), com paginação e total."""
        filtros: list[ColumnElement[bool]] = [Usuario.deletado_em.is_(None)]
        if status_filtro is not None:
            filtros.append(Usuario.status == status_filtro)

        total = await self._session.scalar(
            select(func.count()).select_from(Usuario).where(*filtros)
        )

        stmt = (
            select(Usuario)
            .where(*filtros)
            .order_by(Usuario.criado_em.desc())
            .limit(limit)
            .offset(offset)
        )
        resultado = await self._session.scalars(stmt)
        return list(resultado.all()), int(total or 0)

    def adicionar(self, usuario: Usuario) -> None:
        self._session.add(usuario)

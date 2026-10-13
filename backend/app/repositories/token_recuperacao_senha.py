from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token_recuperacao_senha import TokenRecuperacaoSenha


class TokenRecuperacaoSenhaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def adicionar(self, token: TokenRecuperacaoSenha) -> None:
        self._session.add(token)

    async def obter_por_hash(
        self, token_hash: str, *, bloquear: bool = False
    ) -> TokenRecuperacaoSenha | None:
        """Busca o token pelo hash; `bloquear` evita que dois pedidos usem o mesmo link."""
        stmt = select(TokenRecuperacaoSenha).where(TokenRecuperacaoSenha.token_hash == token_hash)
        if bloquear:
            stmt = stmt.with_for_update()
        token: TokenRecuperacaoSenha | None = await self._session.scalar(stmt)
        return token

    async def invalidar_pendentes(self, usuario_id: UUID, agora: datetime) -> None:
        """Marca como usados todos os tokens ainda não utilizados do usuário."""
        await self._session.execute(
            update(TokenRecuperacaoSenha)
            .where(
                TokenRecuperacaoSenha.usuario_id == usuario_id,
                TokenRecuperacaoSenha.usado_em.is_(None),
            )
            .values(usado_em=agora)
        )

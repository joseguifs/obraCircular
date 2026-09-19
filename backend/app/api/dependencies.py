from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.errors import AuthenticationError
from app.models.usuario import Usuario
from app.services.autenticacao import AutenticacaoService

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    session: DatabaseSession,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Usuario:
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise AuthenticationError("Token de acesso não informado.")
    usuario = await AutenticacaoService(session).obter_usuario_por_token(
        credenciais.credentials,
        tipo="access",
    )
    # A consulta de autenticação inicia uma transação implícita do SQLAlchemy.
    # O usuário é destacado antes do rollback para manter seus campos carregados e
    # liberar a mesma sessão para a transação explícita aberta pelo serviço da rota.
    session.expunge(usuario)
    await session.rollback()
    return usuario


CurrentUser = Annotated[Usuario, Depends(get_current_user)]

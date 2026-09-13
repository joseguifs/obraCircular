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
    return await AutenticacaoService(session).obter_usuario_por_token(
        credenciais.credentials,
        tipo="access",
    )


CurrentUser = Annotated[Usuario, Depends(get_current_user)]

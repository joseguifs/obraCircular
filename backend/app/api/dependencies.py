from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserId = Annotated[
    UUID,
    Header(
        alias="X-User-Id",
        description=(
            "Identificador temporário do usuário atual. Será substituído pelo usuário "
            "autenticado quando a autenticação for implementada."
        ),
    ),
]

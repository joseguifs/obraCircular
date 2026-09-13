from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import engine, get_db_session
from app.main import app
from app.models.enums import UsuarioStatus
from app.models.usuario import Usuario


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Sessão isolada em uma transação por teste, desfeita ao final (rollback)."""
    async with engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def _override_get_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def usuario_autenticado() -> Iterator[Usuario]:
    """Substitui a autenticação em testes focados somente no contrato da rota."""
    usuario = Usuario(
        id=uuid4(),
        nome="Usuário de Teste",
        email="usuario-rota@example.com",
        senha_hash="hash-nao-utilizado",
        telefone=None,
        status=UsuarioStatus.ATIVO,
    )

    async def _override_get_current_user() -> Usuario:
        return usuario

    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        yield usuario
    finally:
        app.dependency_overrides.pop(get_current_user, None)

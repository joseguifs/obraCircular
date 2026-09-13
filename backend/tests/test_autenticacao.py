import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import UsuarioStatus
from app.models.usuario import Usuario

USUARIO = {
    "nome": "João Autenticado",
    "email": "joao@example.com",
    "senha": "senha-segura-123",
}


async def _criar_usuario(client: AsyncClient, **sobrescritas: object) -> dict:
    resposta = await client.post("/api/v1/users", json={**USUARIO, **sobrescritas})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


async def _login(client: AsyncClient, **sobrescritas: object) -> dict:
    credenciais = {"email": USUARIO["email"], "senha": USUARIO["senha"], **sobrescritas}
    resposta = await client.post("/api/v1/auth/login", json=credenciais)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_login_emite_tokens_e_permite_consultar_usuario_atual(
    client: AsyncClient,
) -> None:
    usuario = await _criar_usuario(client)

    resposta_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "JOAO@EXAMPLE.COM", "senha": USUARIO["senha"]},
    )

    assert resposta_login.status_code == 200
    tokens = resposta_login.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] > 0
    assert tokens["access_token"] != tokens["refresh_token"]

    resposta_me = await client.get(
        "/api/v1/auth/me",
        headers=_bearer(tokens["access_token"]),
    )
    assert resposta_me.status_code == 200
    assert resposta_me.json()["id"] == usuario["id"]


async def test_login_com_senha_incorreta_retorna_401_generico(client: AsyncClient) -> None:
    await _criar_usuario(client)

    resposta = await client.post(
        "/api/v1/auth/login",
        json={"email": USUARIO["email"], "senha": "senha-incorreta"},
    )

    assert resposta.status_code == 401
    assert resposta.json() == {
        "detail": "E-mail ou senha inválidos.",
        "code": "AUTHENTICATION_REQUIRED",
    }
    assert resposta.headers["www-authenticate"] == "Bearer"


async def test_usuario_inativo_nao_pode_autenticar(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    usuario = await _criar_usuario(client)
    registro = await db_session.get(Usuario, UUID(usuario["id"]))
    assert registro is not None
    registro.status = UsuarioStatus.INATIVO
    await db_session.commit()

    resposta = await client.post(
        "/api/v1/auth/login",
        json={"email": USUARIO["email"], "senha": USUARIO["senha"]},
    )

    assert resposta.status_code == 401


async def test_rota_protegida_sem_token_retorna_401(client: AsyncClient) -> None:
    resposta = await client.get("/api/v1/auth/me")

    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


async def test_header_temporario_nao_autentica_usuario(client: AsyncClient) -> None:
    resposta = await client.get(
        "/api/v1/users/me/addresses",
        headers={"X-User-Id": "00000000-0000-0000-0000-000000000000"},
    )

    assert resposta.status_code == 401


async def test_refresh_emite_novo_par_de_tokens(client: AsyncClient) -> None:
    await _criar_usuario(client)
    tokens = await _login(client)

    resposta = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert resposta.status_code == 200
    novos_tokens = resposta.json()
    assert novos_tokens["access_token"] != tokens["access_token"]
    assert novos_tokens["refresh_token"] != tokens["refresh_token"]


async def test_access_token_nao_pode_ser_usado_para_refresh(client: AsyncClient) -> None:
    await _criar_usuario(client)
    tokens = await _login(client)

    resposta = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["access_token"]},
    )

    assert resposta.status_code == 401


async def test_usuario_nao_pode_acessar_registro_de_outro_usuario(
    client: AsyncClient,
) -> None:
    await _criar_usuario(client)
    outro = await _criar_usuario(client, email="outro@example.com")
    tokens = await _login(client)

    resposta = await client.get(
        f"/api/v1/users/{outro['id']}",
        headers=_bearer(tokens["access_token"]),
    )

    assert resposta.status_code == 403
    assert resposta.json()["code"] == "FORBIDDEN"


async def test_bloqueio_invalida_token_de_acesso_ja_emitido(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    usuario = await _criar_usuario(client)
    tokens = await _login(client)
    headers = _bearer(tokens["access_token"])

    registro = await db_session.get(Usuario, UUID(usuario["id"]))
    assert registro is not None
    registro.status = UsuarioStatus.BLOQUEADO
    await db_session.commit()

    resposta_me = await client.get("/api/v1/auth/me", headers=headers)
    assert resposta_me.status_code == 401


async def test_token_expirado_retorna_401(client: AsyncClient) -> None:
    usuario = await _criar_usuario(client)
    settings = get_settings()
    agora = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": usuario["id"],
            "type": "access",
            "iat": agora - timedelta(minutes=2),
            "exp": agora - timedelta(minutes=1),
            "jti": "token-expirado",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    resposta = await client.get("/api/v1/auth/me", headers=_bearer(token))

    assert resposta.status_code == 401


async def test_login_atualiza_hash_pbkdf2_antigo(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    salt = "0123456789abcdef0123456789abcdef"
    derivado = hashlib.pbkdf2_hmac(
        "sha256",
        USUARIO["senha"].encode(),
        salt.encode(),
        260_000,
    ).hex()
    usuario = Usuario(
        nome=USUARIO["nome"],
        email=USUARIO["email"],
        senha_hash=f"pbkdf2_sha256$260000${salt}${derivado}",
        telefone=None,
        status=UsuarioStatus.ATIVO,
    )
    db_session.add(usuario)
    await db_session.commit()

    resposta = await client.post(
        "/api/v1/auth/login",
        json={"email": USUARIO["email"], "senha": USUARIO["senha"]},
    )

    assert resposta.status_code == 200
    await db_session.refresh(usuario)
    assert usuario.senha_hash.startswith("pbkdf2_sha256$600000$")

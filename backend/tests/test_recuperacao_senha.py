import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_enviador_email
from app.main import app
from app.models.enums import UsuarioStatus
from app.models.token_recuperacao_senha import TokenRecuperacaoSenha
from app.models.usuario import Usuario

USUARIO = {
    "nome": "Maria Recuperação",
    "email": "maria@example.com",
    "senha": "senha-antiga-123",
}
NOVA_SENHA = "senha-nova-456"
MENSAGEM_GENERICA = (
    "Se o e-mail estiver cadastrado, você receberá um link para redefinir sua senha."
)


class EnviadorFalso:
    def __init__(self) -> None:
        self.mensagens: list[EmailMessage] = []

    def enviar(self, mensagem: EmailMessage) -> None:
        self.mensagens.append(mensagem)


@pytest.fixture
def enviador() -> Iterator[EnviadorFalso]:
    falso = EnviadorFalso()
    app.dependency_overrides[get_enviador_email] = lambda: falso
    try:
        yield falso
    finally:
        app.dependency_overrides.pop(get_enviador_email, None)


async def _criar_usuario(client: AsyncClient) -> dict[str, str]:
    resposta = await client.post("/api/v1/users", json=USUARIO)
    assert resposta.status_code == 201, resposta.text
    dados: dict[str, str] = resposta.json()
    return dados


async def _solicitar(client: AsyncClient, email: str = USUARIO["email"]) -> None:
    resposta = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert resposta.status_code == 202, resposta.text
    assert resposta.json() == {"detail": MENSAGEM_GENERICA}


def _token_do_email(mensagem: EmailMessage) -> str:
    corpo = mensagem.get_body(preferencelist=("plain",))
    assert corpo is not None
    link = re.search(r"https?://\S+", corpo.get_content())
    assert link is not None
    url = urlparse(link.group())
    assert url.path == "/redefinir-senha"
    return parse_qs(url.query)["token"][0]


async def _login(client: AsyncClient, senha: str) -> int:
    resposta = await client.post(
        "/api/v1/auth/login", json={"email": USUARIO["email"], "senha": senha}
    )
    return resposta.status_code


async def test_fluxo_completo_de_recuperacao_de_senha(
    client: AsyncClient, enviador: EnviadorFalso
) -> None:
    await _criar_usuario(client)

    await _solicitar(client, "MARIA@EXAMPLE.COM")

    assert len(enviador.mensagens) == 1
    mensagem = enviador.mensagens[0]
    assert mensagem["To"] == USUARIO["email"]
    assert "Redefinição de senha" in mensagem["Subject"]
    html = mensagem.get_body(preferencelist=("html",))
    assert html is not None and "Redefinir minha senha" in html.get_content()
    token = _token_do_email(mensagem)

    validacao = await client.post("/api/v1/auth/reset-password/validate", json={"token": token})
    assert validacao.status_code == 204

    redefinicao = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "nova_senha": NOVA_SENHA}
    )
    assert redefinicao.status_code == 204

    assert await _login(client, USUARIO["senha"]) == 401
    assert await _login(client, NOVA_SENHA) == 200


async def test_email_nao_cadastrado_recebe_mesma_resposta_sem_envio(
    client: AsyncClient, enviador: EnviadorFalso
) -> None:
    await _solicitar(client, "ninguem@example.com")

    assert enviador.mensagens == []


async def test_usuario_bloqueado_nao_recebe_email(
    client: AsyncClient, db_session: AsyncSession, enviador: EnviadorFalso
) -> None:
    usuario = await _criar_usuario(client)
    await db_session.execute(
        update(Usuario)
        .where(Usuario.id == UUID(usuario["id"]))
        .values(status=UsuarioStatus.BLOQUEADO)
    )

    await _solicitar(client)

    assert enviador.mensagens == []


async def test_token_so_pode_ser_usado_uma_vez(
    client: AsyncClient, enviador: EnviadorFalso
) -> None:
    await _criar_usuario(client)
    await _solicitar(client)
    token = _token_do_email(enviador.mensagens[0])
    dados = {"token": token, "nova_senha": NOVA_SENHA}

    primeira = await client.post("/api/v1/auth/reset-password", json=dados)
    segunda = await client.post(
        "/api/v1/auth/reset-password", json={**dados, "nova_senha": "outra-senha-789"}
    )

    assert primeira.status_code == 204
    assert segunda.status_code == 400
    assert segunda.json()["code"] == "PASSWORD_RESET_TOKEN_INVALID"
    assert await _login(client, NOVA_SENHA) == 200


async def test_novo_pedido_invalida_link_anterior(
    client: AsyncClient, enviador: EnviadorFalso
) -> None:
    await _criar_usuario(client)
    await _solicitar(client)
    await _solicitar(client)
    token_antigo, token_novo = (_token_do_email(m) for m in enviador.mensagens)

    antigo = await client.post(
        "/api/v1/auth/reset-password/validate", json={"token": token_antigo}
    )
    novo = await client.post("/api/v1/auth/reset-password/validate", json={"token": token_novo})

    assert antigo.status_code == 400
    assert novo.status_code == 204


async def test_token_expirado_e_rejeitado(
    client: AsyncClient, db_session: AsyncSession, enviador: EnviadorFalso
) -> None:
    await _criar_usuario(client)
    await _solicitar(client)
    token = _token_do_email(enviador.mensagens[0])
    await db_session.execute(
        update(TokenRecuperacaoSenha).values(expira_em=datetime.now(UTC) - timedelta(minutes=1))
    )

    resposta = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "nova_senha": NOVA_SENHA}
    )

    assert resposta.status_code == 400
    assert resposta.json() == {
        "detail": "Este link de redefinição é inválido ou expirou. Solicite um novo link.",
        "code": "PASSWORD_RESET_TOKEN_INVALID",
    }
    assert await _login(client, USUARIO["senha"]) == 200


async def test_token_desconhecido_e_rejeitado(client: AsyncClient) -> None:
    resposta = await client.post(
        "/api/v1/auth/reset-password/validate", json={"token": "token-inexistente"}
    )

    assert resposta.status_code == 400
    assert resposta.json()["code"] == "PASSWORD_RESET_TOKEN_INVALID"


async def test_banco_guarda_apenas_hash_do_token(
    client: AsyncClient, db_session: AsyncSession, enviador: EnviadorFalso
) -> None:
    await _criar_usuario(client)
    await _solicitar(client)
    token = _token_do_email(enviador.mensagens[0])

    hashes = (await db_session.scalars(select(TokenRecuperacaoSenha.token_hash))).all()

    assert len(hashes) == 1
    assert hashes[0] != token
    assert len(hashes[0]) == 64


async def test_nova_senha_curta_e_rejeitada(client: AsyncClient) -> None:
    resposta = await client.post(
        "/api/v1/auth/reset-password", json={"token": "qualquer", "nova_senha": "curta"}
    )

    assert resposta.status_code == 422

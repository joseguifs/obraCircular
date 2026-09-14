"""Hash e verificação de senhas.

Usa PBKDF2-HMAC-SHA256 (stdlib `hashlib`) para não introduzir dependências
externas de criptografia nesta etapa do projeto. O formato armazenado segue
`algoritmo$iteracoes$salt$hash`, todos em hexadecimal, permitindo evoluir o
algoritmo ou o número de iterações sem invalidar hashes já gravados.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import Settings

_ALGORITMO = "pbkdf2_sha256"
_ITERACOES = 600_000
_TAMANHO_SALT = 16
_HASH_SENHA_FALSA = f"{_ALGORITMO}${_ITERACOES}${'0' * 32}${'0' * 64}"

TipoToken = Literal["access", "refresh"]


@dataclass(frozen=True, slots=True)
class ParTokens:
    access_token: str
    refresh_token: str
    expires_in: int


def hash_senha(senha: str) -> str:
    """Gera o hash seguro de uma senha em texto puro."""
    salt = secrets.token_hex(_TAMANHO_SALT)
    derivado = _derivar(senha, salt, _ITERACOES)
    return f"{_ALGORITMO}${_ITERACOES}${salt}${derivado}"


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Confere se `senha` corresponde ao hash previamente armazenado."""
    partes = senha_hash.split("$")
    if len(partes) != 4:
        return False
    algoritmo, iteracoes_str, salt, derivado_esperado = partes
    if algoritmo != _ALGORITMO or not iteracoes_str.isdigit():
        return False
    derivado = _derivar(senha, salt, int(iteracoes_str))
    return hmac.compare_digest(derivado, derivado_esperado)


def verificar_senha_sem_revelar_usuario(
    senha: str,
    senha_hash: str | None,
) -> bool:
    """Executa o mesmo trabalho criptográfico mesmo quando o usuário não existe."""
    return verificar_senha(senha, senha_hash or _HASH_SENHA_FALSA)


def senha_precisa_atualizacao(senha_hash: str) -> bool:
    partes = senha_hash.split("$")
    if len(partes) != 4 or not partes[1].isdigit():
        return True
    return partes[0] != _ALGORITMO or int(partes[1]) < _ITERACOES


def criar_par_tokens(usuario_id: UUID, settings: Settings) -> ParTokens:
    minutos_acesso = settings.jwt_access_token_expire_minutes
    return ParTokens(
        access_token=_criar_token(
            usuario_id,
            tipo="access",
            validade=timedelta(minutes=minutos_acesso),
            settings=settings,
        ),
        refresh_token=_criar_token(
            usuario_id,
            tipo="refresh",
            validade=timedelta(days=settings.jwt_refresh_token_expire_days),
            settings=settings,
        ),
        expires_in=minutos_acesso * 60,
    )


def obter_usuario_id_do_token(
    token: str,
    *,
    tipo_esperado: TipoToken,
    settings: Settings,
) -> UUID | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "type", "iat", "exp", "jti", "iss", "aud"]},
        )
        if payload.get("type") != tipo_esperado:
            return None
        return UUID(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        return None


def _criar_token(
    usuario_id: UUID,
    *,
    tipo: TipoToken,
    validade: timedelta,
    settings: Settings,
) -> str:
    agora = datetime.now(UTC)
    payload = {
        "sub": str(usuario_id),
        "type": tipo,
        "iat": agora,
        "exp": agora + validade,
        "jti": str(uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def _derivar(senha: str, salt: str, iteracoes: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        senha.encode("utf-8"),
        salt.encode("utf-8"),
        iteracoes,
    ).hex()

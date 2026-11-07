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


def gerar_token_recuperacao_senha() -> tuple[str, str]:
    """Gera um token aleatório para o link de e-mail e o hash que vai para o banco."""
    token = secrets.token_urlsafe(32)
    return token, hash_token_recuperacao_senha(token)


def hash_token_recuperacao_senha(token: str) -> str:
    # O token já tem 256 bits de entropia; um SHA-256 simples basta para não guardá-lo
    # em texto puro, sem o custo do PBKDF2 usado nas senhas.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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


# --- PIN de confirmação de entrega -------------------------------------------------
#
# O PIN tem apenas 10^5 combinações, então qualquer hash sem segredo seria revertido
# por força bruta em milissegundos caso o banco vazasse. Por isso o hash é um
# HMAC-SHA256 com chave do servidor, vinculado ao id da entrega (o mesmo PIN em
# entregas diferentes gera hashes diferentes). O prefixo de versão permite trocar
# o esquema no futuro sem invalidar silenciosamente os PINs ativos.

PIN_ENTREGA_DIGITOS = 5
_PIN_HASH_VERSAO = "hmac_sha256_v1"
_PIN_HASH_CONTEXTO = b"obra-circular:entrega-pin:v1"


def gerar_pin_entrega() -> str:
    """Gera um PIN numérico de 5 dígitos com o CSPRNG do sistema operacional."""
    return f"{secrets.randbelow(10**PIN_ENTREGA_DIGITOS):0{PIN_ENTREGA_DIGITOS}d}"


def hash_pin_entrega(pin: str, entrega_id: UUID, settings: Settings) -> str:
    digest = hmac.new(
        _chave_pin_entrega(settings),
        f"{entrega_id}:{pin}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{_PIN_HASH_VERSAO}${digest}"


def verificar_pin_entrega(pin: str, entrega_id: UUID, pin_hash: str, settings: Settings) -> bool:
    esperado = hash_pin_entrega(pin, entrega_id, settings)
    return hmac.compare_digest(esperado.encode(), pin_hash.encode())


def _chave_pin_entrega(settings: Settings) -> bytes:
    segredo = settings.delivery_pin_secret_key or settings.jwt_secret_key
    # Deriva uma subchave própria para que o PIN nunca use o segredo do JWT diretamente.
    chave = segredo.get_secret_value().encode()
    return hmac.new(chave, _PIN_HASH_CONTEXTO, hashlib.sha256).digest()

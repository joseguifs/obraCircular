"""Hash e verificação de senhas.

Usa PBKDF2-HMAC-SHA256 (stdlib `hashlib`) para não introduzir dependências
externas de criptografia nesta etapa do projeto. O formato armazenado segue
`algoritmo$iteracoes$salt$hash`, todos em hexadecimal, permitindo evoluir o
algoritmo ou o número de iterações sem invalidar hashes já gravados.
"""

import hashlib
import hmac
import secrets

_ALGORITMO = "pbkdf2_sha256"
_ITERACOES = 260_000
_TAMANHO_SALT = 16


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


def _derivar(senha: str, salt: str, iteracoes: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        senha.encode("utf-8"),
        salt.encode("utf-8"),
        iteracoes,
    ).hex()

import base64
import hashlib
import hmac
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class TokenCipher:
    """Criptografia autenticada para tokens OAuth persistidos no banco."""

    def __init__(self, secret: str) -> None:
        if len(secret) < 32:
            raise ValueError("A chave de criptografia deve ter ao menos 32 caracteres.")
        self._key = hashlib.sha256(secret.encode("utf-8")).digest()

    def encrypt(self, value: str) -> str:
        nonce = secrets.token_bytes(12)
        encrypted = AESGCM(self._key).encrypt(nonce, value.encode("utf-8"), None)
        return base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")

    def decrypt(self, value: str) -> str:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
        return AESGCM(self._key).decrypt(raw[:12], raw[12:], None).decode("utf-8")


def validar_assinatura_webhook(
    *,
    x_signature: str,
    x_request_id: str,
    data_id: str,
    secret: str,
) -> bool:
    """Valida a assinatura HMAC-SHA256 documentada pelo Mercado Pago."""
    partes = {}
    for item in x_signature.split(","):
        chave, separador, valor = item.strip().partition("=")
        if separador:
            partes[chave] = valor
    timestamp = partes.get("ts")
    assinatura = partes.get("v1")
    if not timestamp or not assinatura or not x_request_id or not data_id:
        return False

    # Orders atualmente assina o identificador preservando a capitalizacao
    # recebida na query string. Outros produtos/documentos do Mercado Pago
    # normalizam identificadores alfanumericos para minusculas, portanto
    # mantemos compatibilidade com ambos os manifestos. Em qualquer caso a
    # assinatura ainda precisa ser um HMAC valido gerado com o segredo.
    identificadores = (data_id, data_id.lower())
    for identificador in dict.fromkeys(identificadores):
        manifesto = f"id:{identificador};request-id:{x_request_id};ts:{timestamp};"
        esperada = hmac.new(
            secret.encode("utf-8"), manifesto.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(esperada, assinatura):
            return True
    return False


def gerar_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def hash_state(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()

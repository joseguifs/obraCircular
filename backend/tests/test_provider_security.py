import hashlib
import hmac

from app.core.provider_security import TokenCipher, gerar_pkce, validar_assinatura_webhook


def test_token_cipher_round_trip_e_nao_expoe_segredo() -> None:
    cipher = TokenCipher("uma-chave-de-teste-com-mais-de-trinta-e-dois-caracteres")
    token = "APP_USR-token-muito-sensivel"

    criptografado = cipher.encrypt(token)

    assert token not in criptografado
    assert cipher.decrypt(criptografado) == token


def test_assinatura_webhook_valida_manifesto_oficial() -> None:
    secret = "segredo-webhook"
    manifesto = "id:123456;request-id:req-abc;ts:1704908010;"
    assinatura = hmac.new(secret.encode(), manifesto.encode(), hashlib.sha256).hexdigest()

    assert validar_assinatura_webhook(
        x_signature=f"ts=1704908010,v1={assinatura}",
        x_request_id="req-abc",
        data_id="123456",
        secret=secret,
    )
    assert not validar_assinatura_webhook(
        x_signature="ts=1704908010,v1=invalida",
        x_request_id="req-abc",
        data_id="123456",
        secret=secret,
    )


def test_assinatura_webhook_preserva_caixa_do_id_de_order() -> None:
    secret = "segredo-webhook"
    order_id = "ORDTST01M5417PHSM35YJ1HDKJQS99N2"
    manifesto = f"id:{order_id};request-id:req-order;ts:1704908010;"
    assinatura = hmac.new(secret.encode(), manifesto.encode(), hashlib.sha256).hexdigest()

    assert validar_assinatura_webhook(
        x_signature=f"ts=1704908010,v1={assinatura}",
        x_request_id="req-order",
        data_id=order_id,
        secret=secret,
    )


def test_assinatura_webhook_aceita_id_alfanumerico_normalizado() -> None:
    secret = "segredo-webhook"
    order_id = "ORDTST01M5417PHSM35YJ1HDKJQS99N2"
    manifesto = f"id:{order_id.lower()};request-id:req-order;ts:1704908010;"
    assinatura = hmac.new(secret.encode(), manifesto.encode(), hashlib.sha256).hexdigest()

    assert validar_assinatura_webhook(
        x_signature=f"ts=1704908010,v1={assinatura}",
        x_request_id="req-order",
        data_id=order_id,
        secret=secret,
    )


def test_pkce_gera_verifier_e_challenge_s256() -> None:
    verifier, challenge = gerar_pkce()

    assert 43 <= len(verifier) <= 128
    assert challenge
    assert verifier != challenge

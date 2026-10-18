from typing import Any

import httpx
import pytest

from app.integrations.mercado_pago import MercadoPagoGateway


@pytest.mark.parametrize(("test_token", "valor_enviado"), [(True, "true"), (False, "false")])
async def test_troca_oauth_informa_ambiente_do_token(
    monkeypatch: pytest.MonkeyPatch,
    test_token: bool,
    valor_enviado: str,
) -> None:
    payload_enviado: dict[str, Any] = {}

    async def request(
        _self: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> httpx.Response:
        assert method == "POST"
        assert url == "https://api.mercadopago.com/oauth/token"
        assert headers["Accept"] == "application/json"
        payload_enviado.update(json)
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "user_id": 123,
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "request", request)

    await MercadoPagoGateway("https://api.mercadopago.com").trocar_codigo_oauth(
        client_id="app-id",
        client_secret="client-secret",
        code="authorization-code",
        redirect_uri="https://example.test/oauth/callback",
        code_verifier="code-verifier",
        test_token=test_token,
    )

    assert payload_enviado["test_token"] == valor_enviado

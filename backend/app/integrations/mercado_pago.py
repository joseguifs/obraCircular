import asyncio
from dataclasses import dataclass
from typing import Any, cast

import httpx
import mercadopago  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class MercadoPagoResponse:
    data: dict[str, Any]


class MercadoPagoIntegrationError(Exception):
    def __init__(
        self, message: str, *, status_code: int | None = None, payload: Any = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class MercadoPagoGateway:
    def __init__(self, api_url: str, *, timeout: float = 15.0) -> None:
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

    async def trocar_codigo_oauth(
        self,
        *,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        code_verifier: str,
        test_token: bool = False,
    ) -> MercadoPagoResponse:
        return await self._request(
            "POST",
            "/oauth/token",
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
                "test_token": "true" if test_token else "false",
            },
        )

    async def renovar_token(
        self, *, client_id: str, client_secret: str, refresh_token: str
    ) -> MercadoPagoResponse:
        return await self._request(
            "POST",
            "/oauth/token",
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )

    async def criar_preferencia(
        self, *, access_token: str, payload: dict[str, Any]
    ) -> MercadoPagoResponse:
        def executar() -> dict[str, Any]:
            sdk = mercadopago.SDK(access_token)
            return cast(dict[str, Any], sdk.preference().create(payload))

        try:
            resultado = await asyncio.to_thread(executar)
        except Exception as exc:
            raise MercadoPagoIntegrationError("Falha de comunicação com o Mercado Pago.") from exc
        return self._resposta_sdk(resultado)

    async def obter_preferencia(
        self, *, access_token: str, preferencia_id: str
    ) -> MercadoPagoResponse:
        def executar() -> dict[str, Any]:
            sdk = mercadopago.SDK(access_token)
            return cast(dict[str, Any], sdk.preference().get(preferencia_id))

        try:
            resultado = await asyncio.to_thread(executar)
        except Exception as exc:
            raise MercadoPagoIntegrationError("Falha de comunicação com o Mercado Pago.") from exc
        return self._resposta_sdk(resultado)

    async def criar_order(
        self,
        *,
        access_token: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> MercadoPagoResponse:
        def executar() -> dict[str, Any]:
            sdk = mercadopago.SDK(access_token)
            opcoes = mercadopago.config.RequestOptions()
            opcoes.custom_headers = {"x-idempotency-key": idempotency_key}
            return cast(dict[str, Any], sdk.order().create(payload, opcoes))

        try:
            resultado = await asyncio.to_thread(executar)
        except Exception as exc:
            raise MercadoPagoIntegrationError("Falha de comunicação com o Mercado Pago.") from exc
        return self._resposta_sdk(resultado)

    async def obter_order(self, *, access_token: str, order_id: str) -> MercadoPagoResponse:
        def executar() -> dict[str, Any]:
            return cast(dict[str, Any], mercadopago.SDK(access_token).order().get(order_id))

        try:
            resultado = await asyncio.to_thread(executar)
        except Exception as exc:
            raise MercadoPagoIntegrationError("Falha de comunicação com o Mercado Pago.") from exc
        return self._resposta_sdk(resultado)

    async def obter_pagamento(
        self, *, access_token: str, pagamento_externo_id: str
    ) -> MercadoPagoResponse:
        return await self._request(
            "GET", f"/v1/payments/{pagamento_externo_id}", access_token=access_token
        )

    async def reembolsar_pagamento(
        self,
        *,
        access_token: str,
        pagamento_externo_id: str,
        idempotency_key: str,
    ) -> MercadoPagoResponse:
        return await self._request(
            "POST",
            f"/v1/payments/{pagamento_externo_id}/refunds",
            access_token=access_token,
            headers={"X-Idempotency-Key": idempotency_key},
            json={},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        access_token: str | None = None,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> MercadoPagoResponse:
        request_headers = {"Accept": "application/json", **(headers or {})}
        if access_token:
            request_headers["Authorization"] = f"Bearer {access_token}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method,
                    f"{self.api_url}{path}",
                    headers=request_headers,
                    json=json,
                )
        except httpx.RequestError as exc:
            raise MercadoPagoIntegrationError("Falha de comunicação com o Mercado Pago.") from exc

        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.is_error:
            raise MercadoPagoIntegrationError(
                "O Mercado Pago recusou a operação.",
                status_code=response.status_code,
                payload=payload,
            )
        if not isinstance(payload, dict):
            raise MercadoPagoIntegrationError("Resposta inválida do Mercado Pago.")
        return MercadoPagoResponse(data=payload)

    @staticmethod
    def _resposta_sdk(resultado: object) -> MercadoPagoResponse:
        if not isinstance(resultado, dict):
            raise MercadoPagoIntegrationError("Resposta inválida do Mercado Pago.")
        status = resultado.get("status")
        payload = resultado.get("response")
        if not isinstance(payload, dict):
            raise MercadoPagoIntegrationError("Resposta inválida do Mercado Pago.")
        if isinstance(status, int) and status >= 400:
            raise MercadoPagoIntegrationError(
                "O Mercado Pago recusou a operação.",
                status_code=status,
                payload=payload,
            )
        return MercadoPagoResponse(data=payload)

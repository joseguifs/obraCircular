import base64
import json
import re
from typing import Any
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.mercado_pago import MercadoPagoIntegrationError
from app.services.credencial_pagamento import token_marketplace


def codigo_erro_provedor(payload: Any) -> str | None:
    """Extrai apenas o codigo tecnico, sem expor mensagens, chaves ou dados bancarios."""
    if not isinstance(payload, dict):
        return None
    for campo in ("code", "error"):
        codigo = payload.get(campo)
        if isinstance(codigo, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", codigo):
            return codigo
    return None


class PayoutsGateway:
    """Contrato Pix/BRL publicado em /docs/payouts/integration-configuration/money-transfers.

    Aprovacao HTTP e status approved sao intermediarios; consultar a transacao.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validar_configuracao(self, *, somente_consulta: bool = False) -> None:
        token_marketplace(self.settings)
        if not self.settings.mp_payouts_enabled and not somente_consulta:
            raise AppError(
                status_code=503,
                detail="A execução de repasses não está habilitada.",
                code="PAYOUTS_DISABLED",
            )
        url = urlsplit(self.settings.mp_payouts_notification_url or "")
        if (
            url.scheme != "https"
            or not url.hostname
            or url.hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
        ):
            raise AppError(
                status_code=503,
                detail="Configure a URL HTTPS dos repasses.",
                code="PAYOUTS_NOTIFICATION_URL_INVALID",
            )
        if self.settings.mp_payouts_test_mode == self.settings.mp_live_mode:
            raise AppError(
                status_code=503,
                detail="Os ambientes de cobrança e repasse divergem.",
                code="PAYOUTS_MODE_MISMATCH",
            )
        if not self.settings.mp_payouts_test_mode and not somente_consulta:
            self._chave()

    def _chave(self) -> Ed25519PrivateKey:
        path = self.settings.mp_payouts_private_key_path
        try:
            key = (
                serialization.load_pem_private_key(path.read_bytes(), password=None)
                if path
                else None
            )
        except (OSError, ValueError) as exc:
            raise AppError(
                status_code=503,
                detail="Chave de assinatura dos repasses inválida.",
                code="PAYOUTS_SIGNATURE_KEY_INVALID",
            ) from exc
        if not isinstance(key, Ed25519PrivateKey):
            raise AppError(
                status_code=503,
                detail="Configure uma chave Ed25519 para os repasses.",
                code="PAYOUTS_SIGNATURE_KEY_INVALID",
            )
        return key

    async def criar(self, corpo: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        self.validar_configuracao()
        # Serializa uma unica vez: os bytes assinados sao os mesmos enviados.
        serializado = json.dumps(corpo, separators=(",", ":"), ensure_ascii=False).encode()
        headers = {
            "X-Idempotency-Key": idempotency_key,
            "X-test-token": "true" if self.settings.mp_payouts_test_mode else "false",
            "X-enforce-signature": "false" if self.settings.mp_payouts_test_mode else "true",
            "Content-Type": "application/json",
        }
        if not self.settings.mp_payouts_test_mode:
            headers["X-signature"] = base64.b64encode(self._chave().sign(serializado)).decode()
        return await self._request("POST", "/v1/payouts", headers=headers, content=serializado)

    async def consultar(self, payout_id: str) -> dict[str, Any]:
        self.validar_configuracao(somente_consulta=True)
        return await self._request("GET", f"/v1/payouts/{payout_id}/transactions?limit=10&offset=0")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.request(
                    method,
                    self.settings.mercado_pago_api_url + path,
                    headers={
                        "Authorization": "Bearer " + token_marketplace(self.settings),
                        "Accept": "application/json",
                        "X-test-token": "true" if self.settings.mp_payouts_test_mode else "false",
                        **(headers or {}),
                    },
                    content=content,
                )
            if response.is_error:
                try:
                    codigo = codigo_erro_provedor(response.json())
                except ValueError:
                    codigo = None
                raise MercadoPagoIntegrationError(
                    "Provedor não confirmou o repasse.",
                    status_code=response.status_code,
                    payload={"code": codigo} if codigo else None,
                )
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("invalid response")
            return result
        except (httpx.RequestError, ValueError) as exc:
            raise MercadoPagoIntegrationError(
                "Não foi possível confirmar o estado do repasse."
            ) from exc

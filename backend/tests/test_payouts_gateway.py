import base64
import json
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.mercado_pago import MercadoPagoIntegrationError
from app.integrations.payouts import PayoutsGateway
from app.schemas.repasse import DestinoRepasseCreate
from tests.test_repasse_posterior import configuracao


@pytest.mark.parametrize(
    "environment,test_mode,live_mode",
    [
        ("production", True, False),
        ("staging", True, False),
        ("local", False, False),
        ("local", True, True),
    ],
)
def test_dispensa_de_prazo_recusa_ambiente_incompativel(
    environment: str, test_mode: bool, live_mode: bool
) -> None:
    dados = configuracao().model_dump()
    dados.update(
        environment=environment,
        jwt_secret_key="chave-jwt-exclusiva-de-teste-com-mais-de-32-caracteres",
        mp_payouts_test_skip_wait=True,
        mp_payouts_test_mode=test_mode,
        mp_live_mode=live_mode,
    )
    with pytest.raises(ValidationError, match="MP_PAYOUTS_TEST_SKIP_WAIT"):
        Settings.model_validate(dados)


async def test_assina_exatamente_os_bytes_enviados_em_producao(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    chave = Ed25519PrivateKey.generate()
    path = tmp_path / "assinatura.pem"
    path.write_bytes(
        chave.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    settings = configuracao()
    settings.mp_live_mode = True
    settings.mp_payouts_test_mode = False
    settings.mp_payouts_private_key_path = path
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        chave.public_key().verify(base64.b64decode(request.headers["X-signature"]), request.content)
        assert request.headers["X-enforce-signature"] == "true"
        assert request.headers["X-test-token"] == "false"
        assert request.headers["X-Idempotency-Key"] == "chave-persistida"
        return httpx.Response(201, json={"id": "payout-1"})

    client_original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_original(**kwargs, transport=httpx.MockTransport(handler)),
    )
    result = await PayoutsGateway(settings).criar(
        {"descricao": "Teste de assinatura"}, "chave-persistida"
    )
    assert result["id"] == "payout-1"
    assert len(chamadas) == 1


async def test_modo_teste_envia_header_explicito_sem_chave_privada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-test-token"] == "true"
        assert request.headers["X-enforce-signature"] == "false"
        assert "X-signature" not in request.headers
        return httpx.Response(201, json={"id": "payout-1"})

    client_original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_original(**kwargs, transport=httpx.MockTransport(handler)),
    )
    await PayoutsGateway(configuracao()).criar({"transactions": []}, "chave")


@pytest.mark.parametrize(
    "payload,codigo",
    [
        (
            {"code": "PA_UNAUTHORIZED_RESULT_FROM_POLICIES", "message": "dados sigilosos"},
            "PA_UNAUTHORIZED_RESULT_FROM_POLICIES",
        ),
        ({"error": "forbidden", "message": "dados sigilosos"}, "forbidden"),
        ({"code": "usuario@example.com", "message": "dados sigilosos"}, None),
        ({"code": {"secret": "dados sigilosos"}}, None),
    ],
)
async def test_recusa_http_preserva_codigo_tecnico_sem_payload_sensivel(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, object], codigo: str | None
) -> None:
    client_original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_original(
            **kwargs, transport=httpx.MockTransport(lambda _: httpx.Response(403, json=payload))
        ),
    )
    with pytest.raises(MercadoPagoIntegrationError) as erro:
        await PayoutsGateway(configuracao()).criar({"transactions": []}, "chave-persistida")
    assert erro.value.status_code == 403
    assert erro.value.payload == ({"code": codigo} if codigo else None)
    assert "dados sigilosos" not in str(erro.value)


async def test_conta_por_email_envia_header_de_teste_e_payload_sem_pix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        assert request.headers["X-test-token"] == "true"
        assert request.headers["X-enforce-signature"] == "false"
        assert request.headers["X-Idempotency-Key"] == "instrucao-congelada"
        assert "X-signature" not in request.headers
        transacao = json.loads(request.content)["transactions"][0]
        assert transacao["type"] == "account" and "pix" not in transacao
        assert transacao["account"] == {"email": "destino@testuser.com"}
        return httpx.Response(202, json={"id": "payout-teste"})

    client_original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_original(**kwargs, transport=httpx.MockTransport(handler)),
    )
    result = await PayoutsGateway(configuracao()).criar(
        {
            "transactions": [
                {
                    "type": "account",
                    "account": {"email": "destino@testuser.com"},
                    "amount": {"currency": "BRL", "value": 16},
                }
            ]
        },
        "instrucao-congelada",
    )
    assert result["id"] == "payout-teste" and len(chamadas) == 1


def test_email_real_nao_e_aceito_como_conta_de_teste() -> None:
    with pytest.raises(ValidationError, match="@testuser.com"):
        DestinoRepasseCreate(
            tipo_chave="CONTA_MP_TESTE",
            chave="pessoa@gmail.com",
            titularidade_conferida=True,
        )


@pytest.mark.parametrize("problema", ["desabilitado", "url_local", "sem_assinatura", "ambiente"])
def test_configuracao_invalida_impede_transferencia(problema: str) -> None:
    settings = configuracao()
    if problema == "desabilitado":
        settings.mp_payouts_enabled = False
    elif problema == "url_local":
        settings.mp_payouts_notification_url = "https://localhost/webhook"
    elif problema == "sem_assinatura":
        settings.mp_live_mode = True
        settings.mp_payouts_test_mode = False
    else:
        settings.mp_payouts_test_mode = False
    with pytest.raises(AppError):
        PayoutsGateway(settings).validar_configuracao()

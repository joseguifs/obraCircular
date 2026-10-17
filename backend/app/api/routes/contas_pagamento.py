from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from app.api.dependencies import CurrentUser, DatabaseSession
from app.core.config import get_settings
from app.schemas.conta_pagamento import ConexaoMercadoPagoResponse, ContaPagamentoResponse
from app.services.conta_pagamento import ContaPagamentoService

account_router = APIRouter(prefix="/payment-accounts/mercado-pago", tags=["pagamentos"])
integration_router = APIRouter(prefix="/integrations/mercado-pago", tags=["pagamentos"])


@account_router.post("/connect", response_model=ConexaoMercadoPagoResponse)
async def conectar_mercado_pago(
    session: DatabaseSession, usuario: CurrentUser
) -> ConexaoMercadoPagoResponse:
    return await ContaPagamentoService(session).iniciar_conexao(usuario.id)


@account_router.get("", response_model=ContaPagamentoResponse)
async def consultar_conta_mercado_pago(
    session: DatabaseSession, usuario: CurrentUser
) -> ContaPagamentoResponse:
    return await ContaPagamentoService(session).obter_status(usuario.id)


@integration_router.get("/oauth/callback", response_class=RedirectResponse)
async def callback_mercado_pago(
    session: DatabaseSession,
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
) -> RedirectResponse:
    await ContaPagamentoService(session).concluir_conexao(code=code, state=state)
    return RedirectResponse(get_settings().mp_oauth_success_url, status_code=303)


@integration_router.get("/checkout/return", response_class=RedirectResponse)
async def retorno_checkout_mercado_pago(
    request: Request,
    result: Annotated[str, Query(pattern="^(success|pending|failure)$")],
) -> RedirectResponse:
    settings = get_settings()
    destinos = {
        "success": settings.mp_checkout_success_url,
        "pending": settings.mp_checkout_pending_url,
        "failure": settings.mp_checkout_failure_url,
    }
    destino = urlsplit(destinos[result])
    parametros = dict(parse_qsl(destino.query, keep_blank_values=True))
    parametros.update(
        {
            chave: valor
            for chave, valor in request.query_params.items()
            if chave != "result"
        }
    )
    url = urlunsplit(
        (destino.scheme, destino.netloc, destino.path, urlencode(parametros), destino.fragment)
    )
    return RedirectResponse(url, status_code=303)

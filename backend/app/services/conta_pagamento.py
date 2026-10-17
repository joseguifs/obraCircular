import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.provider_security import TokenCipher, gerar_pkce, hash_state
from app.integrations.mercado_pago import MercadoPagoGateway, MercadoPagoIntegrationError
from app.models.autorizacao_oauth import AutorizacaoOAuth
from app.models.conta_pagamento import ContaPagamento
from app.models.enums import ContaPagamentoStatus, ProvedorPagamento
from app.schemas.conta_pagamento import ConexaoMercadoPagoResponse, ContaPagamentoResponse

_OAUTH_TTL_MINUTES = 10


class ContaPagamentoService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        gateway: MercadoPagoGateway | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.gateway = gateway or MercadoPagoGateway(self.settings.mercado_pago_api_url)

    async def iniciar_conexao(self, usuario_id: UUID) -> ConexaoMercadoPagoResponse:
        client_id, _, redirect_uri, cipher = self._configuracao()
        state = secrets.token_urlsafe(32)
        verifier, challenge = gerar_pkce()
        agora = datetime.now(UTC)
        autorizacao = AutorizacaoOAuth(
            usuario_id=usuario_id,
            state_hash=hash_state(state),
            code_verifier_criptografado=cipher.encrypt(verifier),
            expira_em=agora + timedelta(minutes=_OAUTH_TTL_MINUTES),
            utilizado_em=None,
        )
        async with self.session.begin():
            self.session.add(autorizacao)
            await self.session.flush()

        query = urlencode(
            {
                "client_id": client_id,
                "response_type": "code",
                "platform_id": "mp",
                "state": state,
                "redirect_uri": redirect_uri,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return ConexaoMercadoPagoResponse(
            authorization_url=f"{self.settings.mercado_pago_auth_url}?{query}",
            expires_in=_OAUTH_TTL_MINUTES * 60,
        )

    async def concluir_conexao(self, *, code: str, state: str) -> None:
        client_id, client_secret, redirect_uri, cipher = self._configuracao()
        agora = datetime.now(UTC)
        async with self.session.begin():
            autorizacao = await self.session.scalar(
                select(AutorizacaoOAuth)
                .where(AutorizacaoOAuth.state_hash == hash_state(state))
                .with_for_update()
            )
            if (
                autorizacao is None
                or autorizacao.utilizado_em is not None
                or autorizacao.expira_em <= agora
            ):
                raise AppError(
                    status_code=400,
                    detail="A autorização do Mercado Pago expirou ou já foi utilizada.",
                    code="MP_OAUTH_STATE_INVALID",
                )
            autorizacao.utilizado_em = agora
            usuario_id = autorizacao.usuario_id
            verifier = cipher.decrypt(autorizacao.code_verifier_criptografado)

        try:
            resposta = await self.gateway.trocar_codigo_oauth(
                client_id=client_id,
                client_secret=client_secret,
                code=code,
                redirect_uri=redirect_uri,
                code_verifier=verifier,
            )
        except MercadoPagoIntegrationError as exc:
            raise AppError(
                status_code=502,
                detail="Não foi possível concluir a conexão com o Mercado Pago.",
                code="MP_OAUTH_EXCHANGE_FAILED",
            ) from exc

        access_token = self._campo_obrigatorio(resposta.data, "access_token")
        refresh_token = self._campo_obrigatorio(resposta.data, "refresh_token")
        conta_externa_id = str(self._campo_obrigatorio(resposta.data, "user_id"))
        expires_in = int(resposta.data.get("expires_in", 15_552_000))

        async with self.session.begin():
            conta = await self.session.scalar(
                select(ContaPagamento)
                .where(
                    ContaPagamento.usuario_id == usuario_id,
                    ContaPagamento.provedor == ProvedorPagamento.MERCADO_PAGO,
                )
                .with_for_update()
            )
            if conta is None:
                conta = ContaPagamento(
                    usuario_id=usuario_id,
                    provedor=ProvedorPagamento.MERCADO_PAGO,
                    conta_externa_id=conta_externa_id,
                    access_token_criptografado=cipher.encrypt(access_token),
                    refresh_token_criptografado=cipher.encrypt(refresh_token),
                    status=ContaPagamentoStatus.ATIVA,
                    autorizado_em=agora,
                    token_expira_em=agora + timedelta(seconds=expires_in),
                )
                self.session.add(conta)
            else:
                conta.conta_externa_id = conta_externa_id
                conta.access_token_criptografado = cipher.encrypt(access_token)
                conta.refresh_token_criptografado = cipher.encrypt(refresh_token)
                conta.status = ContaPagamentoStatus.ATIVA
                conta.autorizado_em = agora
                conta.token_expira_em = agora + timedelta(seconds=expires_in)
            await self.session.flush()

    async def obter_status(self, usuario_id: UUID) -> ContaPagamentoResponse:
        async with self.session.begin():
            conta = await self.session.scalar(
                select(ContaPagamento).where(
                    ContaPagamento.usuario_id == usuario_id,
                    ContaPagamento.provedor == ProvedorPagamento.MERCADO_PAGO,
                )
            )
        if conta is None:
            return ContaPagamentoResponse(
                status=ContaPagamentoStatus.PENDENTE,
                conta_externa_id=None,
                autorizado_em=None,
                token_expira_em=None,
            )
        return ContaPagamentoResponse(
            status=conta.status,
            conta_externa_id=conta.conta_externa_id,
            autorizado_em=conta.autorizado_em,
            token_expira_em=conta.token_expira_em,
        )

    async def obter_access_token(self, usuario_id: UUID) -> tuple[ContaPagamento, str]:
        client_id, client_secret, _, cipher = self._configuracao()
        agora = datetime.now(UTC)
        async with self.session.begin():
            conta = await self.session.scalar(
                select(ContaPagamento).where(
                    ContaPagamento.usuario_id == usuario_id,
                    ContaPagamento.provedor == ProvedorPagamento.MERCADO_PAGO,
                )
            )
        if (
            conta is None
            or conta.status != ContaPagamentoStatus.ATIVA
            or not conta.access_token_criptografado
        ):
            raise AppError(
                status_code=409,
                detail="O vendedor precisa conectar uma conta Mercado Pago antes de vender.",
                code="MP_SELLER_NOT_CONNECTED",
            )
        if conta.token_expira_em and conta.token_expira_em > agora + timedelta(minutes=5):
            return conta, cipher.decrypt(conta.access_token_criptografado)
        if not conta.refresh_token_criptografado:
            await self._bloquear_conta(conta)
            raise self._erro_token()

        try:
            resposta = await self.gateway.renovar_token(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=cipher.decrypt(conta.refresh_token_criptografado),
            )
        except MercadoPagoIntegrationError as exc:
            await self._bloquear_conta(conta)
            raise self._erro_token() from exc

        access_token = self._campo_obrigatorio(resposta.data, "access_token")
        refresh_token = str(resposta.data.get("refresh_token") or "")
        expires_in = int(resposta.data.get("expires_in", 15_552_000))
        async with self.session.begin():
            conta.access_token_criptografado = cipher.encrypt(access_token)
            if refresh_token:
                conta.refresh_token_criptografado = cipher.encrypt(refresh_token)
            conta.token_expira_em = agora + timedelta(seconds=expires_in)
            conta.status = ContaPagamentoStatus.ATIVA
            await self.session.flush()
        return conta, access_token

    async def _bloquear_conta(self, conta: ContaPagamento) -> None:
        if self.session.in_transaction():
            await self.session.rollback()
        async with self.session.begin():
            conta.status = ContaPagamentoStatus.BLOQUEADA
            await self.session.flush()

    def _configuracao(self) -> tuple[str, str, str, TokenCipher]:
        segredo = self.settings.mp_client_secret
        chave = self.settings.mp_token_encryption_key
        if not self.settings.mp_client_id or segredo is None or chave is None:
            raise AppError(
                status_code=503,
                detail="A integração com o Mercado Pago ainda não foi configurada.",
                code="MP_NOT_CONFIGURED",
            )
        if not self.settings.mp_oauth_redirect_uri:
            raise AppError(
                status_code=503,
                detail="A URL de retorno OAuth do Mercado Pago não foi configurada.",
                code="MP_OAUTH_REDIRECT_NOT_CONFIGURED",
            )
        try:
            cipher = TokenCipher(chave.get_secret_value())
        except ValueError as exc:
            raise AppError(
                status_code=503,
                detail="A chave de criptografia dos tokens do Mercado Pago é inválida.",
                code="MP_ENCRYPTION_KEY_INVALID",
            ) from exc
        return (
            self.settings.mp_client_id,
            segredo.get_secret_value(),
            self.settings.mp_oauth_redirect_uri,
            cipher,
        )

    @staticmethod
    def _campo_obrigatorio(payload: dict[str, object], campo: str) -> str:
        valor = payload.get(campo)
        if valor is None or valor == "":
            raise AppError(
                status_code=502,
                detail="O Mercado Pago retornou uma resposta incompleta.",
                code="MP_INVALID_RESPONSE",
            )
        return str(valor)

    @staticmethod
    def _erro_token() -> AppError:
        return AppError(
            status_code=409,
            detail="A autorização do vendedor no Mercado Pago expirou. Reconecte a conta.",
            code="MP_SELLER_RECONNECT_REQUIRED",
        )

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.integrations.mercado_pago import MercadoPagoGateway, MercadoPagoIntegrationError
from app.models.anuncio import Anuncio
from app.models.destaque_anuncio import REFERENCIA_DESTAQUE, DestaqueAnuncio
from app.models.enums import (
    AnuncioStatus,
    DestaqueAnuncioStatus,
    EventoProcessamentoStatus,
    MetodoPagamento,
    PagamentoStatus,
)
from app.models.evento_provedor import EventoProvedor
from app.schemas.destaque_anuncio import (
    DestaqueAnuncioListResponse,
    DestaqueAnuncioResponse,
    DestaqueCheckoutResponse,
    DestaquePrecoResponse,
)
from app.services.credencial_pagamento import token_marketplace
from app.services.pedido import CENTAVOS, PedidoService

logger = logging.getLogger(__name__)

TIPO_DESTAQUE = "DESTAQUE_ANUNCIO"
_PAGAMENTO_FINAL = {PagamentoStatus.APROVADO, PagamentoStatus.REEMBOLSADO}


def eh_referencia_destaque(external_reference: object) -> bool:
    return str(external_reference or "").startswith(REFERENCIA_DESTAQUE)


class DestaqueAnuncioService:
    """Venda do destaque de anúncio pelo Checkout Pro, recebida pela Obra Circular."""

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

    def preco(self) -> DestaquePrecoResponse:
        return DestaquePrecoResponse(
            valor=self.settings.featured_ad_price.quantize(CENTAVOS),
            duracao_dias=self.settings.featured_ad_duration_days,
        )

    async def criar_checkout(
        self,
        anuncio_id: UUID,
        *,
        vendedor_id: UUID,
        vendedor_email: str,
        vendedor_nome: str = "",
        vendedor_criado_em: datetime | None = None,
    ) -> DestaqueCheckoutResponse:
        """Cria uma Preference para o vendedor pagar o destaque do próprio anúncio."""
        access_token = token_marketplace(self.settings)
        agora = datetime.now(UTC)
        valor = self.settings.featured_ad_price.quantize(CENTAVOS)
        duracao = self.settings.featured_ad_duration_days
        checkout_expira_em = agora + timedelta(minutes=self.settings.featured_ad_checkout_minutes)

        retomar: tuple[UUID, str, Decimal, int, datetime] | None = None
        async with self.session.begin():
            anuncio = await self.session.scalar(
                select(Anuncio).where(Anuncio.id == anuncio_id).with_for_update()
            )
            if anuncio is None or anuncio.deletado_em is not None:
                raise self._erro(404, "Anúncio não encontrado.", "AD_NOT_FOUND")
            if anuncio.vendedor_id != vendedor_id:
                raise self._erro(
                    403, "Somente o vendedor pode destacar este anúncio.", "AD_FORBIDDEN"
                )
            if anuncio.status != AnuncioStatus.ATIVO:
                raise self._erro(
                    409,
                    "Apenas anúncios disponíveis podem ser destacados.",
                    "AD_NOT_AVAILABLE_FOR_FEATURE",
                )
            pendente = await self.session.scalar(
                select(DestaqueAnuncio)
                .where(
                    DestaqueAnuncio.anuncio_id == anuncio.id,
                    DestaqueAnuncio.status == DestaqueAnuncioStatus.AGUARDANDO_PAGAMENTO,
                )
                .with_for_update()
            )
            if pendente is not None:
                if pendente.checkout_expira_em > agora and pendente.preferencia_externa_id:
                    retomar = (
                        pendente.id,
                        pendente.preferencia_externa_id,
                        pendente.valor,
                        pendente.duracao_dias,
                        pendente.checkout_expira_em,
                    )
                else:
                    self._cancelar(pendente, agora)
                    await self.session.flush()

            if retomar is None:
                destaque = DestaqueAnuncio(
                    anuncio_id=anuncio.id,
                    vendedor_id=vendedor_id,
                    valor=valor,
                    duracao_dias=duracao,
                    status=DestaqueAnuncioStatus.AGUARDANDO_PAGAMENTO,
                    idempotency_key=str(uuid4()),
                    recebedor_externo_id=self.settings.mp_marketplace_user_id,
                    status_pagamento=PagamentoStatus.CRIADO,
                    checkout_expira_em=checkout_expira_em,
                )
                self.session.add(destaque)
                await self.session.flush()
                destaque_id = destaque.id
                titulo = anuncio.titulo

        if retomar is not None:
            return await self._retomar(anuncio_id, *retomar, access_token=access_token)

        try:
            payload = self._payload_preferencia(
                destaque_id=destaque_id,
                anuncio_id=anuncio_id,
                titulo=titulo,
                valor=valor,
                duracao=duracao,
                vendedor_email=vendedor_email,
                vendedor_nome=vendedor_nome,
                vendedor_criado_em=vendedor_criado_em,
                expira_em=checkout_expira_em,
            )
            resposta = await self.gateway.criar_preferencia(
                access_token=access_token, payload=payload
            )
            preferencia_id = str(resposta.data["id"])
            init_point = str(resposta.data.get("init_point"))
            if not init_point or init_point == "None":
                raise KeyError("init_point")
        except (MercadoPagoIntegrationError, KeyError, AppError) as exc:
            logger.warning(
                "Falha ao criar Preference de destaque: destaque_id=%s erro=%s",
                destaque_id,
                type(exc).__name__,
            )
            async with self.session.begin():
                falho = await self.session.get(DestaqueAnuncio, destaque_id)
                if falho is not None:
                    self._cancelar(falho, datetime.now(UTC))
            if isinstance(exc, AppError):
                raise
            if isinstance(exc, MercadoPagoIntegrationError) and exc.status_code == 401:
                raise self._erro(
                    409,
                    "A credencial recebedora da Obra Circular foi recusada.",
                    "MP_MARKETPLACE_CREDENTIAL_INVALID",
                ) from exc
            raise self._erro(
                502,
                "Não foi possível iniciar o pagamento do destaque no Mercado Pago.",
                "MP_FEATURED_CHECKOUT_CREATE_FAILED",
            ) from exc

        async with self.session.begin():
            destaque_atualizado = await self.session.get(DestaqueAnuncio, destaque_id)
            if destaque_atualizado is None:
                raise self._erro(500, "Compra de destaque não encontrada.", "FEATURED_NOT_FOUND")
            destaque_atualizado.preferencia_externa_id = preferencia_id
            destaque_atualizado.status_pagamento = PagamentoStatus.PENDENTE

        return DestaqueCheckoutResponse(
            destaque_id=destaque_id,
            anuncio_id=anuncio_id,
            preferencia_externa_id=preferencia_id,
            init_point=init_point,
            valor=valor,
            duracao_dias=duracao,
            checkout_expira_em=checkout_expira_em,
        )

    async def buscar(self, destaque_id: UUID, vendedor_id: UUID) -> DestaqueAnuncioResponse:
        destaque = await self.session.scalar(
            select(DestaqueAnuncio).where(
                DestaqueAnuncio.id == destaque_id,
                DestaqueAnuncio.vendedor_id == vendedor_id,
            )
        )
        if destaque is None:
            raise self._erro(404, "Compra de destaque não encontrada.", "FEATURED_NOT_FOUND")
        return DestaqueAnuncioResponse.model_validate(destaque)

    async def listar(self, anuncio_id: UUID, vendedor_id: UUID) -> DestaqueAnuncioListResponse:
        anuncio = await self.session.get(Anuncio, anuncio_id)
        if anuncio is None or anuncio.deletado_em is not None:
            raise self._erro(404, "Anúncio não encontrado.", "AD_NOT_FOUND")
        if anuncio.vendedor_id != vendedor_id:
            raise self._erro(403, "Somente o vendedor pode consultar os destaques.", "AD_FORBIDDEN")
        destaques = list(
            await self.session.scalars(
                select(DestaqueAnuncio)
                .where(DestaqueAnuncio.anuncio_id == anuncio_id)
                .order_by(DestaqueAnuncio.criado_em.desc(), DestaqueAnuncio.id.desc())
            )
        )
        return DestaqueAnuncioListResponse(
            items=[DestaqueAnuncioResponse.model_validate(item) for item in destaques],
            total=len(destaques),
        )

    async def aplicar_pagamento(
        self,
        evento_id: UUID,
        dados: dict[str, Any],
        *,
        metodo: MetodoPagamento | None,
        trabalhador: str | None = None,
    ) -> None:
        """Concilia um pagamento de destaque já consultado no Mercado Pago.

        Idempotente: reaplicar o mesmo estado não estende o destaque novamente.
        """
        referencia = str(dados.get("external_reference") or "")
        try:
            destaque_id = UUID(referencia.removeprefix(REFERENCIA_DESTAQUE))
        except ValueError as exc:
            raise self._erro(
                400, "Referência de destaque inválida.", "FEATURED_REFERENCE_INVALID"
            ) from exc
        agora = datetime.now(UTC)
        async with self.session.begin():
            evento = await self.session.scalar(
                select(EventoProvedor)
                .where(EventoProvedor.id == evento_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if evento is None:
                raise self._erro(404, "Evento não encontrado.", "PROVIDER_EVENT_NOT_FOUND")
            if evento.status_processamento in {
                EventoProcessamentoStatus.PROCESSADO,
                EventoProcessamentoStatus.IGNORADO,
            }:
                return
            if trabalhador and evento.bloqueado_por != trabalhador:
                raise self._erro(
                    409,
                    "O lease deste evento pertence a outro worker.",
                    "PROVIDER_EVENT_LEASE_LOST",
                )
            destaque = await self.session.scalar(
                select(DestaqueAnuncio).where(DestaqueAnuncio.id == destaque_id).with_for_update()
            )
            if destaque is None:
                raise self._erro(404, "Compra de destaque não encontrada.", "FEATURED_NOT_FOUND")
            self._validar_dados(dados, destaque)

            pagamento_externo_id = str(dados["id"])
            if (
                destaque.status_pagamento in _PAGAMENTO_FINAL
                and destaque.pagamento_externo_id not in {None, pagamento_externo_id}
            ):
                # Outro pagamento para a mesma Preference depois da conciliação: não
                # estende o destaque duas vezes. Fica registrado para o atendimento.
                logger.warning(
                    "Pagamento adicional para destaque já conciliado: destaque_id=%s pagamento=%s",
                    destaque.id,
                    pagamento_externo_id,
                )
                self._finalizar_evento(evento, EventoProcessamentoStatus.PROCESSADO, agora)
                return
            destaque.pagamento_externo_id = pagamento_externo_id
            destaque.status_detalhe = (
                str(dados["status_detail"])[:100] if dados.get("status_detail") else None
            )
            if metodo is not None:
                destaque.metodo = metodo

            status_mp = str(dados.get("status"))
            if status_mp == "approved":
                if destaque.status_pagamento not in _PAGAMENTO_FINAL:
                    await self._ativar(destaque, agora)
            elif status_mp in {"pending", "authorized"}:
                if destaque.status_pagamento not in _PAGAMENTO_FINAL:
                    destaque.status_pagamento = PagamentoStatus.PENDENTE
            elif status_mp == "in_process":
                if destaque.status_pagamento not in _PAGAMENTO_FINAL:
                    destaque.status_pagamento = PagamentoStatus.EM_PROCESSAMENTO
            elif status_mp == "rejected":
                if destaque.status_pagamento not in _PAGAMENTO_FINAL:
                    destaque.status_pagamento = PagamentoStatus.RECUSADO
            elif status_mp == "cancelled":
                if destaque.status_pagamento not in _PAGAMENTO_FINAL:
                    self._cancelar(destaque, agora)
            elif status_mp in {"refunded", "charged_back"}:
                if destaque.status_pagamento != PagamentoStatus.REEMBOLSADO:
                    await self._revogar(destaque, agora)
            else:
                self._finalizar_evento(evento, EventoProcessamentoStatus.IGNORADO, agora)
                return
            self._finalizar_evento(evento, EventoProcessamentoStatus.PROCESSADO, agora)

    async def _retomar(
        self,
        anuncio_id: UUID,
        destaque_id: UUID,
        preferencia_id: str,
        valor: Decimal,
        duracao: int,
        checkout_expira_em: datetime,
        *,
        access_token: str,
    ) -> DestaqueCheckoutResponse:
        try:
            resposta = await self.gateway.obter_preferencia(
                access_token=access_token, preferencia_id=preferencia_id
            )
            init_point = str(resposta.data.get("init_point"))
            if not init_point or init_point == "None":
                raise KeyError("init_point")
        except (MercadoPagoIntegrationError, KeyError) as exc:
            raise self._erro(
                502,
                "Não foi possível retomar o pagamento do destaque no Mercado Pago.",
                "MP_FEATURED_CHECKOUT_RESUME_FAILED",
            ) from exc
        return DestaqueCheckoutResponse(
            destaque_id=destaque_id,
            anuncio_id=anuncio_id,
            preferencia_externa_id=preferencia_id,
            init_point=init_point,
            valor=valor,
            duracao_dias=duracao,
            checkout_expira_em=checkout_expira_em,
        )

    async def _ativar(self, destaque: DestaqueAnuncio, agora: datetime) -> None:
        anuncio = await self.session.scalar(
            select(Anuncio).where(Anuncio.id == destaque.anuncio_id).with_for_update()
        )
        if anuncio is None:
            raise self._erro(500, "Anúncio do destaque não encontrado.", "AD_NOT_FOUND")
        # Pagamentos aprovados são sempre honrados, mesmo se o checkout local já
        # tiver expirado. Um destaque vigente é estendido em vez de sobreposto.
        inicio = max(agora, anuncio.destaque_ate) if anuncio.destaque_ate else agora
        fim = inicio + timedelta(days=destaque.duracao_dias)
        destaque.status = DestaqueAnuncioStatus.ATIVO
        destaque.status_pagamento = PagamentoStatus.APROVADO
        destaque.aprovado_em = agora
        destaque.inicia_em = inicio
        destaque.expira_em = fim
        destaque.cancelado_em = None
        anuncio.destaque_ate = fim

    async def _revogar(self, destaque: DestaqueAnuncio, agora: datetime) -> None:
        estava_ativo = destaque.status == DestaqueAnuncioStatus.ATIVO
        destaque.status_pagamento = PagamentoStatus.REEMBOLSADO
        destaque.status = DestaqueAnuncioStatus.REEMBOLSADO
        destaque.cancelado_em = destaque.cancelado_em or agora
        if not estava_ativo or destaque.inicia_em is None or destaque.expira_em is None:
            return
        anuncio = await self.session.scalar(
            select(Anuncio).where(Anuncio.id == destaque.anuncio_id).with_for_update()
        )
        if anuncio is None or anuncio.destaque_ate is None:
            return
        # Remove apenas o tempo ainda não usufruído deste destaque.
        restante = destaque.expira_em - max(destaque.inicia_em, agora)
        if restante > timedelta(0):
            novo_fim = anuncio.destaque_ate - restante
            anuncio.destaque_ate = novo_fim if novo_fim > agora else None

    @staticmethod
    def _cancelar(destaque: DestaqueAnuncio, agora: datetime) -> None:
        if destaque.status == DestaqueAnuncioStatus.AGUARDANDO_PAGAMENTO:
            destaque.status = DestaqueAnuncioStatus.CANCELADO
            destaque.cancelado_em = agora
        if destaque.status_pagamento not in _PAGAMENTO_FINAL:
            destaque.status_pagamento = PagamentoStatus.CANCELADO

    def _validar_dados(self, dados: dict[str, Any], destaque: DestaqueAnuncio) -> None:
        metadata = dados.get("metadata") or {}
        destaque_meta = metadata.get("destaque_id") if isinstance(metadata, dict) else None
        if destaque_meta and str(destaque_meta) != str(destaque.id):
            raise self._erro(
                409, "Destaque do pagamento é inconsistente.", "FEATURED_PAYMENT_MISMATCH"
            )
        if str(dados.get("collector_id")) != str(destaque.recebedor_externo_id):
            raise self._erro(
                409, "Recebedor do pagamento é inconsistente.", "PAYMENT_COLLECTOR_MISMATCH"
            )
        valor = Decimal(str(dados.get("transaction_amount"))).quantize(CENTAVOS)
        if valor != destaque.valor:
            raise self._erro(409, "Valor do pagamento é inconsistente.", "PAYMENT_AMOUNT_MISMATCH")
        if self.settings.mp_live_mode and not bool(dados.get("live_mode")):
            raise self._erro(
                409,
                "O modo do pagamento não corresponde ao modo configurado no backend.",
                "PAYMENT_MODE_MISMATCH",
            )

    def _payload_preferencia(
        self,
        *,
        destaque_id: UUID,
        anuncio_id: UUID,
        titulo: str,
        valor: Decimal,
        duracao: int,
        vendedor_email: str,
        vendedor_nome: str,
        vendedor_criado_em: datetime | None,
        expira_em: datetime,
    ) -> dict[str, Any]:
        if not self.settings.mp_public_base_url or not self.settings.mp_webhook_url:
            raise self._erro(
                503,
                "As URLs públicas do Mercado Pago não foram configuradas.",
                "MP_PUBLIC_URLS_NOT_CONFIGURED",
            )
        retorno = (
            f"{self.settings.mp_public_base_url.rstrip('/')}"
            f"{self.settings.api_v1_prefix}/integrations/mercado-pago/checkout/return"
        )
        partes_nome = vendedor_nome.strip().split(maxsplit=1)
        payer: dict[str, Any] = {}
        if self.settings.mp_live_mode:
            payer["email"] = vendedor_email
        if partes_nome:
            payer["name"] = partes_nome[0]
        if len(partes_nome) > 1:
            payer["surname"] = partes_nome[1]
        if vendedor_criado_em is not None:
            payer["date_created"] = PedidoService._data_mp(vendedor_criado_em)
        payload: dict[str, Any] = {
            "external_reference": f"{REFERENCIA_DESTAQUE}{destaque_id}",
            "notification_url": self.settings.mp_webhook_url,
            "statement_descriptor": "OBRACIRCULAR",
            "payer": payer,
            "items": [
                {
                    "id": f"destaque-{anuncio_id}",
                    "title": f"Destaque de anúncio por {duracao} dias",
                    "description": f"Destaque do anúncio: {titulo}"[:255],
                    "category_id": "services",
                    "currency_id": "BRL",
                    "quantity": 1,
                    "unit_price": float(valor),
                }
            ],
            "metadata": {
                "tipo": TIPO_DESTAQUE,
                "destaque_id": str(destaque_id),
                "anuncio_id": str(anuncio_id),
            },
            "back_urls": {
                "success": f"{retorno}?result=success",
                "pending": f"{retorno}?result=pending",
                "failure": f"{retorno}?result=failure",
            },
            "expires": True,
            "expiration_date_to": PedidoService._data_mp(expira_em),
            "payment_methods": {"excluded_payment_types": [{"id": "ticket"}, {"id": "atm"}]},
        }
        if PedidoService._url_publica_https(self.settings.mp_public_base_url):
            payload["auto_return"] = "approved"
        return payload

    @staticmethod
    def _finalizar_evento(
        evento: EventoProvedor, status: EventoProcessamentoStatus, agora: datetime
    ) -> None:
        evento.status_processamento = status
        evento.processado_em = agora
        evento.erro = None
        evento.proxima_tentativa_em = None
        evento.bloqueado_ate = None
        evento.bloqueado_por = None

    @staticmethod
    def _erro(status: int, detail: str, code: str) -> AppError:
        return AppError(status_code=status, detail=detail, code=code)

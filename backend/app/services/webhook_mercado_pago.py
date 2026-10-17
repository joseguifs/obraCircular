from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.provider_security import validar_assinatura_webhook
from app.integrations.mercado_pago import MercadoPagoGateway, MercadoPagoIntegrationError
from app.models.anuncio import Anuncio
from app.models.conta_pagamento import ContaPagamento
from app.models.enums import (
    EventoProcessamentoStatus,
    MetodoPagamento,
    PagamentoStatus,
    PedidoStatus,
    ProvedorPagamento,
    RepasseStatus,
)
from app.models.evento_provedor import EventoProvedor
from app.models.pagamento import Pagamento
from app.models.pedido import Pedido
from app.models.repasse import Repasse
from app.services.conta_pagamento import ContaPagamentoService
from app.services.pedido import CENTAVOS, PedidoService


class WebhookMercadoPagoService:
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

    async def receber(
        self,
        *,
        payload: dict[str, Any],
        data_id: str,
        x_signature: str,
        x_request_id: str,
    ) -> None:
        segredo = self.settings.mp_webhook_secret
        if segredo is None:
            raise self._erro(
                503,
                "O segredo do webhook não foi configurado.",
                "MP_WEBHOOK_NOT_CONFIGURED",
            )
        if not validar_assinatura_webhook(
            x_signature=x_signature,
            x_request_id=x_request_id,
            data_id=data_id,
            secret=segredo.get_secret_value(),
        ):
            raise self._erro(401, "Assinatura do webhook inválida.", "MP_WEBHOOK_INVALID_SIGNATURE")
        corpo_data_id = str((payload.get("data") or {}).get("id", ""))
        if not corpo_data_id or corpo_data_id.lower() != data_id.lower():
            raise self._erro(
                400,
                "Identificador do webhook inconsistente.",
                "MP_WEBHOOK_DATA_MISMATCH",
            )

        evento_externo_id = str(payload.get("id") or x_request_id)
        evento = await self._registrar_evento(evento_externo_id, data_id, payload)
        if evento.status_processamento in {
            EventoProcessamentoStatus.PROCESSADO,
            EventoProcessamentoStatus.IGNORADO,
        }:
            return
        if payload.get("type") != "payment":
            await self._marcar_evento(evento.id, EventoProcessamentoStatus.IGNORADO)
            return

        try:
            usuario_id = await self._identificar_vendedor(payload)
            _, access_token = await ContaPagamentoService(
                self.session, settings=self.settings, gateway=self.gateway
            ).obter_access_token(usuario_id)
            pagamento_mp = (
                await self.gateway.obter_pagamento(
                    access_token=access_token, pagamento_externo_id=data_id
                )
            ).data
            await self._aplicar_pagamento(evento.id, pagamento_mp, usuario_id)
        except (AppError, MercadoPagoIntegrationError, KeyError, TypeError, ValueError) as exc:
            await self._marcar_evento(
                evento.id, EventoProcessamentoStatus.FALHOU, erro=str(exc)[:2000]
            )
            if isinstance(exc, AppError):
                raise
            raise self._erro(
                503,
                "Não foi possível processar o webhook do Mercado Pago.",
                "MP_WEBHOOK_PROCESSING_FAILED",
            ) from exc

    async def _registrar_evento(
        self, evento_externo_id: str, recurso_id: str, payload: dict[str, Any]
    ) -> EventoProvedor:
        async with self.session.begin():
            evento = await self.session.scalar(
                select(EventoProvedor).where(
                    EventoProvedor.provedor == ProvedorPagamento.MERCADO_PAGO,
                    EventoProvedor.evento_externo_id == evento_externo_id,
                )
            )
            if evento is None:
                evento = EventoProvedor(
                    provedor=ProvedorPagamento.MERCADO_PAGO,
                    evento_externo_id=evento_externo_id,
                    tipo=str(payload.get("action") or payload.get("type") or "unknown"),
                    recurso_externo_id=recurso_id,
                    payload=payload,
                    status_processamento=EventoProcessamentoStatus.PENDENTE,
                    tentativas=0,
                    processado_em=None,
                    erro=None,
                )
                self.session.add(evento)
                await self.session.flush()
            else:
                evento.tentativas += 1
                evento.payload = payload
                await self.session.flush()
        return evento

    async def _identificar_vendedor(self, payload: dict[str, Any]) -> UUID:
        conta_externa_id = str(payload.get("user_id") or "")
        if not conta_externa_id:
            raise self._erro(
                400,
                "Webhook sem identificação do vendedor.",
                "MP_WEBHOOK_USER_MISSING",
            )
        async with self.session.begin():
            conta = await self.session.scalar(
                select(ContaPagamento).where(
                    ContaPagamento.provedor == ProvedorPagamento.MERCADO_PAGO,
                    ContaPagamento.conta_externa_id == conta_externa_id,
                )
            )
            if conta is None:
                raise self._erro(404, "Conta de vendedor não reconhecida.", "MP_SELLER_UNKNOWN")
            return conta.usuario_id

    async def _aplicar_pagamento(
        self, evento_id: UUID, dados: dict[str, Any], vendedor_id: UUID
    ) -> None:
        pedido_id = UUID(str(dados["external_reference"]))
        metadata = dados.get("metadata") or {}
        pagamento_id_texto = metadata.get("pagamento_id")
        agora = datetime.now(UTC)
        async with self.session.begin():
            evento = await self.session.scalar(
                select(EventoProvedor).where(EventoProvedor.id == evento_id).with_for_update()
            )
            if evento is None:
                raise self._erro(404, "Evento não encontrado.", "PROVIDER_EVENT_NOT_FOUND")
            if evento.status_processamento == EventoProcessamentoStatus.PROCESSADO:
                return
            pedido = await self.session.scalar(
                select(Pedido).where(Pedido.id == pedido_id).with_for_update()
            )
            if pedido is None:
                raise self._erro(404, "Pedido do pagamento não encontrado.", "ORDER_NOT_FOUND")
            if pagamento_id_texto:
                pagamento = await self.session.scalar(
                    select(Pagamento).where(
                        Pagamento.id == UUID(str(pagamento_id_texto)),
                        Pagamento.pedido_id == pedido.id,
                    )
                )
            else:
                pagamento = await self.session.scalar(
                    select(Pagamento)
                    .where(Pagamento.pedido_id == pedido.id)
                    .order_by(Pagamento.criado_em.desc())
                )
            if pagamento is None:
                raise self._erro(404, "Tentativa de pagamento não encontrada.", "PAYMENT_NOT_FOUND")

            anuncio = await self.session.scalar(
                select(Anuncio).where(Anuncio.id == pedido.anuncio_id).with_for_update()
            )
            if anuncio is None or anuncio.vendedor_id != vendedor_id:
                raise self._erro(
                    409,
                    "Vendedor do pagamento é inconsistente.",
                    "PAYMENT_SELLER_MISMATCH",
                )
            conta = await self.session.scalar(
                select(ContaPagamento).where(
                    ContaPagamento.usuario_id == vendedor_id,
                    ContaPagamento.provedor == ProvedorPagamento.MERCADO_PAGO,
                )
            )
            if conta is None:
                raise self._erro(409, "Conta do vendedor não encontrada.", "MP_SELLER_UNKNOWN")
            self._validar_dados(dados, pedido)
            pagamento.pagamento_externo_id = str(dados["id"])
            pagamento.status_detalhe = self._texto_opcional(dados.get("status_detail"))
            pagamento.metodo = self._mapear_metodo(dados)
            pagamento.parcelas = (
                int(dados.get("installments") or 1)
                if pagamento.metodo == MetodoPagamento.CARTAO_CREDITO
                else None
            )
            status_mp = str(dados.get("status"))
            if status_mp == "approved":
                self._aprovar(pedido, pagamento, anuncio, conta.id, dados, agora)
            elif status_mp in {"pending", "authorized"}:
                pagamento.status = PagamentoStatus.PENDENTE
            elif status_mp == "in_process":
                pagamento.status = PagamentoStatus.EM_PROCESSAMENTO
            elif status_mp == "rejected":
                pagamento.status = PagamentoStatus.RECUSADO
                pagamento.motivo_recusa = pagamento.status_detalhe
            elif status_mp == "cancelled":
                pagamento.status = PagamentoStatus.CANCELADO
                pagamento.cancelado_em = agora
                if pedido.status == PedidoStatus.AGUARDANDO_PAGAMENTO:
                    PedidoService._liberar_estoque(pedido, anuncio, agora)
                    pedido.status = PedidoStatus.CANCELADO
                    pedido.cancelado_em = agora
            elif status_mp in {"refunded", "charged_back"}:
                pagamento.status = PagamentoStatus.REEMBOLSADO
                pedido.status = PedidoStatus.REEMBOLSADO
                PedidoService._liberar_estoque(pedido, anuncio, agora)
                repasse = await self.session.scalar(
                    select(Repasse).where(Repasse.pagamento_id == pagamento.id)
                )
                if repasse:
                    repasse.status = RepasseStatus.REEMBOLSADO
            else:
                evento.status_processamento = EventoProcessamentoStatus.IGNORADO
                evento.processado_em = agora
                return
            evento.status_processamento = EventoProcessamentoStatus.PROCESSADO
            evento.processado_em = agora
            evento.erro = None
            await self.session.flush()

    def _aprovar(
        self,
        pedido: Pedido,
        pagamento: Pagamento,
        anuncio: Anuncio,
        conta_pagamento_id: UUID,
        dados: dict[str, Any],
        agora: datetime,
    ) -> None:
        if pagamento.status == PagamentoStatus.APROVADO:
            return
        if pedido.status != PedidoStatus.AGUARDANDO_PAGAMENTO or pedido.estoque_liberado_em:
            raise self._erro(
                409,
                "O pagamento foi aprovado depois que a reserva deixou de ser válida.",
                "PAYMENT_APPROVED_WITHOUT_RESERVATION",
            )
        pagamento.status = PagamentoStatus.APROVADO
        pagamento.aprovado_em = agora
        pedido.status = PedidoStatus.PAGAMENTO_APROVADO
        taxa_marketplace = PedidoService.calcular_taxa_marketplace(
            pedido.valor_total, self.settings.marketplace_fee_percent
        )
        taxa_provedor = self._taxa_provedor(dados)
        valor_liquido = (pedido.valor_total - taxa_marketplace - taxa_provedor).quantize(
            CENTAVOS, rounding=ROUND_HALF_UP
        )
        if valor_liquido < 0:
            raise self._erro(
                409,
                "As taxas confirmadas excedem o valor do pagamento.",
                "PAYMENT_FEES_INVALID",
            )
        repasse = Repasse(
            pedido_id=pedido.id,
            pagamento_id=pagamento.id,
            vendedor_id=anuncio.vendedor_id,
            conta_pagamento_id=conta_pagamento_id,
            valor_bruto=pedido.valor_total,
            taxa_provedor=taxa_provedor,
            taxa_marketplace=taxa_marketplace,
            valor_liquido=valor_liquido,
            percentual_marketplace=self.settings.marketplace_fee_percent,
            status=RepasseStatus.PAGO,
            liberacao_prevista_em=None,
            repasse_externo_id=str(dados["id"]),
            tentativas=0,
            liberado_em=agora,
            pago_em=agora,
            bloqueado_em=None,
        )
        self.session.add(repasse)

    def _validar_dados(self, dados: dict[str, Any], pedido: Pedido) -> None:
        valor = Decimal(str(dados.get("transaction_amount"))).quantize(CENTAVOS)
        if valor != pedido.valor_total:
            raise self._erro(409, "Valor do pagamento é inconsistente.", "PAYMENT_AMOUNT_MISMATCH")
        live_mode = bool(dados.get("live_mode"))
        if live_mode != (self.settings.environment == "production"):
            raise self._erro(
                409,
                "Pagamento de teste recebido em produção.",
                "PAYMENT_MODE_MISMATCH",
            )

    @staticmethod
    def _mapear_metodo(dados: dict[str, Any]) -> MetodoPagamento | None:
        tipo = str(dados.get("payment_type_id") or "")
        metodo = str(dados.get("payment_method_id") or "")
        if tipo == "credit_card":
            return MetodoPagamento.CARTAO_CREDITO
        if tipo == "debit_card":
            return MetodoPagamento.CARTAO_DEBITO
        if metodo == "pix" or tipo == "bank_transfer":
            return MetodoPagamento.PIX
        if tipo in {"ticket", "atm"}:
            return MetodoPagamento.BOLETO
        return None

    @staticmethod
    def _taxa_provedor(dados: dict[str, Any]) -> Decimal:
        total = Decimal("0")
        for item in dados.get("fee_details") or []:
            if item.get("type") in {"mercadopago_fee", "financing_fee"}:
                total += Decimal(str(item.get("amount") or "0"))
        return total.quantize(CENTAVOS, rounding=ROUND_HALF_UP)

    async def _marcar_evento(
        self,
        evento_id: UUID,
        status: EventoProcessamentoStatus,
        *,
        erro: str | None = None,
    ) -> None:
        if self.session.in_transaction():
            await self.session.rollback()
        async with self.session.begin():
            evento = await self.session.get(EventoProvedor, evento_id)
            if evento:
                evento.status_processamento = status
                evento.erro = erro
                evento.processado_em = datetime.now(UTC) if erro is None else None

    @staticmethod
    def _texto_opcional(valor: object) -> str | None:
        return str(valor)[:100] if valor is not None else None

    @staticmethod
    def _erro(status: int, detail: str, code: str) -> AppError:
        return AppError(status_code=status, detail=detail, code=code)

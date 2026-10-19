import logging
import os
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.provider_security import validar_assinatura_webhook
from app.integrations.mercado_pago import MercadoPagoGateway, MercadoPagoIntegrationError
from app.models.anuncio import Anuncio
from app.models.conta_pagamento import ContaPagamento
from app.models.enums import (
    ContaPagamentoStatus,
    EventoProcessamentoStatus,
    MetodoPagamento,
    PagamentoStatus,
    PedidoStatus,
    ProvedorPagamento,
    ReembolsoStatus,
    RepasseStatus,
)
from app.models.evento_provedor import EventoProvedor
from app.models.pagamento import Pagamento
from app.models.pedido import Pedido
from app.models.reembolso import Reembolso
from app.models.repasse import Repasse
from app.services.conta_pagamento import ContaPagamentoService
from app.services.pedido import CENTAVOS, PedidoService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WebhookMonitoramento:
    status: str
    pendentes: int
    falhas_agendadas: int
    falhas_sem_retentativa: int
    em_processamento: int
    abandonados: int
    processados: int
    ignorados: int
    mais_antigo_nao_finalizado_em: datetime | None


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
    ) -> UUID:
        segredos = {
            segredo.get_secret_value()
            for segredo in (
                self.settings.mp_webhook_secret_test,
                self.settings.mp_webhook_secret_production,
                self.settings.mp_webhook_secret,
            )
            if segredo is not None and segredo.get_secret_value()
        }
        if not segredos:
            raise self._erro(
                503,
                "O segredo do webhook não foi configurado.",
                "MP_WEBHOOK_NOT_CONFIGURED",
            )
        if not any(
            validar_assinatura_webhook(
                x_signature=x_signature,
                x_request_id=x_request_id,
                data_id=data_id,
                secret=segredo,
            )
            for segredo in segredos
        ):
            raise self._erro(401, "Assinatura do webhook inválida.", "MP_WEBHOOK_INVALID_SIGNATURE")
        dados = payload.get("data")
        corpo_data_id = str(dados.get("id", "")) if isinstance(dados, dict) else ""
        if not corpo_data_id or corpo_data_id.lower() != data_id.lower():
            raise self._erro(
                400,
                "Identificador do webhook inconsistente.",
                "MP_WEBHOOK_DATA_MISMATCH",
            )

        evento_externo_id = str(payload.get("id") or x_request_id)
        evento = await self._registrar_evento(evento_externo_id, data_id, payload)
        return evento.id

    async def reprocessar_evento(self, evento_id: UUID, *, forcar: bool = False) -> bool:
        trabalhador = self._identificador_trabalhador()
        reivindicado = await self._reivindicar_evento(
            evento_id=evento_id,
            trabalhador=trabalhador,
            forcar=forcar,
        )
        if reivindicado is None:
            return False
        payload, recurso_id = reivindicado
        try:
            await self._executar_evento(evento_id, payload, recurso_id, trabalhador)
        except Exception as exc:
            reprocessavel = (
                exc.status_code is None or exc.status_code == 429 or exc.status_code >= 500
                if isinstance(exc, MercadoPagoIntegrationError)
                else not isinstance(exc, AppError) or exc.status_code >= 500
            )
            logger.warning(
                "Falha ao processar webhook do Mercado Pago: evento_id=%s reprocessavel=%s erro=%s",
                evento_id,
                reprocessavel,
                str(exc)[:500],
                exc_info=not isinstance(exc, AppError),
            )
            await self._marcar_evento(
                evento_id,
                EventoProcessamentoStatus.FALHOU,
                erro=str(exc)[:2000],
                reprocessavel=reprocessavel,
                trabalhador=trabalhador,
            )
        return True

    async def reprocessar_pendentes(self, *, limite: int | None = None) -> int:
        agora = datetime.now(UTC)
        tamanho_lote = limite or self.settings.webhook_retry_batch_size
        async with self.session.begin():
            ids = list(
                await self.session.scalars(
                    select(EventoProvedor.id)
                    .where(
                        EventoProvedor.status_processamento.in_(
                            (
                                EventoProcessamentoStatus.PENDENTE,
                                EventoProcessamentoStatus.FALHOU,
                            )
                        ),
                        self._elegivel(agora),
                        or_(
                            EventoProvedor.bloqueado_ate.is_(None),
                            EventoProvedor.bloqueado_ate <= agora,
                        ),
                    )
                    .order_by(
                        EventoProvedor.proxima_tentativa_em.asc().nullsfirst(),
                        EventoProvedor.recebido_em,
                    )
                    .limit(tamanho_lote)
                )
            )
        processados = 0
        for evento_id in ids:
            if await self.reprocessar_evento(evento_id):
                processados += 1
        return processados

    async def obter_monitoramento(self) -> WebhookMonitoramento:
        agora = datetime.now(UTC)
        nao_finalizados = (
            EventoProcessamentoStatus.PENDENTE,
            EventoProcessamentoStatus.FALHOU,
        )
        async with self.session.begin():
            pendentes = await self._contar(
                EventoProvedor.status_processamento == EventoProcessamentoStatus.PENDENTE
            )
            falhas_agendadas = await self._contar(
                EventoProvedor.status_processamento == EventoProcessamentoStatus.FALHOU,
                EventoProvedor.proxima_tentativa_em.is_not(None),
            )
            falhas_sem_retentativa = await self._contar(
                EventoProvedor.status_processamento == EventoProcessamentoStatus.FALHOU,
                EventoProvedor.proxima_tentativa_em.is_(None),
            )
            em_processamento = await self._contar(
                EventoProvedor.status_processamento.in_(nao_finalizados),
                EventoProvedor.bloqueado_ate > agora,
            )
            abandonados = await self._contar(
                EventoProvedor.status_processamento == EventoProcessamentoStatus.PENDENTE,
                EventoProvedor.proxima_tentativa_em.is_(None),
                or_(
                    EventoProvedor.bloqueado_ate.is_(None),
                    EventoProvedor.bloqueado_ate <= agora,
                ),
            )
            processados = await self._contar(
                EventoProvedor.status_processamento == EventoProcessamentoStatus.PROCESSADO
            )
            ignorados = await self._contar(
                EventoProvedor.status_processamento == EventoProcessamentoStatus.IGNORADO
            )
            mais_antigo = await self.session.scalar(
                select(func.min(EventoProvedor.recebido_em)).where(
                    EventoProvedor.status_processamento.in_(nao_finalizados)
                )
            )
        atrasado = mais_antigo is not None and mais_antigo <= agora - timedelta(minutes=5)
        status = (
            "critical"
            if falhas_sem_retentativa or abandonados
            else "degraded"
            if falhas_agendadas or atrasado
            else "ok"
        )
        return WebhookMonitoramento(
            status=status,
            pendentes=pendentes,
            falhas_agendadas=falhas_agendadas,
            falhas_sem_retentativa=falhas_sem_retentativa,
            em_processamento=em_processamento,
            abandonados=abandonados,
            processados=processados,
            ignorados=ignorados,
            mais_antigo_nao_finalizado_em=mais_antigo,
        )

    async def _executar_evento(
        self,
        evento_id: UUID,
        payload: dict[str, Any],
        recurso_id: str,
        trabalhador: str,
    ) -> None:
        tipo = str(payload.get("type") or "")
        if tipo == "mp-connect":
            await self._processar_mp_connect(evento_id, payload, trabalhador=trabalhador)
            return
        if tipo not in {"order", "payment"}:
            await self._marcar_evento(
                evento_id,
                EventoProcessamentoStatus.IGNORADO,
                trabalhador=trabalhador,
            )
            return
        usuario_id = await self._identificar_vendedor(payload)
        _, access_token = await ContaPagamentoService(
            self.session, settings=self.settings, gateway=self.gateway
        ).obter_access_token(usuario_id)
        if tipo == "order":
            order_mp = (
                await self.gateway.obter_order(access_token=access_token, order_id=recurso_id)
            ).data
            pagamento_mp = self._normalizar_order(order_mp, payload)
            devolver = await self._aplicar_pagamento(
                evento_id,
                pagamento_mp,
                usuario_id,
                ordem_externa_id=recurso_id,
                trabalhador=trabalhador,
            )
        else:
            pagamento_mp = (
                await self.gateway.obter_pagamento(
                    access_token=access_token, pagamento_externo_id=recurso_id
                )
            ).data
            devolver = await self._aplicar_pagamento(
                evento_id,
                pagamento_mp,
                usuario_id,
                trabalhador=trabalhador,
            )
        if devolver is not None:
            # A aprovação já foi conciliada em uma transação independente. Uma
            # queda aqui deixa o evento com lease, retomável pelo worker periódico.
            from app.services.reembolso import ReembolsoService

            pedido_id, comprador_id = devolver
            try:
                reembolso = await ReembolsoService(
                    self.session, settings=self.settings, gateway=self.gateway
                ).solicitar(pedido_id, comprador_id)
                if reembolso.status != ReembolsoStatus.CONCLUIDO:
                    raise self._erro(
                        503,
                        "A devolução do pagamento tardio ainda não foi confirmada.",
                        "LATE_PAYMENT_REFUND_PENDING",
                    )
            except (AppError, MercadoPagoIntegrationError) as exc:
                raise self._erro(
                    503,
                    "Pagamento tardio conciliado; a devolução precisa de nova tentativa.",
                    "LATE_PAYMENT_REFUND_PENDING",
                ) from exc
            await self._marcar_evento(
                evento_id, EventoProcessamentoStatus.PROCESSADO, trabalhador=trabalhador
            )

    @staticmethod
    def _elegivel(agora: datetime) -> ColumnElement[bool]:
        return or_(
            EventoProvedor.proxima_tentativa_em <= agora,
            and_(
                EventoProvedor.status_processamento == EventoProcessamentoStatus.PENDENTE,
                EventoProvedor.proxima_tentativa_em.is_(None),
            ),
        )

    async def _reivindicar_evento(
        self,
        *,
        evento_id: UUID,
        trabalhador: str,
        forcar: bool,
    ) -> tuple[dict[str, Any], str] | None:
        agora = datetime.now(UTC)
        criterios = [
            EventoProvedor.id == evento_id,
            EventoProvedor.status_processamento.in_(
                (
                    EventoProcessamentoStatus.PENDENTE,
                    EventoProcessamentoStatus.FALHOU,
                )
            ),
            or_(
                EventoProvedor.bloqueado_ate.is_(None),
                EventoProvedor.bloqueado_ate <= agora,
            ),
        ]
        if not forcar:
            criterios.extend((self._elegivel(agora),))
        async with self.session.begin():
            evento = await self.session.scalar(
                select(EventoProvedor)
                .where(*criterios)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
            if evento is None:
                return None
            if not forcar and evento.tentativas >= self.settings.webhook_retry_max_attempts:
                evento.status_processamento = EventoProcessamentoStatus.FALHOU
                evento.erro = "Limite de tentativas atingido; intervenção necessária."
                evento.proxima_tentativa_em = None
                evento.bloqueado_ate = None
                evento.bloqueado_por = None
                return None
            evento.status_processamento = EventoProcessamentoStatus.PENDENTE
            evento.tentativas += 1
            evento.ultima_tentativa_em = agora
            evento.proxima_tentativa_em = None
            evento.bloqueado_ate = agora + timedelta(
                seconds=self.settings.webhook_processing_lease_seconds
            )
            evento.bloqueado_por = trabalhador
            payload = dict(evento.payload)
            recurso_id = str(evento.recurso_externo_id or "")
        return payload, recurso_id

    async def _contar(self, *criterios: Any) -> int:
        quantidade = await self.session.scalar(
            select(func.count()).select_from(EventoProvedor).where(*criterios)
        )
        return int(quantidade or 0)

    @staticmethod
    def _identificador_trabalhador() -> str:
        return f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"[:100]

    async def _registrar_evento(
        self, evento_externo_id: str, recurso_id: str, payload: dict[str, Any]
    ) -> EventoProvedor:
        agora = datetime.now(UTC)
        async with self.session.begin():
            insercao = (
                pg_insert(EventoProvedor)
                .values(
                    provedor=ProvedorPagamento.MERCADO_PAGO,
                    evento_externo_id=evento_externo_id,
                    tipo=str(payload.get("action") or payload.get("type") or "unknown"),
                    recurso_externo_id=recurso_id,
                    payload=payload,
                    status_processamento=EventoProcessamentoStatus.PENDENTE,
                    tentativas=0,
                    ultima_tentativa_em=None,
                    proxima_tentativa_em=agora,
                    bloqueado_ate=None,
                    bloqueado_por=None,
                    processado_em=None,
                    erro=None,
                )
                .on_conflict_do_nothing(constraint="uq_eventos_provedor_externo")
                .returning(EventoProvedor.id)
            )
            evento_inserido_id = (await self.session.execute(insercao)).scalar_one_or_none()
            evento = await self.session.scalar(
                select(EventoProvedor).where(
                    EventoProvedor.provedor == ProvedorPagamento.MERCADO_PAGO,
                    EventoProvedor.evento_externo_id == evento_externo_id,
                )
            )
            evento_inconsistente = (
                evento_inserido_id is not None and evento.id != evento_inserido_id
                if evento is not None
                else False
            )
            if evento is None or evento_inconsistente:
                raise self._erro(
                    500,
                    "Não foi possível persistir o evento do provedor.",
                    "PROVIDER_EVENT_PERSISTENCE_FAILED",
                )
            if evento.recurso_externo_id != recurso_id:
                raise self._erro(
                    409,
                    "Identificador de evento reutilizado para outro recurso.",
                    "PROVIDER_EVENT_RESOURCE_MISMATCH",
                )
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
        self,
        evento_id: UUID,
        dados: dict[str, Any],
        vendedor_id: UUID,
        *,
        ordem_externa_id: str | None = None,
        trabalhador: str | None = None,
    ) -> tuple[UUID, UUID] | None:
        pedido_id = UUID(str(dados["external_reference"]))
        metadata = dados.get("metadata") or {}
        pagamento_id_texto = metadata.get("pagamento_id")
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
                return None
            if trabalhador and evento.bloqueado_por != trabalhador:
                raise self._erro(
                    409,
                    "O lease deste evento pertence a outro worker.",
                    "PROVIDER_EVENT_LEASE_LOST",
                )
            pedido = await self.session.scalar(
                select(Pedido).where(Pedido.id == pedido_id).with_for_update()
            )
            if pedido is None:
                raise self._erro(404, "Pedido do pagamento não encontrado.", "ORDER_NOT_FOUND")
            if ordem_externa_id:
                pagamento = await self.session.scalar(
                    select(Pagamento).where(
                        Pagamento.ordem_externa_id == ordem_externa_id,
                        Pagamento.pedido_id == pedido.id,
                    )
                )
            elif pagamento_id_texto:
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
            if ordem_externa_id and pagamento.ordem_externa_id != ordem_externa_id:
                raise self._erro(
                    409,
                    "Order do pagamento é inconsistente.",
                    "PAYMENT_ORDER_MISMATCH",
                )

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
            devolver = False
            if status_mp == "approved":
                if pagamento.status != PagamentoStatus.REEMBOLSADO:
                    devolver = self._aprovar(pedido, pagamento, anuncio, conta.id, dados, agora)
            elif status_mp in {"pending", "authorized"}:
                if pagamento.status not in {PagamentoStatus.APROVADO, PagamentoStatus.REEMBOLSADO}:
                    pagamento.status = PagamentoStatus.PENDENTE
            elif status_mp == "in_process":
                if pagamento.status not in {PagamentoStatus.APROVADO, PagamentoStatus.REEMBOLSADO}:
                    pagamento.status = PagamentoStatus.EM_PROCESSAMENTO
            elif status_mp == "rejected":
                if pagamento.status not in {PagamentoStatus.APROVADO, PagamentoStatus.REEMBOLSADO}:
                    pagamento.status = PagamentoStatus.RECUSADO
                    pagamento.motivo_recusa = pagamento.status_detalhe
            elif status_mp == "cancelled":
                if pagamento.status not in {PagamentoStatus.APROVADO, PagamentoStatus.REEMBOLSADO}:
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
                reembolso = await self.session.scalar(
                    select(Reembolso)
                    .where(Reembolso.pagamento_id == pagamento.id)
                    .with_for_update()
                )
                if reembolso is not None:
                    reembolso.status = ReembolsoStatus.CONCLUIDO
                    reembolso.processado_em = agora
                    reembolso.falhou_em = None
            else:
                evento.status_processamento = EventoProcessamentoStatus.IGNORADO
                evento.processado_em = agora
                evento.proxima_tentativa_em = None
                evento.bloqueado_ate = None
                evento.bloqueado_por = None
                return None
            if devolver:
                await self.session.flush()
                return pedido.id, pedido.comprador_id
            evento.status_processamento = EventoProcessamentoStatus.PROCESSADO
            evento.processado_em = agora
            evento.erro = None
            evento.proxima_tentativa_em = None
            evento.bloqueado_ate = None
            evento.bloqueado_por = None
            await self.session.flush()
        return None

    async def _processar_mp_connect(
        self,
        evento_id: UUID,
        payload: dict[str, Any],
        *,
        trabalhador: str | None = None,
    ) -> None:
        conta_externa_id = str(
            payload.get("user_id") or (payload.get("data") or {}).get("id") or ""
        )
        if not conta_externa_id:
            raise self._erro(
                400,
                "Webhook OAuth sem identificação do vendedor.",
                "MP_CONNECT_USER_MISSING",
            )
        acao = str(payload.get("action") or "")
        agora = datetime.now(UTC)
        async with self.session.begin():
            evento = await self.session.scalar(
                select(EventoProvedor).where(EventoProvedor.id == evento_id).with_for_update()
            )
            conta = await self.session.scalar(
                select(ContaPagamento)
                .where(
                    ContaPagamento.provedor == ProvedorPagamento.MERCADO_PAGO,
                    ContaPagamento.conta_externa_id == conta_externa_id,
                )
                .with_for_update()
            )
            if evento is None:
                raise self._erro(404, "Evento não encontrado.", "PROVIDER_EVENT_NOT_FOUND")
            if trabalhador and evento.bloqueado_por != trabalhador:
                raise self._erro(
                    409,
                    "O lease deste evento pertence a outro worker.",
                    "PROVIDER_EVENT_LEASE_LOST",
                )
            if acao == "application.deauthorized" and conta is not None:
                conta.status = ContaPagamentoStatus.DESCONECTADA
                conta.access_token_criptografado = None
                conta.refresh_token_criptografado = None
                conta.token_expira_em = None
            elif acao == "application.authorized" and conta is not None:
                if conta.access_token_criptografado:
                    conta.status = ContaPagamentoStatus.ATIVA
            elif acao not in {"application.authorized", "application.deauthorized"}:
                evento.status_processamento = EventoProcessamentoStatus.IGNORADO
                evento.processado_em = agora
                evento.proxima_tentativa_em = None
                evento.bloqueado_ate = None
                evento.bloqueado_por = None
                return
            evento.status_processamento = EventoProcessamentoStatus.PROCESSADO
            evento.processado_em = agora
            evento.erro = None
            evento.proxima_tentativa_em = None
            evento.bloqueado_ate = None
            evento.bloqueado_por = None

    @staticmethod
    def _normalizar_order(order: dict[str, Any], webhook: dict[str, Any]) -> dict[str, Any]:
        transacoes = order.get("transactions") or {}
        pagamentos = transacoes.get("payments") or []
        pagamento = pagamentos[0] if pagamentos else {}
        metodo = pagamento.get("payment_method") or {}
        order_status = str(order.get("status") or "")
        pagamento_status = str(pagamento.get("status") or "")
        status = "pending"
        if order_status == "processed" and pagamento_status in {"processed", "approved"}:
            status = "approved"
        elif order_status in {"failed"} or pagamento_status in {"failed", "rejected"}:
            status = "rejected"
        elif order_status in {"cancelled", "canceled"} or pagamento_status in {
            "cancelled",
            "canceled",
        }:
            status = "cancelled"
        elif order_status == "refunded" or pagamento_status == "refunded":
            status = "refunded"
        pagamento_externo_id = pagamento.get("reference_id") or pagamento.get("id") or order["id"]
        return {
            "id": str(pagamento_externo_id),
            "external_reference": order["external_reference"],
            "transaction_amount": order.get("total_amount"),
            "status": status,
            "status_detail": pagamento.get("status_detail") or order.get("status_detail"),
            "payment_type_id": metodo.get("type"),
            "payment_method_id": metodo.get("id"),
            "installments": metodo.get("installments"),
            "fee_details": [],
            "live_mode": bool(webhook.get("live_mode")),
        }

    def _aprovar(
        self,
        pedido: Pedido,
        pagamento: Pagamento,
        anuncio: Anuncio,
        conta_pagamento_id: UUID,
        dados: dict[str, Any],
        agora: datetime,
    ) -> bool:
        devolucao_necessaria = (
            pedido.status == PedidoStatus.CANCELADO or pedido.estoque_liberado_em is not None
        )
        if pagamento.status == PagamentoStatus.APROVADO:
            return devolucao_necessaria
        if pedido.status not in {
            PedidoStatus.AGUARDANDO_PAGAMENTO,
            PedidoStatus.CANCELADO,
        }:
            raise self._erro(
                409,
                "O pagamento foi aprovado depois que a reserva deixou de ser válida.",
                "PAYMENT_APPROVED_WITHOUT_RESERVATION",
            )
        pagamento.status = PagamentoStatus.APROVADO
        pagamento.aprovado_em = agora
        pedido.status = (
            PedidoStatus.CANCELADO if devolucao_necessaria else PedidoStatus.PAGAMENTO_APROVADO
        )
        if devolucao_necessaria:
            pedido.cancelado_em = pedido.cancelado_em or agora
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
        return devolucao_necessaria

    def _validar_dados(self, dados: dict[str, Any], pedido: Pedido) -> None:
        valor = Decimal(str(dados.get("transaction_amount"))).quantize(CENTAVOS)
        if valor != pedido.valor_total:
            raise self._erro(409, "Valor do pagamento é inconsistente.", "PAYMENT_AMOUNT_MISMATCH")
        # Contas de teste usam credenciais de produção, então seus pagamentos também
        # chegam com live_mode=true. Só o modo produtivo exige live_mode verdadeiro.
        live_mode = bool(dados.get("live_mode"))
        if self.settings.mp_live_mode and not live_mode:
            raise self._erro(
                409,
                "O modo do pagamento não corresponde ao modo configurado no backend.",
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
        reprocessavel: bool = False,
        trabalhador: str | None = None,
    ) -> None:
        if self.session.in_transaction():
            await self.session.rollback()
        async with self.session.begin():
            evento = await self.session.scalar(
                select(EventoProvedor)
                .where(EventoProvedor.id == evento_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if evento:
                if trabalhador and evento.bloqueado_por != trabalhador:
                    return
                if erro is not None and evento.status_processamento in {
                    EventoProcessamentoStatus.PROCESSADO,
                    EventoProcessamentoStatus.IGNORADO,
                }:
                    return
                evento.status_processamento = status
                evento.erro = erro
                agora = datetime.now(UTC)
                evento.processado_em = agora if erro is None else None
                evento.bloqueado_ate = None
                evento.bloqueado_por = None
                if erro is None:
                    evento.proxima_tentativa_em = None
                elif reprocessavel and evento.tentativas < self.settings.webhook_retry_max_attempts:
                    expoente = max(evento.tentativas - 1, 0)
                    espera = min(
                        self.settings.webhook_retry_base_seconds * (2**expoente),
                        self.settings.webhook_retry_max_seconds,
                    )
                    evento.proxima_tentativa_em = agora + timedelta(seconds=espera)
                else:
                    evento.proxima_tentativa_em = None

    @staticmethod
    def _texto_opcional(valor: object) -> str | None:
        return str(valor)[:100] if valor is not None else None

    @staticmethod
    def _erro(status: int, detail: str, code: str) -> AppError:
        return AppError(status_code=status, detail=detail, code=code)

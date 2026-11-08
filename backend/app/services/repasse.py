import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.provider_security import TokenCipher
from app.integrations.mercado_pago import MercadoPagoGateway, MercadoPagoIntegrationError
from app.integrations.payouts import PayoutsGateway, codigo_erro_provedor
from app.models.administrador import Administrador
from app.models.contestacao import Contestacao
from app.models.entrega import Entrega
from app.models.enums import (
    EntregaStatus,
    PagamentoStatus,
    PedidoStatus,
    ReembolsoStatus,
    RepasseStatus,
)
from app.models.operacao_repasse import DestinoRepasse, EventoRepasse, InstrucaoRepasse
from app.models.pagamento import Pagamento
from app.models.pedido import MODELO_REPASSE_POSTERIOR, Pedido
from app.models.reembolso import Reembolso
from app.models.repasse import Repasse
from app.models.usuario import Usuario
from app.schemas.repasse import (
    DestinoRepasseCreate,
    DestinoRepasseResponse,
    RepasseListResponse,
    RepasseResponse,
)
from app.services.contestacao import STATUS_ATIVOS
from app.services.credencial_pagamento import token_marketplace

logger = logging.getLogger(__name__)

# Repasses do modelo posterior que ainda aguardam a liberação ao vendedor.
STATUS_PRE_LIBERACAO = frozenset(
    {
        RepasseStatus.AGUARDANDO_ENTREGA,
        RepasseStatus.EM_PERIODO_CONTESTACAO,
        RepasseStatus.PRONTO_PARA_LIBERACAO,
    }
)
STATUS_LIBERAVEIS = STATUS_PRE_LIBERACAO | {RepasseStatus.PROCESSANDO}


class RepasseService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        gateway: PayoutsGateway | None = None,
        pagamentos_gateway: MercadoPagoGateway | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.gateway = gateway or PayoutsGateway(self.settings)
        self.pagamentos_gateway = pagamentos_gateway or MercadoPagoGateway(
            self.settings.mercado_pago_api_url
        )

    def _cipher(self) -> TokenCipher:
        chave = self.settings.mp_token_encryption_key
        if not chave:
            raise self._erro(
                503, "Configure a criptografia dos dados financeiros.", "PAYOUT_CIPHER_MISSING"
            )
        return TokenCipher(chave.get_secret_value())

    async def _validar_admin(self, operador_id: UUID) -> None:
        autorizado = await self.session.scalar(
            select(Usuario.id)
            .join(Administrador, Administrador.usuario_id == Usuario.id)
            .where(
                Usuario.id == operador_id, Usuario.status == "ATIVO", Usuario.deletado_em.is_(None)
            )
        )
        if autorizado is None:
            raise self._erro(403, "Acesso restrito a administradores ativos.", "PAYOUT_FORBIDDEN")

    async def cadastrar_destino(
        self, vendedor_id: UUID, dados: DestinoRepasseCreate, operador_id: UUID
    ) -> DestinoRepasseResponse:
        async with self.session.begin():
            await self._validar_admin(operador_id)
            if dados.tipo_chave == "CONTA_MP_TESTE":
                self._validar_conta_teste()
            vendedor = await self.session.scalar(
                select(Usuario).where(Usuario.id == vendedor_id).with_for_update()
            )
            if vendedor is None or vendedor.deletado_em is not None:
                raise self._erro(404, "Vendedor não encontrado.", "SELLER_NOT_FOUND")
            destino = await self.session.scalar(
                select(DestinoRepasse).where(DestinoRepasse.vendedor_id == vendedor_id)
            )
            if destino is None:
                destino = DestinoRepasse(vendedor_id=vendedor_id)
                self.session.add(destino)
            destino.tipo_chave = dados.tipo_chave
            destino.chave_criptografada = self._cipher().encrypt(dados.chave)
            destino.validado_por = operador_id
            destino.validado_em = datetime.now(UTC)
            destino.ativo = True
            repasses = await self.session.scalars(
                select(Repasse).where(Repasse.vendedor_id == vendedor_id)
            )
            for repasse in repasses:
                self._auditar(
                    repasse,
                    "DESTINO_CONTA_TESTE_CONFERIDO"
                    if dados.tipo_chave == "CONTA_MP_TESTE"
                    else "DESTINO_PIX_CONFERIDO",
                    operador_id,
                )
            await self.session.flush()
            return DestinoRepasseResponse(
                vendedor_id=vendedor_id,
                tipo_chave=destino.tipo_chave,
                validado_em=destino.validado_em,
                ativo=destino.ativo,
            )

    def _conta_teste_permitida(self) -> bool:
        return (
            self.settings.environment in {"local", "test"}
            and self.settings.mp_payouts_test_mode
            and not self.settings.mp_live_mode
        )

    def _validar_conta_teste(self, valor: Decimal | None = None) -> None:
        if not self._conta_teste_permitida():
            raise self._erro(
                409,
                "Transferência por e-mail de teste exige ambiente local/test e Payouts de teste.",
                "PAYOUT_TEST_ACCOUNT_ONLY",
            )
        if valor is not None and (
            not valor.is_finite()
            or valor <= 0
            or valor > self.settings.mp_payouts_test_account_max_amount
        ):
            raise self._erro(
                409,
                "O valor ultrapassa o limite configurado para repasse entre contas de teste.",
                "PAYOUT_TEST_AMOUNT_LIMIT",
            )

    def _dispensar_prazo_teste(self) -> bool:
        return (
            self.settings.mp_payouts_test_skip_wait
            and self.settings.environment in {"local", "test"}
            and self.settings.mp_payouts_test_mode
            and not self.settings.mp_live_mode
        )

    async def _dispensar_prazo_pedido_teste(self, repasse_id: UUID) -> bool:
        # Excecao operacional por pedido; nunca se aplica em staging/producao.
        if self.settings.environment not in {"local", "test"}:
            return False
        acao = await self.session.scalar(
            select(EventoRepasse.acao)
            .where(
                EventoRepasse.repasse_id == repasse_id,
                EventoRepasse.acao.in_(
                    {"AUTORIZACAO_PRAZO_PEDIDO_TESTE", "REVOGACAO_PRAZO_PEDIDO_TESTE"}
                ),
            )
            .order_by(EventoRepasse.criado_em.desc(), EventoRepasse.id.desc())
            .limit(1)
        )
        return acao == "AUTORIZACAO_PRAZO_PEDIDO_TESTE"

    async def _fim_periodo_contestacao(self, entrega: Entrega, repasse_id: UUID) -> datetime:
        assert entrega.confirmado_em is not None and entrega.prazo_contestacao_em is not None
        if self._dispensar_prazo_teste() or await self._dispensar_prazo_pedido_teste(repasse_id):
            return entrega.confirmado_em
        return max(entrega.prazo_contestacao_em, entrega.confirmado_em + timedelta(days=7))

    async def _motivo(
        self, repasse: Repasse, pedido: Pedido, *, exigir_destino: bool = True
    ) -> str | None:
        if not pedido.repasse_posterior:
            return "Venda com split legado; não executar outra transferência."
        if repasse.status not in STATUS_LIBERAVEIS:
            return "O estado do repasse não permite liberação."
        if pedido.status != PedidoStatus.ENTREGUE:
            return "O pedido precisa estar entregue."
        entrega = await self.session.scalar(select(Entrega).where(Entrega.pedido_id == pedido.id))
        if (
            entrega is None
            or entrega.status != EntregaStatus.ENTREGUE
            or entrega.confirmado_em is None
            or entrega.prazo_contestacao_em is None
        ):
            return "A entrega precisa estar confirmada com prazo de contestação."
        if entrega.confirmado_por != repasse.vendedor_id:
            return "A entrega precisa ter sido confirmada pelo vendedor."
        fim_periodo = await self._fim_periodo_contestacao(entrega, repasse.id)
        if datetime.now(UTC) <= fim_periodo:
            return "O período de contestação ainda não terminou."
        if await self.session.scalar(
            select(Contestacao.id).where(
                Contestacao.pedido_id == pedido.id, Contestacao.status.in_(STATUS_ATIVOS)
            )
        ):
            return "Existe uma contestação ativa."
        if await self.session.scalar(
            select(Reembolso.id).where(
                Reembolso.pedido_id == pedido.id, Reembolso.status != ReembolsoStatus.CANCELADO
            )
        ):
            return "Existe uma solicitação de reembolso."
        pagamento = await self.session.get(Pagamento, repasse.pagamento_id)
        if pagamento is None or pagamento.status != PagamentoStatus.APROVADO:
            return "O pagamento precisa estar aprovado."
        vendedor = await self.session.get(Usuario, repasse.vendedor_id)
        if vendedor is None or vendedor.status != "ATIVO" or vendedor.deletado_em is not None:
            return "O vendedor precisa estar ativo."
        destino = await self.session.scalar(
            select(DestinoRepasse).where(
                DestinoRepasse.vendedor_id == repasse.vendedor_id, DestinoRepasse.ativo.is_(True)
            )
        )
        if exigir_destino and destino is None:
            return "Cadastre e confira o destino Pix do vendedor."
        if destino and destino.tipo_chave == "CONTA_MP_TESTE":
            try:
                self._validar_conta_teste(repasse.valor_liquido)
            except AppError as exc:
                return exc.detail
        return None

    async def atualizar_estados(self) -> int:
        ids = list(
            await self.session.scalars(
                select(Repasse.id)
                .join(Pedido)
                .where(
                    Pedido.modelo_financeiro == MODELO_REPASSE_POSTERIOR,
                    Repasse.status.in_(STATUS_PRE_LIBERACAO),
                )
                .order_by(Repasse.criado_em)
                .limit(500)
            )
        )
        await self.session.rollback()
        alterados = 0
        for repasse_id in ids:
            async with self.session.begin():
                pedido_id = await self.session.scalar(
                    select(Repasse.pedido_id).where(Repasse.id == repasse_id)
                )
                pedido = await self.session.scalar(
                    select(Pedido)
                    .where(Pedido.id == pedido_id)
                    .with_for_update(skip_locked=True)
                    .execution_options(populate_existing=True)
                )
                if pedido is None:
                    continue
                repasse = await self.session.scalar(
                    select(Repasse)
                    .where(Repasse.id == repasse_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if repasse is None or repasse.status not in STATUS_PRE_LIBERACAO:
                    continue
                entrega = await self.session.scalar(
                    select(Entrega).where(Entrega.pedido_id == pedido.id)
                )
                if (
                    pedido.status != PedidoStatus.ENTREGUE
                    or entrega is None
                    or entrega.confirmado_em is None
                    or entrega.prazo_contestacao_em is None
                    or entrega.status != EntregaStatus.ENTREGUE
                ):
                    continue
                novo = RepasseStatus.EM_PERIODO_CONTESTACAO
                fim_periodo = await self._fim_periodo_contestacao(entrega, repasse.id)
                if datetime.now(UTC) > fim_periodo:
                    if await self._motivo(repasse, pedido, exigir_destino=False):
                        continue
                    novo = RepasseStatus.PRONTO_PARA_LIBERACAO
                repasse.liberacao_prevista_em = entrega.prazo_contestacao_em
                if repasse.status != novo:
                    repasse.status = novo
                    self._auditar(repasse, "ATUALIZACAO_DE_PRAZO", None)
                    alterados += 1
        return alterados

    async def _resposta(self, repasse: Repasse, pedido: Pedido) -> RepasseResponse:
        vendedor = await self.session.get(Usuario, repasse.vendedor_id)
        destino = await self.session.scalar(
            select(DestinoRepasse).where(
                DestinoRepasse.vendedor_id == repasse.vendedor_id, DestinoRepasse.ativo.is_(True)
            )
        )
        motivo = await self._motivo(repasse, pedido)
        instrucao = await self.session.scalar(
            select(InstrucaoRepasse).where(InstrucaoRepasse.repasse_id == repasse.id)
        )
        if repasse.status == RepasseStatus.PROCESSANDO:
            if (
                motivo is None
                and instrucao
                and not instrucao.recurso_externo_id
                and (instrucao.lease_ate is None or instrucao.lease_ate <= datetime.now(UTC))
            ):
                motivo = None  # Retomada reutiliza a mesma instrucao e chave persistidas.
            elif instrucao and not instrucao.recurso_externo_id and motivo is None:
                motivo = (
                    "Envio sem identificação confirmada. Aguarde o bloqueio temporário "
                    "de dois minutos e atualize os repasses para retomar a mesma instrução."
                )
            else:
                motivo = motivo or (
                    "Transferência em processamento; consulte o estado antes de qualquer ação."
                )
        return RepasseResponse(
            id=repasse.id,
            pedido_id=pedido.id,
            vendedor_id=repasse.vendedor_id,
            vendedor_nome=vendedor.nome if vendedor else "Vendedor",
            modelo_financeiro=pedido.modelo_financeiro,
            valor_bruto=repasse.valor_bruto,
            percentual_marketplace=repasse.percentual_marketplace,
            taxa_marketplace=repasse.taxa_marketplace,
            taxa_provedor=repasse.taxa_provedor,
            valor_liquido=repasse.valor_liquido,
            taxas_por_conta_marketplace=repasse.taxas_por_conta_marketplace,
            status=repasse.status,
            liberacao_prevista_em=repasse.liberacao_prevista_em,
            pago_em=repasse.pago_em,
            destino_cadastrado=destino is not None,
            pode_liberar=motivo is None,
            pode_consultar=bool(instrucao and instrucao.recurso_externo_id),
            destino_tipo=destino.tipo_chave if destino else None,
            motivo_bloqueio=motivo,
        )

    async def listar(
        self, *, status: RepasseStatus | None = None, offset: int = 0, limit: int = 50
    ) -> RepasseListResponse:
        query = select(Repasse).order_by(Repasse.criado_em.desc(), Repasse.id)
        count = select(func.count()).select_from(Repasse)
        if status:
            query = query.where(Repasse.status == status)
            count = count.where(Repasse.status == status)
        total = int(await self.session.scalar(count) or 0)
        repasses = await self.session.scalars(query.offset(offset).limit(limit))
        items = []
        for repasse in repasses:
            pedido = await self.session.get(Pedido, repasse.pedido_id)
            if pedido is not None:
                items.append(await self._resposta(repasse, pedido))
        return RepasseListResponse(items=items, total=total, offset=offset, limit=limit)

    async def _preparar(self, repasse_id: UUID, operador_id: UUID) -> UUID:
        self.gateway.validar_configuracao()
        async with self.session.begin():
            await self._validar_admin(operador_id)
            pedido_id = await self.session.scalar(
                select(Repasse.pedido_id).where(Repasse.id == repasse_id)
            )
            pedido = await self.session.scalar(
                select(Pedido)
                .where(Pedido.id == pedido_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            repasse = await self.session.scalar(
                select(Repasse)
                .where(Repasse.id == repasse_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if repasse is None or pedido is None:
                raise self._erro(404, "Repasse não encontrado.", "PAYOUT_NOT_FOUND")
            motivo = await self._motivo(repasse, pedido)
            if motivo:
                raise self._erro(409, motivo, "PAYOUT_NOT_ELIGIBLE")
            if pedido.recebedor_externo_id != self.settings.mp_marketplace_user_id:
                raise self._erro(
                    409, "A conta recebedora da venda mudou.", "PAYOUT_COLLECTOR_MISMATCH"
                )
            instrucao = await self.session.scalar(
                select(InstrucaoRepasse)
                .where(InstrucaoRepasse.repasse_id == repasse_id)
                .with_for_update()
            )
            agora = datetime.now(UTC)
            if instrucao and instrucao.lease_ate and instrucao.lease_ate > agora:
                raise self._erro(
                    409, "Este repasse já está sendo processado.", "PAYOUT_IN_PROGRESS"
                )
            if instrucao is None:
                destino = await self.session.scalar(
                    select(DestinoRepasse)
                    .where(DestinoRepasse.vendedor_id == repasse.vendedor_id)
                    .with_for_update()
                )
                assert destino is not None
                transacao: dict[str, object] = {
                    "description": "Repasse ao vendedor",
                    "amount": {"currency": "BRL", "value": float(repasse.valor_liquido)},
                    "external_reference": f"venda-{pedido.id.hex}",
                }
                if destino.tipo_chave == "CONTA_MP_TESTE":
                    self._validar_conta_teste(repasse.valor_liquido)
                    transacao.update(
                        {
                            "type": "account",
                            "account": {
                                "email": self._cipher().decrypt(destino.chave_criptografada)
                            },
                        }
                    )
                else:
                    transacao.update(
                        {
                            "type": "pix",
                            "pix": {
                                "type": destino.tipo_chave,
                                "chave": self._cipher().decrypt(destino.chave_criptografada),
                            },
                        }
                    )
                corpo = {
                    "external_reference": f"repasse-{repasse.id.hex}",
                    "config": {"notification_url": self.settings.mp_payouts_notification_url},
                    "description": "Repasse Obra Circular",
                    "transactions": [transacao],
                }
                instrucao = InstrucaoRepasse(
                    repasse_id=repasse.id,
                    idempotency_key=str(uuid4()),
                    corpo_criptografado=self._cipher().encrypt(json.dumps(corpo)),
                    solicitado_por=operador_id,
                    test_mode=self.settings.mp_payouts_test_mode,
                )
                self.session.add(instrucao)
                if self._dispensar_prazo_teste() or await self._dispensar_prazo_pedido_teste(
                    repasse.id
                ):
                    self._auditar(repasse, "PRAZO_DISPENSADO_EM_TESTE", operador_id)
            elif instrucao.test_mode != self.settings.mp_payouts_test_mode:
                raise self._erro(
                    409, "A instrução pertence a outro ambiente.", "PAYOUT_MODE_MISMATCH"
                )
            instrucao.lease_ate = agora + timedelta(minutes=2)
            repasse.status = RepasseStatus.PROCESSANDO
            repasse.liberado_em = repasse.liberado_em or agora
            repasse.tentativas += 1
            self._auditar(repasse, "LIBERACAO_SOLICITADA", operador_id)
            await self.session.flush()
            return instrucao.id

    async def liberar(self, repasse_id: UUID, operador_id: UUID) -> RepasseResponse:
        instrucao_id = await self._preparar(repasse_id, operador_id)
        instrucao = await self.session.get(InstrucaoRepasse, instrucao_id)
        assert instrucao is not None
        recurso_id = instrucao.recurso_externo_id
        key = instrucao.idempotency_key
        corpo = json.loads(self._cipher().decrypt(instrucao.corpo_criptografado))
        await self.session.rollback()
        fase = "configuracao"
        try:
            for transacao in corpo.get("transactions", []):
                if transacao.get("type") == "account":
                    self._validar_conta_teste(Decimal(str(transacao["amount"]["value"])))
            fase = "recebimento"
            if recurso_id is None:
                await self._verificar_recebimento(repasse_id)
                fase = "envio"
                resultado = await self.gateway.criar(corpo, key)
                recurso_id = str(resultado.get("id") or "")
                if not recurso_id:
                    raise MercadoPagoIntegrationError(
                        "Identificador do repasse não foi confirmado."
                    )
                async with self.session.begin():
                    atual = await self.session.scalar(
                        select(InstrucaoRepasse)
                        .where(InstrucaoRepasse.id == instrucao_id)
                        .with_for_update()
                    )
                    assert atual is not None
                    atual.recurso_externo_id = recurso_id
            fase = "consulta"
            return await self.conciliar(repasse_id, operador_id)
        except (MercadoPagoIntegrationError, AppError) as exc:
            # Resultado incerto permanece PROCESSANDO. Nunca gerar uma nova chave.
            http = exc.status_code if isinstance(exc, MercadoPagoIntegrationError) else None
            codigo = (
                codigo_erro_provedor(exc.payload)
                if isinstance(exc, MercadoPagoIntegrationError)
                else exc.code
            )
            logger.warning(
                "Falha no repasse %s: fase=%s http=%s codigo=%s",
                repasse_id,
                fase,
                http,
                codigo,
            )
            if self.session.in_transaction():
                await self.session.rollback()
            async with self.session.begin():
                repasse = await self.session.get(Repasse, repasse_id)
                if repasse:
                    self._auditar(repasse, "CONFIRMACAO_PENDENTE", operador_id)
                    self._auditar(
                        repasse,
                        f"ERRO_{fase.upper()}" + (f"_HTTP_{http}" if http else ""),
                        operador_id,
                    )
            if fase == "recebimento":
                detalhe = (
                    exc.detail
                    if isinstance(exc, AppError)
                    else "Não foi possível consultar o pagamento no Mercado Pago."
                )
                raise self._erro(
                    409,
                    f"A verificação do recebimento impediu esta tentativa de envio. {detalhe}",
                    "PAYOUT_RECEIPT_CHECK_FAILED",
                ) from None
            if isinstance(exc, AppError):
                raise exc from None
            raise self._erro_provedor(exc, fase) from None

    def _erro_provedor(self, exc: MercadoPagoIntegrationError, fase: str) -> AppError:
        if exc.status_code is not None:
            codigo = codigo_erro_provedor(exc.payload)
            operacao = "o envio" if fase == "envio" else "a consulta"
            detalhe = (
                f"O Mercado Pago retornou erro durante {operacao} do repasse "
                f"(HTTP {exc.status_code}"
            )
            detalhe += f", {codigo}). " if codigo else "). "
            detalhe += (
                "Confira as credenciais e a habilitação de Payouts da conta de origem. "
                if exc.status_code in {401, 403}
                else "Confira a configuração e os dados da operação. "
            )
            detalhe += "A instrução original foi preservada; não há confirmação de crédito."
            return self._erro(409, detalhe, "PAYOUT_PROVIDER_ERROR")
        return self._erro(
            409,
            (
                "Repasse sem confirmação. Atualize os repasses e retome a mesma instrução "
                "após o bloqueio temporário."
                if fase == "envio"
                else "Repasse sem confirmação. Consulte novamente o estado no provedor."
            ),
            "PAYOUT_CONFIRMATION_PENDING",
        )

    async def _verificar_recebimento(self, repasse_id: UUID) -> None:
        repasse = await self.session.get(Repasse, repasse_id)
        assert repasse is not None
        pagamento = await self.session.get(Pagamento, repasse.pagamento_id)
        pedido = await self.session.get(Pedido, repasse.pedido_id)
        assert pagamento is not None and pedido is not None
        externo_id = pagamento.pagamento_externo_id
        valor = pedido.valor_total
        recebedor = pedido.recebedor_externo_id
        await self.session.rollback()
        if not externo_id:
            raise self._erro(409, "Pagamento externo não identificado.", "PAYOUT_PAYMENT_MISSING")
        dados = (
            await self.pagamentos_gateway.obter_pagamento(
                access_token=token_marketplace(self.settings), pagamento_externo_id=externo_id
            )
        ).data
        if (
            dados.get("status") != "approved"
            or str(dados.get("collector_id")) != recebedor
            or Decimal(str(dados.get("transaction_amount"))) != valor
            or Decimal(str(dados.get("transaction_amount_refunded") or 0)) != 0
        ):
            raise self._erro(
                409, "Recebimento não está disponível para repasse.", "PAYOUT_PAYMENT_NOT_AVAILABLE"
            )
        if dados.get("money_release_status") not in {None, "released"}:
            raise self._erro(
                409, "O provedor ainda não liberou o recebimento.", "PAYOUT_PAYMENT_NOT_AVAILABLE"
            )
        if dados.get("money_release_date"):
            data = datetime.fromisoformat(str(dados["money_release_date"]).replace("Z", "+00:00"))
            if data.tzinfo is None or data > datetime.now(UTC):
                raise self._erro(
                    409, "O recebimento ainda não está disponível.", "PAYOUT_PAYMENT_NOT_AVAILABLE"
                )

    async def conciliar(self, repasse_id: UUID, operador_id: UUID | None = None) -> RepasseResponse:
        if operador_id:
            await self._validar_admin(operador_id)
        instrucao = await self.session.scalar(
            select(InstrucaoRepasse).where(InstrucaoRepasse.repasse_id == repasse_id)
        )
        if instrucao is None or not instrucao.recurso_externo_id:
            await self.session.rollback()
            raise self._erro(
                409,
                "O envio ainda não possui identificação confirmada para consulta. "
                "Atualize os repasses e, após o bloqueio temporário, retome a mesma instrução.",
                "PAYOUT_REMOTE_ID_PENDING",
            )
        if instrucao.test_mode != self.settings.mp_payouts_test_mode:
            await self.session.rollback()
            raise self._erro(409, "A instrução pertence a outro ambiente.", "PAYOUT_MODE_MISMATCH")
        recurso_id = instrucao.recurso_externo_id
        instrucao_id = instrucao.id
        corpo = json.loads(self._cipher().decrypt(instrucao.corpo_criptografado))
        await self.session.rollback()
        try:
            recebido = await self.gateway.consultar(recurso_id)
        except MercadoPagoIntegrationError as exc:
            logger.warning(
                "Falha na consulta do repasse %s: http=%s codigo=%s",
                repasse_id,
                exc.status_code,
                codigo_erro_provedor(exc.payload),
            )
            raise self._erro_provedor(exc, "consulta") from None
        transacoes = recebido.get("transactions") or []
        if len(transacoes) != 1:
            raise self._erro(
                409, "O provedor não retornou a transferência esperada.", "PAYOUT_DATA_MISMATCH"
            )
        transacao = transacoes[0]
        esperado = corpo["transactions"][0]
        if (
            transacao.get("external_reference") != esperado["external_reference"]
            or transacao.get("amount", {}).get("currency") != "BRL"
            or Decimal(str(transacao.get("amount", {}).get("value")))
            != Decimal(str(esperado["amount"]["value"]))
        ):
            raise self._erro(
                409, "Valor ou referência da transferência divergem.", "PAYOUT_DATA_MISMATCH"
            )
        async with self.session.begin():
            pedido_id = await self.session.scalar(
                select(Repasse.pedido_id).where(Repasse.id == repasse_id)
            )
            pedido = await self.session.scalar(
                select(Pedido)
                .where(Pedido.id == pedido_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            repasse = await self.session.scalar(
                select(Repasse)
                .where(Repasse.id == repasse_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            instrucao = await self.session.scalar(
                select(InstrucaoRepasse)
                .where(InstrucaoRepasse.id == instrucao_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            assert pedido is not None and repasse is not None and instrucao is not None
            status = str(transacao.get("status") or "")
            detalhe = str(transacao.get("status_detail") or "")
            if (
                instrucao.transferencia_externa_id is not None
                and instrucao.transferencia_externa_id != str(transacao["id"])
            ):
                raise self._erro(
                    409, "Identificador da transferência diverge.", "PAYOUT_DATA_MISMATCH"
                )
            instrucao.transferencia_externa_id = str(transacao["id"])
            instrucao.status_provedor = status + ":" + detalhe
            instrucao.lease_ate = None
            if status == "refunded" or detalhe == "partially_refunded":
                repasse.status = RepasseStatus.FALHOU
                self._auditar(repasse, "TRANSFERENCIA_DEVOLVIDA", operador_id)
            elif repasse.status != RepasseStatus.PAGO:
                if (status, detalhe) in {("success", "accredited"), ("processed", "approved")}:
                    repasse.status = RepasseStatus.PAGO
                    repasse.pago_em = datetime.now(UTC)
                    repasse.repasse_externo_id = str(transacao["id"])
                    if pedido.status == PedidoStatus.ENTREGUE:
                        pedido.status = PedidoStatus.CONCLUIDO
                        pedido.concluido_em = repasse.pago_em
                elif status in {"error", "rejected", "canceled", "refunded"}:
                    repasse.status = RepasseStatus.FALHOU
                self._auditar(repasse, "CONCILIACAO_" + status[:40], operador_id)
            await self.session.flush()
            return await self._resposta(repasse, pedido)

    async def conciliar_recurso(self, recurso_id: str) -> None:
        repasse_id = await self.session.scalar(
            select(InstrucaoRepasse.repasse_id).where(
                InstrucaoRepasse.recurso_externo_id == recurso_id
            )
        )
        await self.session.rollback()
        if repasse_id is None:
            raise self._erro(404, "Instrução de repasse não encontrada.", "PAYOUT_NOT_FOUND")
        await self.conciliar(repasse_id)

    def _auditar(self, repasse: Repasse, acao: str, operador_id: UUID | None) -> None:
        self.session.add(
            EventoRepasse(
                repasse_id=repasse.id, operador_id=operador_id, acao=acao, status=repasse.status
            )
        )

    @staticmethod
    def _erro(status: int, detail: str, code: str) -> AppError:
        return AppError(status_code=status, detail=detail, code=code)

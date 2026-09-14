from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MetodoPagamento, PagamentoStatus, ProvedorPagamento


class Pagamento(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pagamentos"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_pagamentos_idempotency_key"),
        UniqueConstraint("provedor", "pagamento_externo_id", name="uq_pagamentos_provedor_externo"),
        CheckConstraint("provedor IN ('MERCADO_PAGO')", name="ck_pagamentos_provedor"),
        CheckConstraint(
            "metodo IN ('PIX', 'CARTAO_CREDITO', 'CARTAO_DEBITO', 'BOLETO')",
            name="ck_pagamentos_metodo",
        ),
        CheckConstraint("valor > 0", name="ck_pagamentos_valor"),
        CheckConstraint(
            "((metodo = 'CARTAO_CREDITO' AND parcelas IS NOT NULL AND parcelas > 0) "
            "OR (metodo <> 'CARTAO_CREDITO' AND parcelas IS NULL))",
            name="ck_pagamentos_parcelas",
        ),
        CheckConstraint(
            "status IN ('CRIADO', 'PENDENTE', 'EM_PROCESSAMENTO', 'APROVADO', "
            "'RECUSADO', 'CANCELADO', 'REEMBOLSADO_PARCIAL', 'REEMBOLSADO')",
            name="ck_pagamentos_status",
        ),
        Index("ix_pagamentos_pedido_id", "pedido_id"),
        Index("ix_pagamentos_status", "status"),
        Index(
            "uq_pagamentos_um_aprovado_por_pedido",
            "pedido_id",
            unique=True,
            postgresql_where=text("status IN ('APROVADO', 'REEMBOLSADO_PARCIAL', 'REEMBOLSADO')"),
        ),
    )

    pedido_id: Mapped[UUID] = mapped_column(ForeignKey("pedidos.id", name="fk_pagamentos_pedido"))
    provedor: Mapped[ProvedorPagamento] = mapped_column(
        String(30),
        default=ProvedorPagamento.MERCADO_PAGO,
        server_default=ProvedorPagamento.MERCADO_PAGO.value,
    )
    pagamento_externo_id: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    metodo: Mapped[MetodoPagamento] = mapped_column(String(30))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    parcelas: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[PagamentoStatus] = mapped_column(
        String(30),
        default=PagamentoStatus.CRIADO,
        server_default=PagamentoStatus.CRIADO.value,
    )
    motivo_recusa: Mapped[str | None] = mapped_column(String(255))
    aprovado_em: Mapped[datetime | None]
    cancelado_em: Mapped[datetime | None]

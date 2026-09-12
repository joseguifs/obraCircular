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
from app.models.enums import RepasseStatus


class Repasse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "repasses"
    __table_args__ = (
        UniqueConstraint("pedido_id", name="uq_repasses_pedido"),
        UniqueConstraint("pagamento_id", name="uq_repasses_pagamento"),
        UniqueConstraint("repasse_externo_id", name="uq_repasses_externo"),
        CheckConstraint(
            "valor_bruto >= 0 AND taxa_provedor >= 0 AND taxa_marketplace >= 0 "
            "AND valor_liquido >= 0 "
            "AND valor_liquido = ROUND(valor_bruto - taxa_provedor - taxa_marketplace, 2)",
            name="ck_repasses_valores",
        ),
        CheckConstraint(
            "percentual_marketplace BETWEEN 0 AND 100",
            name="ck_repasses_percentual",
        ),
        CheckConstraint("tentativas >= 0", name="ck_repasses_tentativas"),
        CheckConstraint(
            "status IN ('AGUARDANDO_ENTREGA', 'EM_PERIODO_CONTESTACAO', 'BLOQUEADO', "
            "'PRONTO_PARA_LIBERACAO', 'PROCESSANDO', 'PAGO', 'FALHOU', 'CANCELADO', "
            "'REEMBOLSADO')",
            name="ck_repasses_status",
        ),
        Index("ix_repasses_vendedor_id", "vendedor_id"),
        Index("ix_repasses_status", "status"),
        Index(
            "ix_repasses_liberacao_pendente",
            "liberacao_prevista_em",
            postgresql_where=text("status = 'EM_PERIODO_CONTESTACAO'"),
        ),
    )

    pedido_id: Mapped[UUID] = mapped_column(ForeignKey("pedidos.id", name="fk_repasses_pedido"))
    pagamento_id: Mapped[UUID] = mapped_column(
        ForeignKey("pagamentos.id", name="fk_repasses_pagamento")
    )
    vendedor_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", name="fk_repasses_vendedor")
    )
    conta_pagamento_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("contas_pagamento.id", name="fk_repasses_conta_pagamento")
    )
    valor_bruto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    taxa_provedor: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default="0")
    taxa_marketplace: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default="0")
    valor_liquido: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    percentual_marketplace: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=0, server_default="0"
    )
    status: Mapped[RepasseStatus] = mapped_column(
        String(30),
        default=RepasseStatus.AGUARDANDO_ENTREGA,
        server_default=RepasseStatus.AGUARDANDO_ENTREGA.value,
    )
    liberacao_prevista_em: Mapped[datetime | None]
    repasse_externo_id: Mapped[str | None] = mapped_column(String(255))
    tentativas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    liberado_em: Mapped[datetime | None]
    pago_em: Mapped[datetime | None]
    bloqueado_em: Mapped[datetime | None]

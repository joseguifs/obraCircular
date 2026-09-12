from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import ModalidadeEntrega, PedidoStatus


class Pedido(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "pedidos"
    __table_args__ = (
        ForeignKeyConstraint(
            ["endereco_entrega_id", "comprador_id"],
            ["enderecos.id", "enderecos.usuario_id"],
            name="fk_pedidos_endereco_comprador",
        ),
        CheckConstraint(
            "modalidade_entrega IN ('ENTREGA', 'RETIRADA')",
            name="ck_pedidos_modalidade",
        ),
        CheckConstraint(
            "((modalidade_entrega = 'ENTREGA' AND endereco_entrega_id IS NOT NULL "
            "AND endereco_entrega_snapshot IS NOT NULL) OR "
            "(modalidade_entrega = 'RETIRADA' AND endereco_entrega_id IS NULL "
            "AND endereco_entrega_snapshot IS NULL))",
            name="ck_pedidos_endereco_entrega",
        ),
        CheckConstraint("quantidade > 0", name="ck_pedidos_quantidade"),
        CheckConstraint("preco_unitario >= 0", name="ck_pedidos_preco_unitario"),
        CheckConstraint("valor_total >= 0", name="ck_pedidos_valor_total"),
        CheckConstraint(
            "valor_total = ROUND(quantidade * preco_unitario, 2)",
            name="ck_pedidos_calculo_total",
        ),
        CheckConstraint(
            "status IN ('AGUARDANDO_PAGAMENTO', 'PAGAMENTO_APROVADO', "
            "'PREPARANDO_ENTREGA', 'EM_ENTREGA', 'ENTREGUE', 'EM_CONTESTACAO', "
            "'CONCLUIDO', 'CANCELADO', 'REEMBOLSADO')",
            name="ck_pedidos_status",
        ),
        Index("ix_pedidos_comprador_id", "comprador_id"),
        Index("ix_pedidos_anuncio_id", "anuncio_id"),
        Index("ix_pedidos_status", "status"),
        Index("ix_pedidos_criado_em", text("criado_em DESC")),
    )

    comprador_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", name="fk_pedidos_comprador")
    )
    anuncio_id: Mapped[UUID] = mapped_column(ForeignKey("anuncios.id", name="fk_pedidos_anuncio"))
    endereco_entrega_id: Mapped[UUID | None]
    endereco_entrega_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    modalidade_entrega: Mapped[ModalidadeEntrega] = mapped_column(
        String(20),
        default=ModalidadeEntrega.ENTREGA,
        server_default=ModalidadeEntrega.ENTREGA.value,
    )
    quantidade: Mapped[int] = mapped_column(Integer)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[PedidoStatus] = mapped_column(
        String(30),
        default=PedidoStatus.AGUARDANDO_PAGAMENTO,
        server_default=PedidoStatus.AGUARDANDO_PAGAMENTO.value,
    )
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )
    concluido_em: Mapped[datetime | None]
    cancelado_em: Mapped[datetime | None]

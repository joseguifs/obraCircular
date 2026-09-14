from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ContestacaoMotivo, ContestacaoStatus


class Contestacao(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contestacoes"
    __table_args__ = (
        CheckConstraint(
            "motivo IN ('PEDIDO_NAO_RECEBIDO', 'PRODUTO_DANIFICADO', "
            "'QUANTIDADE_INCORRETA', 'PRODUTO_DIFERENTE', 'ENTREGA_PARCIAL', 'OUTRO')",
            name="ck_contestacoes_motivo",
        ),
        CheckConstraint(
            "status IN ('ABERTA', 'EM_ANALISE', 'AGUARDANDO_VENDEDOR', "
            "'ACEITA', 'RECUSADA', 'CANCELADA', 'RESOLVIDA')",
            name="ck_contestacoes_status",
        ),
        Index("ix_contestacoes_pedido_id", "pedido_id"),
        Index("ix_contestacoes_comprador_id", "comprador_id"),
        Index(
            "uq_contestacoes_uma_ativa_por_pedido",
            "pedido_id",
            unique=True,
            postgresql_where=text(
                "status IN ('ABERTA', 'EM_ANALISE', 'AGUARDANDO_VENDEDOR', 'ACEITA')"
            ),
        ),
    )

    pedido_id: Mapped[UUID] = mapped_column(ForeignKey("pedidos.id", name="fk_contestacoes_pedido"))
    comprador_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", name="fk_contestacoes_comprador")
    )
    motivo: Mapped[ContestacaoMotivo] = mapped_column(String(40))
    descricao: Mapped[str] = mapped_column(Text)
    status: Mapped[ContestacaoStatus] = mapped_column(
        String(30),
        default=ContestacaoStatus.ABERTA,
        server_default=ContestacaoStatus.ABERTA.value,
    )
    resolucao: Mapped[str | None] = mapped_column(Text)
    resolvida_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", name="fk_contestacoes_resolvida_por")
    )
    resolvida_em: Mapped[datetime | None]

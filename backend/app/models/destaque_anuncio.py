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
from app.models.enums import (
    DestaqueAnuncioStatus,
    MetodoPagamento,
    PagamentoStatus,
    ProvedorPagamento,
)

# Prefixo do `external_reference` enviado ao Mercado Pago. Diferencia a compra de
# destaque de um pedido, cujo `external_reference` é o UUID puro do pedido.
REFERENCIA_DESTAQUE = "destaque:"


class DestaqueAnuncio(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Compra de destaque de um anúncio, paga pelo vendedor via Checkout Pro."""

    __tablename__ = "destaques_anuncio"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_destaques_anuncio_idempotency_key"),
        UniqueConstraint(
            "provedor", "pagamento_externo_id", name="uq_destaques_anuncio_provedor_externo"
        ),
        UniqueConstraint(
            "preferencia_externa_id", name="uq_destaques_anuncio_preferencia_externa_id"
        ),
        CheckConstraint("provedor IN ('MERCADO_PAGO')", name="ck_destaques_anuncio_provedor"),
        CheckConstraint("valor > 0", name="ck_destaques_anuncio_valor"),
        CheckConstraint("duracao_dias > 0", name="ck_destaques_anuncio_duracao"),
        CheckConstraint(
            "status IN ('AGUARDANDO_PAGAMENTO', 'ATIVO', 'CANCELADO', 'REEMBOLSADO')",
            name="ck_destaques_anuncio_status",
        ),
        CheckConstraint(
            "status_pagamento IN ('CRIADO', 'PENDENTE', 'EM_PROCESSAMENTO', 'APROVADO', "
            "'RECUSADO', 'CANCELADO', 'REEMBOLSADO_PARCIAL', 'REEMBOLSADO')",
            name="ck_destaques_anuncio_status_pagamento",
        ),
        CheckConstraint(
            "metodo IS NULL OR metodo IN ('PIX', 'CARTAO_CREDITO', 'CARTAO_DEBITO', 'BOLETO')",
            name="ck_destaques_anuncio_metodo",
        ),
        CheckConstraint(
            "(status <> 'ATIVO') OR (aprovado_em IS NOT NULL AND inicia_em IS NOT NULL "
            "AND expira_em IS NOT NULL AND expira_em > inicia_em)",
            name="ck_destaques_anuncio_periodo",
        ),
        Index("ix_destaques_anuncio_anuncio_id", "anuncio_id"),
        Index("ix_destaques_anuncio_vendedor_id", "vendedor_id"),
        Index(
            "uq_destaques_anuncio_um_pendente",
            "anuncio_id",
            unique=True,
            postgresql_where=text("status = 'AGUARDANDO_PAGAMENTO'"),
        ),
    )

    anuncio_id: Mapped[UUID] = mapped_column(
        ForeignKey("anuncios.id", name="fk_destaques_anuncio_anuncio")
    )
    vendedor_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", name="fk_destaques_anuncio_vendedor")
    )
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    duracao_dias: Mapped[int] = mapped_column(Integer)
    status: Mapped[DestaqueAnuncioStatus] = mapped_column(
        String(30),
        default=DestaqueAnuncioStatus.AGUARDANDO_PAGAMENTO,
        server_default=DestaqueAnuncioStatus.AGUARDANDO_PAGAMENTO.value,
    )
    provedor: Mapped[ProvedorPagamento] = mapped_column(
        String(30),
        default=ProvedorPagamento.MERCADO_PAGO,
        server_default=ProvedorPagamento.MERCADO_PAGO.value,
    )
    idempotency_key: Mapped[str] = mapped_column(String(255))
    preferencia_externa_id: Mapped[str | None] = mapped_column(String(255))
    pagamento_externo_id: Mapped[str | None] = mapped_column(String(255))
    recebedor_externo_id: Mapped[str | None] = mapped_column(String(255))
    status_pagamento: Mapped[PagamentoStatus] = mapped_column(
        String(30),
        default=PagamentoStatus.CRIADO,
        server_default=PagamentoStatus.CRIADO.value,
    )
    status_detalhe: Mapped[str | None] = mapped_column(String(100))
    metodo: Mapped[MetodoPagamento | None] = mapped_column(String(30))
    checkout_expira_em: Mapped[datetime]
    aprovado_em: Mapped[datetime | None]
    inicia_em: Mapped[datetime | None]
    expira_em: Mapped[datetime | None]
    cancelado_em: Mapped[datetime | None]

"""Cria a compra de destaque pago de anúncios.

Revision ID: 20261123_0011
Revises: 20261031_0010
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261123_0011"
down_revision: str | None = "20261031_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("anuncios", sa.Column("destaque_ate", sa.TIMESTAMP(timezone=True)))
    op.create_index(
        "ix_anuncios_destaque_ate",
        "anuncios",
        ["destaque_ate"],
        postgresql_where=sa.text("destaque_ate IS NOT NULL AND deletado_em IS NULL"),
    )

    op.create_table(
        "destaques_anuncio",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("anuncio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vendedor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("duracao_dias", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="AGUARDANDO_PAGAMENTO",
        ),
        sa.Column("provedor", sa.String(30), nullable=False, server_default="MERCADO_PAGO"),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("preferencia_externa_id", sa.String(255)),
        sa.Column("pagamento_externo_id", sa.String(255)),
        sa.Column("recebedor_externo_id", sa.String(255)),
        sa.Column("status_pagamento", sa.String(30), nullable=False, server_default="CRIADO"),
        sa.Column("status_detalhe", sa.String(100)),
        sa.Column("metodo", sa.String(30)),
        sa.Column("checkout_expira_em", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("aprovado_em", sa.TIMESTAMP(timezone=True)),
        sa.Column("inicia_em", sa.TIMESTAMP(timezone=True)),
        sa.Column("expira_em", sa.TIMESTAMP(timezone=True)),
        sa.Column("cancelado_em", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "atualizado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["anuncio_id"], ["anuncios.id"], name="fk_destaques_anuncio_anuncio"
        ),
        sa.ForeignKeyConstraint(
            ["vendedor_id"], ["usuarios.id"], name="fk_destaques_anuncio_vendedor"
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_destaques_anuncio_idempotency_key"),
        sa.UniqueConstraint(
            "provedor", "pagamento_externo_id", name="uq_destaques_anuncio_provedor_externo"
        ),
        sa.UniqueConstraint(
            "preferencia_externa_id", name="uq_destaques_anuncio_preferencia_externa_id"
        ),
        sa.CheckConstraint("provedor IN ('MERCADO_PAGO')", name="ck_destaques_anuncio_provedor"),
        sa.CheckConstraint("valor > 0", name="ck_destaques_anuncio_valor"),
        sa.CheckConstraint("duracao_dias > 0", name="ck_destaques_anuncio_duracao"),
        sa.CheckConstraint(
            "status IN ('AGUARDANDO_PAGAMENTO', 'ATIVO', 'CANCELADO', 'REEMBOLSADO')",
            name="ck_destaques_anuncio_status",
        ),
        sa.CheckConstraint(
            "status_pagamento IN ('CRIADO', 'PENDENTE', 'EM_PROCESSAMENTO', 'APROVADO', "
            "'RECUSADO', 'CANCELADO', 'REEMBOLSADO_PARCIAL', 'REEMBOLSADO')",
            name="ck_destaques_anuncio_status_pagamento",
        ),
        sa.CheckConstraint(
            "metodo IS NULL OR metodo IN ('PIX', 'CARTAO_CREDITO', 'CARTAO_DEBITO', 'BOLETO')",
            name="ck_destaques_anuncio_metodo",
        ),
        sa.CheckConstraint(
            "(status <> 'ATIVO') OR (aprovado_em IS NOT NULL AND inicia_em IS NOT NULL "
            "AND expira_em IS NOT NULL AND expira_em > inicia_em)",
            name="ck_destaques_anuncio_periodo",
        ),
    )
    op.create_index("ix_destaques_anuncio_anuncio_id", "destaques_anuncio", ["anuncio_id"])
    op.create_index("ix_destaques_anuncio_vendedor_id", "destaques_anuncio", ["vendedor_id"])
    op.create_index(
        "uq_destaques_anuncio_um_pendente",
        "destaques_anuncio",
        ["anuncio_id"],
        unique=True,
        postgresql_where=sa.text("status = 'AGUARDANDO_PAGAMENTO'"),
    )


def downgrade() -> None:
    op.drop_index("uq_destaques_anuncio_um_pendente", table_name="destaques_anuncio")
    op.drop_index("ix_destaques_anuncio_vendedor_id", table_name="destaques_anuncio")
    op.drop_index("ix_destaques_anuncio_anuncio_id", table_name="destaques_anuncio")
    op.drop_table("destaques_anuncio")
    op.drop_index("ix_anuncios_destaque_ate", table_name="anuncios")
    op.drop_column("anuncios", "destaque_ate")

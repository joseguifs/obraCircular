"""Cria a tabela de imagens dos anúncios.

Revision ID: 20260919_0004
Revises: 20260912_0003
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "20260919_0004"
down_revision: str | None = "20260912_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anuncio_imagens",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("anuncio_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chave_objeto", sa.Text(), nullable=False),
        sa.Column("nome_original", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=False),
        sa.Column("ordem", sa.SmallInteger(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["anuncio_id"],
            ["anuncios.id"],
            name="fk_anuncio_imagens_anuncio",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("chave_objeto", name="uq_anuncio_imagens_chave_objeto"),
        sa.UniqueConstraint(
            "anuncio_id",
            "ordem",
            name="uq_anuncio_imagens_anuncio_ordem",
        ),
        sa.CheckConstraint("tamanho_bytes > 0", name="ck_anuncio_imagens_tamanho"),
        sa.CheckConstraint("ordem >= 0", name="ck_anuncio_imagens_ordem"),
    )
    op.create_index(
        "ix_anuncio_imagens_anuncio_id",
        "anuncio_imagens",
        ["anuncio_id"],
    )

    op.execute(
        """
        CREATE TRIGGER trg_anuncio_imagens_atualizado_em
        BEFORE UPDATE ON anuncio_imagens
        FOR EACH ROW EXECUTE FUNCTION definir_atualizado_em()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_anuncio_imagens_atualizado_em ON anuncio_imagens"
    )
    op.drop_index("ix_anuncio_imagens_anuncio_id", table_name="anuncio_imagens")
    op.drop_table("anuncio_imagens")

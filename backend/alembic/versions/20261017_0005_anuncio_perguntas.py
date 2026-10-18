"""Cria a tabela de perguntas e respostas dos anúncios.

Revision ID: 20261017_0005
Revises: 20260919_0004
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "20261017_0005"
down_revision: str | None = "20260919_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anuncio_perguntas",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("anuncio_id", UUID(as_uuid=True), nullable=False),
        sa.Column("autor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("pergunta", sa.Text(), nullable=False),
        sa.Column("resposta", sa.Text(), nullable=True),
        sa.Column("respondido_em", sa.DateTime(timezone=True), nullable=True),
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
            name="fk_anuncio_perguntas_anuncio",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["autor_id"],
            ["usuarios.id"],
            name="fk_anuncio_perguntas_autor",
        ),
        sa.CheckConstraint(
            "char_length(btrim(pergunta)) BETWEEN 1 AND 500",
            name="ck_anuncio_perguntas_pergunta",
        ),
        sa.CheckConstraint(
            "resposta IS NULL OR char_length(btrim(resposta)) BETWEEN 1 AND 1000",
            name="ck_anuncio_perguntas_resposta",
        ),
        sa.CheckConstraint(
            "(resposta IS NULL) = (respondido_em IS NULL)",
            name="ck_anuncio_perguntas_respondido_em",
        ),
    )
    op.create_index(
        "ix_anuncio_perguntas_anuncio_criado_em",
        "anuncio_perguntas",
        ["anuncio_id", sa.text("criado_em DESC")],
    )
    op.create_index(
        "ix_anuncio_perguntas_autor_id",
        "anuncio_perguntas",
        ["autor_id"],
    )

    op.execute(
        """
        CREATE TRIGGER trg_anuncio_perguntas_atualizado_em
        BEFORE UPDATE ON anuncio_perguntas
        FOR EACH ROW EXECUTE FUNCTION definir_atualizado_em()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_anuncio_perguntas_atualizado_em ON anuncio_perguntas"
    )
    op.drop_index("ix_anuncio_perguntas_autor_id", table_name="anuncio_perguntas")
    op.drop_index(
        "ix_anuncio_perguntas_anuncio_criado_em",
        table_name="anuncio_perguntas",
    )
    op.drop_table("anuncio_perguntas")

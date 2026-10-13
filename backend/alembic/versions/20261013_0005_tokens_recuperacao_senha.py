"""Cria a tabela de tokens de recuperação de senha.

Revision ID: 20261013_0005
Revises: 20260919_0004
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "20261013_0005"
down_revision: str | None = "20260919_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tokens_recuperacao_senha",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("usuario_id", UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado_em", sa.DateTime(timezone=True), nullable=True),
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
            ["usuario_id"],
            ["usuarios.id"],
            name="fk_tokens_recuperacao_senha_usuario",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token_hash", name="uq_tokens_recuperacao_senha_token_hash"),
    )
    op.create_index(
        "ix_tokens_recuperacao_senha_usuario_id",
        "tokens_recuperacao_senha",
        ["usuario_id"],
    )

    op.execute(
        """
        CREATE TRIGGER trg_tokens_recuperacao_senha_atualizado_em
        BEFORE UPDATE ON tokens_recuperacao_senha
        FOR EACH ROW EXECUTE FUNCTION definir_atualizado_em()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_tokens_recuperacao_senha_atualizado_em "
        "ON tokens_recuperacao_senha"
    )
    op.drop_index(
        "ix_tokens_recuperacao_senha_usuario_id",
        table_name="tokens_recuperacao_senha",
    )
    op.drop_table("tokens_recuperacao_senha")

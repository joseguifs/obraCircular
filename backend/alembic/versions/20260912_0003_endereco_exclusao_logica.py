"""Adiciona exclusão lógica aos endereços.

Revision ID: 20260912_0003
Revises: 20260911_0002
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260912_0003"
down_revision: str | None = "20260911_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("enderecos", sa.Column("deletado_em", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_enderecos_ativos",
        "enderecos",
        ["usuario_id"],
        postgresql_where=sa.text("deletado_em IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_enderecos_ativos", table_name="enderecos")
    op.drop_column("enderecos", "deletado_em")

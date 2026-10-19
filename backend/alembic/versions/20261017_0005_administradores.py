"""Cria a tabela de administradores.

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
        "administradores",
        sa.Column("usuario_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("concedido_por_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name="fk_administradores_usuario",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["concedido_por_id"],
            ["usuarios.id"],
            name="fk_administradores_concedido_por",
            ondelete="SET NULL",
        ),
    )


def downgrade() -> None:
    op.drop_table("administradores")

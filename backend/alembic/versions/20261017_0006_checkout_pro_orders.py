"""Migra o checkout para a API de Orders do Mercado Pago.

Revision ID: 20261017_0006
Revises: 20261016_0005
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261017_0006"
down_revision: str | None = "20261016_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pagamentos", sa.Column("ordem_externa_id", sa.String(255)))
    op.create_unique_constraint(
        "uq_pagamentos_ordem_externa_id", "pagamentos", ["ordem_externa_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_pagamentos_ordem_externa_id", "pagamentos", type_="unique")
    op.drop_column("pagamentos", "ordem_externa_id")

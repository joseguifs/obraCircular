"""Restringe reembolso integral e amplia contestação ativa.

Revision ID: 20260911_0002
Revises: 20260911_0001
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260911_0002"
down_revision: str | None = "20260911_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "uq_contestacoes_uma_ativa_por_pedido",
        table_name="contestacoes",
    )
    op.create_index(
        "uq_contestacoes_uma_ativa_por_pedido",
        "contestacoes",
        ["pedido_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('ABERTA', 'EM_ANALISE', 'AGUARDANDO_VENDEDOR', 'ACEITA')"
        ),
    )

    op.drop_index("ix_reembolsos_pagamento_id", table_name="reembolsos")
    op.create_unique_constraint(
        "uq_reembolsos_pagamento",
        "reembolsos",
        ["pagamento_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_reembolsos_pagamento",
        "reembolsos",
        type_="unique",
    )
    op.create_index(
        "ix_reembolsos_pagamento_id",
        "reembolsos",
        ["pagamento_id"],
    )

    op.drop_index(
        "uq_contestacoes_uma_ativa_por_pedido",
        table_name="contestacoes",
    )
    op.create_index(
        "uq_contestacoes_uma_ativa_por_pedido",
        "contestacoes",
        ["pedido_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ABERTA', 'EM_ANALISE', 'AGUARDANDO_VENDEDOR')"),
    )

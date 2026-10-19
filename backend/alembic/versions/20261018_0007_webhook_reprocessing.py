"""Adiciona controle seguro de reprocessamento de webhooks.

Revision ID: 20261018_0007
Revises: 20261017_0006
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261018_0007"
down_revision: str | None = "20261017_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMPTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("eventos_provedor", sa.Column("ultima_tentativa_em", TIMESTAMPTZ))
    op.add_column("eventos_provedor", sa.Column("proxima_tentativa_em", TIMESTAMPTZ))
    op.add_column("eventos_provedor", sa.Column("bloqueado_ate", TIMESTAMPTZ))
    op.add_column("eventos_provedor", sa.Column("bloqueado_por", sa.String(100)))
    op.execute(
        """
        UPDATE eventos_provedor
        SET proxima_tentativa_em = recebido_em
        WHERE status_processamento IN ('PENDENTE', 'FALHOU')
        """
    )
    op.create_index(
        "ix_eventos_reprocessamento",
        "eventos_provedor",
        ["status_processamento", "proxima_tentativa_em", "bloqueado_ate"],
        postgresql_where=sa.text("status_processamento IN ('PENDENTE', 'FALHOU')"),
    )


def downgrade() -> None:
    op.drop_index("ix_eventos_reprocessamento", table_name="eventos_provedor")
    op.drop_column("eventos_provedor", "bloqueado_por")
    op.drop_column("eventos_provedor", "bloqueado_ate")
    op.drop_column("eventos_provedor", "proxima_tentativa_em")
    op.drop_column("eventos_provedor", "ultima_tentativa_em")

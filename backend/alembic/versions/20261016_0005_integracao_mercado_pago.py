"""Adiciona suporte ao OAuth, checkout e reserva de estoque.

Revision ID: 20261016_0005
Revises: 20260919_0004
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261016_0005"
down_revision: str | None = "20260919_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.alter_column(
        "contas_pagamento",
        "conta_externa_id",
        existing_type=sa.String(255),
        nullable=True,
    )

    op.drop_constraint("ck_pagamentos_metodo", "pagamentos", type_="check")
    op.drop_constraint("ck_pagamentos_parcelas", "pagamentos", type_="check")
    op.alter_column("pagamentos", "metodo", existing_type=sa.String(30), nullable=True)
    op.add_column("pagamentos", sa.Column("preferencia_externa_id", sa.String(255)))
    op.add_column("pagamentos", sa.Column("status_detalhe", sa.String(100)))
    op.create_unique_constraint(
        "uq_pagamentos_preferencia_externa_id", "pagamentos", ["preferencia_externa_id"]
    )
    op.create_check_constraint(
        "ck_pagamentos_metodo",
        "pagamentos",
        "metodo IS NULL OR metodo IN ('PIX', 'CARTAO_CREDITO', 'CARTAO_DEBITO', 'BOLETO')",
    )
    op.create_check_constraint(
        "ck_pagamentos_parcelas",
        "pagamentos",
        "((metodo IS NULL AND parcelas IS NULL) OR "
        "(metodo = 'CARTAO_CREDITO' AND parcelas IS NOT NULL AND parcelas > 0) OR "
        "(metodo IS NOT NULL AND metodo <> 'CARTAO_CREDITO' AND parcelas IS NULL))",
    )

    op.add_column("pedidos", sa.Column("estoque_reservado_em", TIMESTAMPTZ))
    op.add_column("pedidos", sa.Column("reserva_expira_em", TIMESTAMPTZ))
    op.add_column("pedidos", sa.Column("estoque_liberado_em", TIMESTAMPTZ))
    op.create_index(
        "ix_pedidos_reservas_expiradas",
        "pedidos",
        ["reserva_expira_em"],
        postgresql_where=sa.text(
            "status = 'AGUARDANDO_PAGAMENTO' AND estoque_liberado_em IS NULL"
        ),
    )

    op.create_table(
        "autorizacoes_oauth",
        sa.Column(
            "id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("usuario_id", UUID, nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("code_verifier_criptografado", sa.Text(), nullable=False),
        sa.Column("criado_em", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("expira_em", TIMESTAMPTZ, nullable=False),
        sa.Column("utilizado_em", TIMESTAMPTZ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], name="fk_autorizacoes_oauth_usuario"
        ),
    )
    op.create_index(
        "uq_autorizacoes_oauth_state_hash", "autorizacoes_oauth", ["state_hash"], unique=True
    )
    op.create_index(
        "ix_autorizacoes_oauth_expira_em", "autorizacoes_oauth", ["expira_em"]
    )


def downgrade() -> None:
    op.drop_table("autorizacoes_oauth")
    op.drop_index("ix_pedidos_reservas_expiradas", table_name="pedidos")
    op.drop_column("pedidos", "estoque_liberado_em")
    op.drop_column("pedidos", "reserva_expira_em")
    op.drop_column("pedidos", "estoque_reservado_em")

    op.drop_constraint("ck_pagamentos_parcelas", "pagamentos", type_="check")
    op.drop_constraint("ck_pagamentos_metodo", "pagamentos", type_="check")
    op.drop_constraint("uq_pagamentos_preferencia_externa_id", "pagamentos", type_="unique")
    op.drop_column("pagamentos", "status_detalhe")
    op.drop_column("pagamentos", "preferencia_externa_id")
    op.execute("UPDATE pagamentos SET metodo = 'PIX' WHERE metodo IS NULL")
    op.alter_column("pagamentos", "metodo", existing_type=sa.String(30), nullable=False)
    op.create_check_constraint(
        "ck_pagamentos_metodo",
        "pagamentos",
        "metodo IN ('PIX', 'CARTAO_CREDITO', 'CARTAO_DEBITO', 'BOLETO')",
    )
    op.create_check_constraint(
        "ck_pagamentos_parcelas",
        "pagamentos",
        "((metodo = 'CARTAO_CREDITO' AND parcelas IS NOT NULL AND parcelas > 0) OR "
        "(metodo <> 'CARTAO_CREDITO' AND parcelas IS NULL))",
    )
    op.execute("DELETE FROM contas_pagamento WHERE conta_externa_id IS NULL")
    op.alter_column(
        "contas_pagamento",
        "conta_externa_id",
        existing_type=sa.String(255),
        nullable=False,
    )

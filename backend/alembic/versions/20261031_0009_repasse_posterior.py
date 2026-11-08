"""Congela comissao por venda e separa os repasses posteriores do split legado."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261031_0009"
down_revision: str = "20261019_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pedidos",
        sa.Column(
            "modelo_financeiro", sa.String(30), nullable=False, server_default="SPLIT_LEGADO"
        ),
    )
    op.add_column(
        "pedidos",
        sa.Column(
            "percentual_marketplace", sa.Numeric(5, 2), nullable=False, server_default="25.00"
        ),
    )
    op.add_column("pedidos", sa.Column("taxa_marketplace", sa.Numeric(12, 2)))
    op.add_column("pedidos", sa.Column("valor_vendedor", sa.Numeric(12, 2)))
    op.add_column("pedidos", sa.Column("recebedor_externo_id", sa.String(255)))
    op.execute("""
        UPDATE pedidos p SET percentual_marketplace = r.percentual_marketplace
        FROM repasses r WHERE r.pedido_id = p.id
    """)
    op.execute("""
        UPDATE pedidos SET taxa_marketplace = ROUND(valor_total * percentual_marketplace / 100, 2),
        valor_vendedor = valor_total - ROUND(valor_total * percentual_marketplace / 100, 2)
    """)
    op.execute("""
        UPDATE pedidos p SET recebedor_externo_id = c.conta_externa_id
        FROM anuncios a JOIN contas_pagamento c ON c.usuario_id = a.vendedor_id
        WHERE a.id = p.anuncio_id AND c.provedor = 'MERCADO_PAGO'
    """)
    op.create_check_constraint(
        "ck_pedidos_modelo_financeiro",
        "pedidos",
        "modelo_financeiro IN ('SPLIT_LEGADO', 'REPASSE_POSTERIOR')",
    )
    op.create_check_constraint(
        "ck_pedidos_comissao_snapshot",
        "pedidos",
        "percentual_marketplace BETWEEN 0 AND 100 AND "
        "(taxa_marketplace IS NULL OR taxa_marketplace = "
        "ROUND(valor_total * percentual_marketplace / 100, 2)) AND "
        "(valor_vendedor IS NULL OR valor_vendedor = valor_total - taxa_marketplace)",
    )
    op.create_check_constraint(
        "ck_pedidos_repasse_posterior",
        "pedidos",
        "modelo_financeiro = 'SPLIT_LEGADO' OR (taxa_marketplace IS NOT NULL "
        "AND valor_vendedor IS NOT NULL AND valor_vendedor > 0 "
        "AND recebedor_externo_id IS NOT NULL)",
    )
    op.execute("""
        CREATE FUNCTION proteger_calculo_pedido() RETURNS trigger AS $$
        BEGIN
          IF OLD.modelo_financeiro IS DISTINCT FROM NEW.modelo_financeiro
             OR OLD.percentual_marketplace IS DISTINCT FROM NEW.percentual_marketplace
             OR OLD.taxa_marketplace IS DISTINCT FROM NEW.taxa_marketplace
             OR OLD.valor_vendedor IS DISTINCT FROM NEW.valor_vendedor
             OR OLD.recebedor_externo_id IS DISTINCT FROM NEW.recebedor_externo_id
             OR OLD.valor_total IS DISTINCT FROM NEW.valor_total THEN
            RAISE EXCEPTION 'O calculo financeiro do pedido e imutavel';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_pedidos_calculo_imutavel BEFORE UPDATE ON pedidos
        FOR EACH ROW EXECUTE FUNCTION proteger_calculo_pedido()
    """)
    op.add_column(
        "repasses",
        sa.Column(
            "taxas_por_conta_marketplace", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.drop_constraint("ck_repasses_valores", "repasses", type_="check")
    op.create_check_constraint(
        "ck_repasses_valores",
        "repasses",
        "valor_bruto >= 0 AND taxa_provedor >= 0 AND taxa_marketplace >= 0 "
        "AND valor_liquido >= 0 AND valor_liquido = ROUND(valor_bruto - taxa_marketplace - "
        "CASE WHEN taxas_por_conta_marketplace THEN 0 ELSE taxa_provedor END, 2)",
    )
    op.create_table(
        "destinos_repasse",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "vendedor_id", sa.UUID(), sa.ForeignKey("usuarios.id"), nullable=False, unique=True
        ),
        sa.Column("tipo_chave", sa.String(20), nullable=False),
        sa.Column("chave_criptografada", sa.Text(), nullable=False),
        sa.Column("validado_por", sa.UUID(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("validado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "instrucoes_repasse",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "repasse_id", sa.UUID(), sa.ForeignKey("repasses.id"), nullable=False, unique=True
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("corpo_criptografado", sa.Text(), nullable=False),
        sa.Column("recurso_externo_id", sa.String(255), unique=True),
        sa.Column("transferencia_externa_id", sa.String(255), unique=True),
        sa.Column("status_provedor", sa.String(50)),
        sa.Column("solicitado_por", sa.UUID(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("lease_ate", sa.DateTime(timezone=True)),
        sa.Column("test_mode", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "eventos_repasse",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("repasse_id", sa.UUID(), sa.ForeignKey("repasses.id"), nullable=False),
        sa.Column("operador_id", sa.UUID(), sa.ForeignKey("usuarios.id")),
        sa.Column("acao", sa.String(60), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pedidos WHERE modelo_financeiro = 'REPASSE_POSTERIOR') THEN
            RAISE EXCEPTION 'Ha vendas com repasse posterior; downgrade exige plano de migracao';
          END IF;
        END $$;
    """)
    op.drop_table("eventos_repasse")
    op.drop_table("instrucoes_repasse")
    op.drop_table("destinos_repasse")
    op.drop_constraint("ck_repasses_valores", "repasses", type_="check")
    op.create_check_constraint(
        "ck_repasses_valores",
        "repasses",
        "valor_bruto >= 0 AND taxa_provedor >= 0 AND taxa_marketplace >= 0 "
        "AND valor_liquido >= 0 AND valor_liquido = "
        "ROUND(valor_bruto - taxa_provedor - taxa_marketplace, 2)",
    )
    op.drop_column("repasses", "taxas_por_conta_marketplace")
    op.execute("DROP TRIGGER trg_pedidos_calculo_imutavel ON pedidos")
    op.execute("DROP FUNCTION proteger_calculo_pedido()")
    for constraint in (
        "ck_pedidos_repasse_posterior",
        "ck_pedidos_comissao_snapshot",
        "ck_pedidos_modelo_financeiro",
    ):
        op.drop_constraint(constraint, "pedidos", type_="check")
    for column in (
        "recebedor_externo_id",
        "valor_vendedor",
        "taxa_marketplace",
        "percentual_marketplace",
        "modelo_financeiro",
    ):
        op.drop_column("pedidos", column)

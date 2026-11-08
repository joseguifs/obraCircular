"""Protege instrucoes, calculos de repasse e trilha de auditoria contra alteracao."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261031_0010"
down_revision: str = "20261031_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION proteger_instrucao_repasse() RETURNS trigger AS $$
        BEGIN
          IF OLD.repasse_id IS DISTINCT FROM NEW.repasse_id
             OR OLD.idempotency_key IS DISTINCT FROM NEW.idempotency_key
             OR OLD.corpo_criptografado IS DISTINCT FROM NEW.corpo_criptografado
             OR OLD.solicitado_por IS DISTINCT FROM NEW.solicitado_por
             OR OLD.test_mode IS DISTINCT FROM NEW.test_mode THEN
            RAISE EXCEPTION 'A instrucao financeira e imutavel';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_instrucao_repasse_imutavel BEFORE UPDATE ON instrucoes_repasse
        FOR EACH ROW EXECUTE FUNCTION proteger_instrucao_repasse()
    """)
    op.execute("""
        CREATE FUNCTION proteger_calculo_repasse() RETURNS trigger AS $$
        BEGIN
          IF OLD.pedido_id IS DISTINCT FROM NEW.pedido_id
             OR OLD.pagamento_id IS DISTINCT FROM NEW.pagamento_id
             OR OLD.vendedor_id IS DISTINCT FROM NEW.vendedor_id
             OR OLD.valor_bruto IS DISTINCT FROM NEW.valor_bruto
             OR OLD.taxa_marketplace IS DISTINCT FROM NEW.taxa_marketplace
             OR OLD.percentual_marketplace IS DISTINCT FROM NEW.percentual_marketplace
             OR OLD.valor_liquido IS DISTINCT FROM NEW.valor_liquido
             OR OLD.taxas_por_conta_marketplace IS DISTINCT FROM NEW.taxas_por_conta_marketplace
          THEN
            RAISE EXCEPTION 'O calculo do repasse e imutavel';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_calculo_repasse_imutavel BEFORE UPDATE ON repasses
        FOR EACH ROW EXECUTE FUNCTION proteger_calculo_repasse()
    """)
    op.execute("""
        CREATE FUNCTION proteger_auditoria_repasse() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'A auditoria financeira nao pode ser alterada nem excluida';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_auditoria_repasse_imutavel BEFORE UPDATE OR DELETE ON eventos_repasse
        FOR EACH ROW EXECUTE FUNCTION proteger_auditoria_repasse()
    """)


def downgrade() -> None:
    for trigger, tabela, funcao in (
        ("trg_auditoria_repasse_imutavel", "eventos_repasse", "proteger_auditoria_repasse"),
        ("trg_calculo_repasse_imutavel", "repasses", "proteger_calculo_repasse"),
        ("trg_instrucao_repasse_imutavel", "instrucoes_repasse", "proteger_instrucao_repasse"),
    ):
        op.execute(f"DROP TRIGGER {trigger} ON {tabela}")
        op.execute(f"DROP FUNCTION {funcao}()")

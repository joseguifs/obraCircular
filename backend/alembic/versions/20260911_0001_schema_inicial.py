"""Cria o schema inicial do marketplace.

Revision ID: 20260911_0001
Revises:
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260911_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ = sa.DateTime(timezone=True)


def uuid_pk() -> sa.Column[object]:
    return sa.Column(
        "id",
        UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column("criado_em", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION definir_atualizado_em()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.atualizado_em = NOW();
            RETURN NEW;
        END;
        $$
        """
    )

    op.create_table(
        "usuarios",
        uuid_pk(),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("telefone", sa.String(20)),
        sa.Column("status", sa.String(20), nullable=False, server_default="ATIVO"),
        *timestamps(),
        sa.Column("deletado_em", TIMESTAMPTZ),
        sa.CheckConstraint(
            "status IN ('ATIVO', 'INATIVO', 'BLOQUEADO')",
            name="ck_usuarios_status",
        ),
    )
    op.create_index(
        "uq_usuarios_email_normalizado",
        "usuarios",
        [sa.text("lower(email)")],
        unique=True,
    )
    op.create_index("ix_usuarios_status", "usuarios", ["status"])
    op.create_index(
        "ix_usuarios_ativos",
        "usuarios",
        ["id"],
        postgresql_where=sa.text("deletado_em IS NULL"),
    )

    op.create_table(
        "enderecos",
        uuid_pk(),
        sa.Column("usuario_id", UUID, nullable=False),
        sa.Column("cep", sa.String(8), nullable=False),
        sa.Column("logradouro", sa.String(150), nullable=False),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("complemento", sa.String(100)),
        sa.Column("bairro", sa.String(100), nullable=False),
        sa.Column("cidade", sa.String(100), nullable=False),
        sa.Column("estado", sa.CHAR(2), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], name="fk_enderecos_usuario"),
        sa.UniqueConstraint("id", "usuario_id", name="uq_enderecos_id_usuario"),
        sa.CheckConstraint("cep ~ '^[0-9]{8}$'", name="ck_enderecos_cep"),
        sa.CheckConstraint("estado ~ '^[A-Z]{2}$'", name="ck_enderecos_estado"),
    )
    op.create_index("ix_enderecos_usuario_id", "enderecos", ["usuario_id"])

    op.create_table(
        "categorias",
        uuid_pk(),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("descricao", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False, server_default="ATIVA"),
        *timestamps(),
        sa.UniqueConstraint("nome", name="uq_categorias_nome"),
        sa.CheckConstraint("status IN ('ATIVA', 'INATIVA')", name="ck_categorias_status"),
    )
    op.create_index("ix_categorias_status", "categorias", ["status"])

    op.create_table(
        "anuncios",
        uuid_pk(),
        sa.Column("titulo", sa.String(150), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("categoria_id", UUID, nullable=False),
        sa.Column("vendedor_id", UUID, nullable=False),
        sa.Column("endereco_id", UUID, nullable=False),
        sa.Column("preco", sa.Numeric(12, 2), nullable=False),
        sa.Column("imagem_url", sa.Text()),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ATIVO"),
        sa.Column("postado_em", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("encerrado_em", TIMESTAMPTZ),
        sa.Column("deletado_em", TIMESTAMPTZ),
        sa.ForeignKeyConstraint(["categoria_id"], ["categorias.id"], name="fk_anuncios_categoria"),
        sa.ForeignKeyConstraint(["vendedor_id"], ["usuarios.id"], name="fk_anuncios_vendedor"),
        sa.ForeignKeyConstraint(
            ["endereco_id", "vendedor_id"],
            ["enderecos.id", "enderecos.usuario_id"],
            name="fk_anuncios_endereco_vendedor",
        ),
        sa.CheckConstraint("preco >= 0", name="ck_anuncios_preco"),
        sa.CheckConstraint("quantidade >= 0", name="ck_anuncios_quantidade"),
        sa.CheckConstraint(
            "status IN ('ATIVO', 'ESGOTADO', 'ENCERRADO')",
            name="ck_anuncios_status",
        ),
    )
    op.create_index("ix_anuncios_categoria_id", "anuncios", ["categoria_id"])
    op.create_index("ix_anuncios_vendedor_id", "anuncios", ["vendedor_id"])
    op.create_index("ix_anuncios_endereco_id", "anuncios", ["endereco_id"])
    op.create_index(
        "ix_anuncios_busca_ativos",
        "anuncios",
        ["categoria_id", sa.text("postado_em DESC")],
        postgresql_where=sa.text("status = 'ATIVO' AND deletado_em IS NULL"),
    )

    op.create_table(
        "pedidos",
        uuid_pk(),
        sa.Column("comprador_id", UUID, nullable=False),
        sa.Column("anuncio_id", UUID, nullable=False),
        sa.Column("endereco_entrega_id", UUID),
        sa.Column("endereco_entrega_snapshot", postgresql.JSONB()),
        sa.Column("modalidade_entrega", sa.String(20), nullable=False, server_default="ENTREGA"),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("preco_unitario", sa.Numeric(12, 2), nullable=False),
        sa.Column("valor_total", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="AGUARDANDO_PAGAMENTO",
        ),
        *timestamps(),
        sa.Column("concluido_em", TIMESTAMPTZ),
        sa.Column("cancelado_em", TIMESTAMPTZ),
        sa.ForeignKeyConstraint(["comprador_id"], ["usuarios.id"], name="fk_pedidos_comprador"),
        sa.ForeignKeyConstraint(["anuncio_id"], ["anuncios.id"], name="fk_pedidos_anuncio"),
        sa.ForeignKeyConstraint(
            ["endereco_entrega_id", "comprador_id"],
            ["enderecos.id", "enderecos.usuario_id"],
            name="fk_pedidos_endereco_comprador",
        ),
        sa.CheckConstraint(
            "modalidade_entrega IN ('ENTREGA', 'RETIRADA')",
            name="ck_pedidos_modalidade",
        ),
        sa.CheckConstraint(
            "((modalidade_entrega = 'ENTREGA' AND endereco_entrega_id IS NOT NULL "
            "AND endereco_entrega_snapshot IS NOT NULL) OR "
            "(modalidade_entrega = 'RETIRADA' AND endereco_entrega_id IS NULL "
            "AND endereco_entrega_snapshot IS NULL))",
            name="ck_pedidos_endereco_entrega",
        ),
        sa.CheckConstraint("quantidade > 0", name="ck_pedidos_quantidade"),
        sa.CheckConstraint("preco_unitario >= 0", name="ck_pedidos_preco_unitario"),
        sa.CheckConstraint("valor_total >= 0", name="ck_pedidos_valor_total"),
        sa.CheckConstraint(
            "valor_total = ROUND(quantidade * preco_unitario, 2)",
            name="ck_pedidos_calculo_total",
        ),
        sa.CheckConstraint(
            "status IN ('AGUARDANDO_PAGAMENTO', 'PAGAMENTO_APROVADO', "
            "'PREPARANDO_ENTREGA', 'EM_ENTREGA', 'ENTREGUE', 'EM_CONTESTACAO', "
            "'CONCLUIDO', 'CANCELADO', 'REEMBOLSADO')",
            name="ck_pedidos_status",
        ),
    )
    op.create_index("ix_pedidos_comprador_id", "pedidos", ["comprador_id"])
    op.create_index("ix_pedidos_anuncio_id", "pedidos", ["anuncio_id"])
    op.create_index("ix_pedidos_status", "pedidos", ["status"])
    op.create_index("ix_pedidos_criado_em", "pedidos", [sa.text("criado_em DESC")])

    op.create_table(
        "contas_pagamento",
        uuid_pk(),
        sa.Column("usuario_id", UUID, nullable=False),
        sa.Column("provedor", sa.String(30), nullable=False, server_default="MERCADO_PAGO"),
        sa.Column("conta_externa_id", sa.String(255), nullable=False),
        sa.Column("access_token_criptografado", sa.Text()),
        sa.Column("refresh_token_criptografado", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDENTE"),
        sa.Column("autorizado_em", TIMESTAMPTZ),
        sa.Column("token_expira_em", TIMESTAMPTZ),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], name="fk_contas_pagamento_usuario"
        ),
        sa.UniqueConstraint("usuario_id", "provedor", name="uq_contas_pagamento_usuario_provedor"),
        sa.UniqueConstraint(
            "provedor",
            "conta_externa_id",
            name="uq_contas_pagamento_provedor_externa",
        ),
        sa.CheckConstraint("provedor IN ('MERCADO_PAGO')", name="ck_contas_pagamento_provedor"),
        sa.CheckConstraint(
            "status IN ('PENDENTE', 'ATIVA', 'BLOQUEADA', 'DESCONECTADA')",
            name="ck_contas_pagamento_status",
        ),
    )
    op.create_index("ix_contas_pagamento_usuario_id", "contas_pagamento", ["usuario_id"])

    op.create_table(
        "pagamentos",
        uuid_pk(),
        sa.Column("pedido_id", UUID, nullable=False),
        sa.Column("provedor", sa.String(30), nullable=False, server_default="MERCADO_PAGO"),
        sa.Column("pagamento_externo_id", sa.String(255)),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("metodo", sa.String(30), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("parcelas", sa.Integer()),
        sa.Column("status", sa.String(30), nullable=False, server_default="CRIADO"),
        sa.Column("motivo_recusa", sa.String(255)),
        *timestamps(),
        sa.Column("aprovado_em", TIMESTAMPTZ),
        sa.Column("cancelado_em", TIMESTAMPTZ),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"], name="fk_pagamentos_pedido"),
        sa.UniqueConstraint("idempotency_key", name="uq_pagamentos_idempotency_key"),
        sa.UniqueConstraint(
            "provedor", "pagamento_externo_id", name="uq_pagamentos_provedor_externo"
        ),
        sa.CheckConstraint("provedor IN ('MERCADO_PAGO')", name="ck_pagamentos_provedor"),
        sa.CheckConstraint(
            "metodo IN ('PIX', 'CARTAO_CREDITO', 'CARTAO_DEBITO', 'BOLETO')",
            name="ck_pagamentos_metodo",
        ),
        sa.CheckConstraint("valor > 0", name="ck_pagamentos_valor"),
        sa.CheckConstraint(
            "((metodo = 'CARTAO_CREDITO' AND parcelas IS NOT NULL AND parcelas > 0) "
            "OR (metodo <> 'CARTAO_CREDITO' AND parcelas IS NULL))",
            name="ck_pagamentos_parcelas",
        ),
        sa.CheckConstraint(
            "status IN ('CRIADO', 'PENDENTE', 'EM_PROCESSAMENTO', 'APROVADO', "
            "'RECUSADO', 'CANCELADO', 'REEMBOLSADO_PARCIAL', 'REEMBOLSADO')",
            name="ck_pagamentos_status",
        ),
    )
    op.create_index("ix_pagamentos_pedido_id", "pagamentos", ["pedido_id"])
    op.create_index("ix_pagamentos_status", "pagamentos", ["status"])
    op.create_index(
        "uq_pagamentos_um_aprovado_por_pedido",
        "pagamentos",
        ["pedido_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('APROVADO', 'REEMBOLSADO_PARCIAL', 'REEMBOLSADO')"),
    )

    op.create_table(
        "entregas",
        uuid_pk(),
        sa.Column("pedido_id", UUID, nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="AGUARDANDO_ENVIO"),
        sa.Column("pin_hash", sa.String(255), nullable=False),
        sa.Column("pin_tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pin_max_tentativas", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("pin_expira_em", TIMESTAMPTZ),
        sa.Column("pin_bloqueado_em", TIMESTAMPTZ),
        sa.Column("saiu_para_entrega_em", TIMESTAMPTZ),
        sa.Column("confirmado_em", TIMESTAMPTZ),
        sa.Column("confirmado_por", UUID),
        sa.Column("prazo_contestacao_em", TIMESTAMPTZ),
        *timestamps(),
        sa.UniqueConstraint("pedido_id", name="uq_entregas_pedido"),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"], name="fk_entregas_pedido"),
        sa.ForeignKeyConstraint(
            ["confirmado_por"], ["usuarios.id"], name="fk_entregas_confirmado_por"
        ),
        sa.CheckConstraint(
            "pin_tentativas >= 0 AND pin_max_tentativas > 0 "
            "AND pin_tentativas <= pin_max_tentativas",
            name="ck_entregas_tentativas",
        ),
        sa.CheckConstraint(
            "status IN ('AGUARDANDO_ENVIO', 'PREPARANDO', 'EM_ROTA', "
            "'ENTREGUE', 'RECUSADA', 'CANCELADA')",
            name="ck_entregas_status",
        ),
    )
    op.create_index("ix_entregas_status", "entregas", ["status"])
    op.create_index(
        "ix_entregas_prazo_contestacao",
        "entregas",
        ["prazo_contestacao_em"],
        postgresql_where=sa.text("status = 'ENTREGUE'"),
    )

    op.create_table(
        "repasses",
        uuid_pk(),
        sa.Column("pedido_id", UUID, nullable=False),
        sa.Column("pagamento_id", UUID, nullable=False),
        sa.Column("vendedor_id", UUID, nullable=False),
        sa.Column("conta_pagamento_id", UUID),
        sa.Column("valor_bruto", sa.Numeric(12, 2), nullable=False),
        sa.Column("taxa_provedor", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("taxa_marketplace", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("valor_liquido", sa.Numeric(12, 2), nullable=False),
        sa.Column("percentual_marketplace", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="AGUARDANDO_ENTREGA"),
        sa.Column("liberacao_prevista_em", TIMESTAMPTZ),
        sa.Column("repasse_externo_id", sa.String(255)),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        *timestamps(),
        sa.Column("liberado_em", TIMESTAMPTZ),
        sa.Column("pago_em", TIMESTAMPTZ),
        sa.Column("bloqueado_em", TIMESTAMPTZ),
        sa.UniqueConstraint("pedido_id", name="uq_repasses_pedido"),
        sa.UniqueConstraint("pagamento_id", name="uq_repasses_pagamento"),
        sa.UniqueConstraint("repasse_externo_id", name="uq_repasses_externo"),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"], name="fk_repasses_pedido"),
        sa.ForeignKeyConstraint(["pagamento_id"], ["pagamentos.id"], name="fk_repasses_pagamento"),
        sa.ForeignKeyConstraint(["vendedor_id"], ["usuarios.id"], name="fk_repasses_vendedor"),
        sa.ForeignKeyConstraint(
            ["conta_pagamento_id"],
            ["contas_pagamento.id"],
            name="fk_repasses_conta_pagamento",
        ),
        sa.CheckConstraint(
            "valor_bruto >= 0 AND taxa_provedor >= 0 AND taxa_marketplace >= 0 "
            "AND valor_liquido >= 0 "
            "AND valor_liquido = ROUND(valor_bruto - taxa_provedor - taxa_marketplace, 2)",
            name="ck_repasses_valores",
        ),
        sa.CheckConstraint(
            "percentual_marketplace BETWEEN 0 AND 100",
            name="ck_repasses_percentual",
        ),
        sa.CheckConstraint("tentativas >= 0", name="ck_repasses_tentativas"),
        sa.CheckConstraint(
            "status IN ('AGUARDANDO_ENTREGA', 'EM_PERIODO_CONTESTACAO', 'BLOQUEADO', "
            "'PRONTO_PARA_LIBERACAO', 'PROCESSANDO', 'PAGO', 'FALHOU', 'CANCELADO', "
            "'REEMBOLSADO')",
            name="ck_repasses_status",
        ),
    )
    op.create_index("ix_repasses_vendedor_id", "repasses", ["vendedor_id"])
    op.create_index("ix_repasses_status", "repasses", ["status"])
    op.create_index(
        "ix_repasses_liberacao_pendente",
        "repasses",
        ["liberacao_prevista_em"],
        postgresql_where=sa.text("status = 'EM_PERIODO_CONTESTACAO'"),
    )

    op.create_table(
        "contestacoes",
        uuid_pk(),
        sa.Column("pedido_id", UUID, nullable=False),
        sa.Column("comprador_id", UUID, nullable=False),
        sa.Column("motivo", sa.String(40), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="ABERTA"),
        sa.Column("resolucao", sa.Text()),
        sa.Column("resolvida_por", UUID),
        *timestamps(),
        sa.Column("resolvida_em", TIMESTAMPTZ),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"], name="fk_contestacoes_pedido"),
        sa.ForeignKeyConstraint(
            ["comprador_id"], ["usuarios.id"], name="fk_contestacoes_comprador"
        ),
        sa.ForeignKeyConstraint(
            ["resolvida_por"], ["usuarios.id"], name="fk_contestacoes_resolvida_por"
        ),
        sa.CheckConstraint(
            "motivo IN ('PEDIDO_NAO_RECEBIDO', 'PRODUTO_DANIFICADO', "
            "'QUANTIDADE_INCORRETA', 'PRODUTO_DIFERENTE', 'ENTREGA_PARCIAL', 'OUTRO')",
            name="ck_contestacoes_motivo",
        ),
        sa.CheckConstraint(
            "status IN ('ABERTA', 'EM_ANALISE', 'AGUARDANDO_VENDEDOR', "
            "'ACEITA', 'RECUSADA', 'CANCELADA', 'RESOLVIDA')",
            name="ck_contestacoes_status",
        ),
    )
    op.create_index("ix_contestacoes_pedido_id", "contestacoes", ["pedido_id"])
    op.create_index("ix_contestacoes_comprador_id", "contestacoes", ["comprador_id"])
    op.create_index(
        "uq_contestacoes_uma_ativa_por_pedido",
        "contestacoes",
        ["pedido_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ABERTA', 'EM_ANALISE', 'AGUARDANDO_VENDEDOR')"),
    )

    op.create_table(
        "reembolsos",
        uuid_pk(),
        sa.Column("pedido_id", UUID, nullable=False),
        sa.Column("pagamento_id", UUID, nullable=False),
        sa.Column("contestacao_id", UUID),
        sa.Column("reembolso_externo_id", sa.String(255)),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="SOLICITADO"),
        sa.Column("solicitado_por", UUID, nullable=False),
        *timestamps(),
        sa.Column("processado_em", TIMESTAMPTZ),
        sa.Column("falhou_em", TIMESTAMPTZ),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"], name="fk_reembolsos_pedido"),
        sa.ForeignKeyConstraint(
            ["pagamento_id"], ["pagamentos.id"], name="fk_reembolsos_pagamento"
        ),
        sa.ForeignKeyConstraint(
            ["contestacao_id"], ["contestacoes.id"], name="fk_reembolsos_contestacao"
        ),
        sa.ForeignKeyConstraint(
            ["solicitado_por"], ["usuarios.id"], name="fk_reembolsos_solicitado_por"
        ),
        sa.UniqueConstraint("reembolso_externo_id", name="uq_reembolsos_externo"),
        sa.UniqueConstraint("idempotency_key", name="uq_reembolsos_idempotency_key"),
        sa.CheckConstraint("valor > 0", name="ck_reembolsos_valor"),
        sa.CheckConstraint(
            "status IN ('SOLICITADO', 'PROCESSANDO', 'CONCLUIDO', "
            "'RECUSADO', 'FALHOU', 'CANCELADO')",
            name="ck_reembolsos_status",
        ),
    )
    op.create_index("ix_reembolsos_pedido_id", "reembolsos", ["pedido_id"])
    op.create_index("ix_reembolsos_pagamento_id", "reembolsos", ["pagamento_id"])

    op.create_table(
        "eventos_provedor",
        uuid_pk(),
        sa.Column("provedor", sa.String(30), nullable=False, server_default="MERCADO_PAGO"),
        sa.Column("evento_externo_id", sa.String(255), nullable=False),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("recurso_externo_id", sa.String(255)),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status_processamento", sa.String(20), nullable=False, server_default="PENDENTE"),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recebido_em", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("processado_em", TIMESTAMPTZ),
        sa.Column("erro", sa.Text()),
        sa.UniqueConstraint("provedor", "evento_externo_id", name="uq_eventos_provedor_externo"),
        sa.CheckConstraint("provedor IN ('MERCADO_PAGO')", name="ck_eventos_provedor"),
        sa.CheckConstraint("tentativas >= 0", name="ck_eventos_tentativas"),
        sa.CheckConstraint(
            "status_processamento IN ('PENDENTE', 'PROCESSADO', 'FALHOU', 'IGNORADO')",
            name="ck_eventos_status",
        ),
    )
    op.create_index(
        "ix_eventos_status_processamento",
        "eventos_provedor",
        ["status_processamento", "recebido_em"],
    )
    op.create_index(
        "ix_eventos_recurso_externo",
        "eventos_provedor",
        ["provedor", "recurso_externo_id"],
    )

    for table_name in (
        "usuarios",
        "enderecos",
        "categorias",
        "anuncios",
        "pedidos",
        "contas_pagamento",
        "pagamentos",
        "entregas",
        "repasses",
        "contestacoes",
        "reembolsos",
    ):
        op.execute(
            f"""
            CREATE TRIGGER tg_{table_name}_atualizado_em
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION definir_atualizado_em()
            """
        )


def downgrade() -> None:
    for table_name in (
        "reembolsos",
        "contestacoes",
        "repasses",
        "entregas",
        "pagamentos",
        "contas_pagamento",
        "pedidos",
        "anuncios",
        "categorias",
        "enderecos",
        "usuarios",
    ):
        op.drop_table(table_name)

    op.drop_table("eventos_provedor")
    op.execute("DROP FUNCTION IF EXISTS definir_atualizado_em()")

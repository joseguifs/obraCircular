# Regras de Domínio — Entrega

Cada pedido possui exatamente uma entrega, inclusive quando a modalidade é
`RETIRADA`.

## Status

- `AGUARDANDO_ENVIO`
- `PREPARANDO`
- `EM_ROTA`
- `ENTREGUE`
- `RECUSADA`
- `CANCELADA`

Para `ENTREGA`, o fluxo normal é:

```text
AGUARDANDO_ENVIO -> PREPARANDO -> EM_ROTA -> ENTREGUE
```

Para `RETIRADA`, `EM_ROTA` não é utilizado:

```text
AGUARDANDO_ENVIO -> PREPARANDO -> ENTREGUE
```

`RECUSADA` significa que o comprador recusou o recebimento dos materiais.
`CANCELADA` significa que o pedido foi cancelado antes da confirmação do PIN.

## PIN

- O backend gera o PIN com um gerador criptograficamente seguro.
- Somente o hash é armazenado em `pin_hash`.
- O PIN pertence a uma única entrega e somente o comprador pode visualizá-lo.
- O vendedor informa o PIN recebido do comprador para confirmar a entrega ou a
  retirada.
- `confirmado_por` deve ser o vendedor do anúncio associado ao pedido.
- O PIN só pode ser confirmado depois que o comprador conferir todo o material.
- Depois de cinco tentativas incorretas, o PIN é bloqueado.
- O PIN deixa de ser válido depois da confirmação ou do cancelamento.
- Um PIN expirado pode ser regenerado pelo backend. A regeneração substitui o hash,
  redefine as tentativas e invalida o código anterior.
- Para o MVP, o PIN expira 24 horas após ser gerado.

## Prazo de contestação

Após validar o PIN, a aplicação define:

```text
prazo_contestacao_em = confirmado_em + 7 dias corridos
```

As datas são armazenadas em UTC. A contestação pode ser aberta enquanto o momento
atual for menor ou igual ao prazo; o repasse só pode ser liberado quando o momento
atual for posterior ao prazo.

A janela operacional de sete dias acompanha o direito de arrependimento aplicável
às contratações fora do estabelecimento previsto no art. 49 do Código de Defesa do
Consumidor. A aplicação dessa regra ao modelo concreto do marketplace deve ser
validada juridicamente.

Fonte: [Lei nº 8.078/1990, art. 49](https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm).

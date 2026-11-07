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

### Implementação (MVP)

- `POST /api/v1/orders/{pedido_id}/delivery/pin` (comprador): gera o PIN e o
  devolve em texto puro uma única vez. A entrega é criada nesta chamada, caso ainda
  não exista. Só é permitido com o pedido em `PAGAMENTO_APROVADO`,
  `PREPARANDO_ENTREGA` ou `EM_ENTREGA`.
- Como apenas o hash é guardado, o comprador que perder o PIN precisa gerar outro.
  Por isso, a regeneração é permitida a qualquer momento antes da confirmação,
  inclusive com o PIN bloqueado. Ela substitui o hash e zera as tentativas.
- `POST /api/v1/orders/{pedido_id}/delivery/confirm` (vendedor do anúncio): valida
  o PIN. A confirmação repetida pelo mesmo vendedor é idempotente.
- O hash é HMAC-SHA256 com chave do servidor (`OBRA_CIRCULAR_DELIVERY_PIN_SECRET_KEY`,
  ou uma subchave derivada do segredo JWT) e é vinculado ao id da entrega. Um hash
  sem chave de um PIN de 5 dígitos seria revertido por força bruta.

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

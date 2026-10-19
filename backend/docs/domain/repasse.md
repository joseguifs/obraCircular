# Regras de Domínio — Repasse

## Status

- `AGUARDANDO_ENTREGA`
- `EM_PERIODO_CONTESTACAO`
- `BLOQUEADO`
- `PRONTO_PARA_LIBERACAO`
- `PROCESSANDO`
- `PAGO`
- `FALHOU`
- `CANCELADO`
- `REEMBOLSADO`

## Valor líquido

```text
valor_liquido = valor_bruto - taxa_marketplace - taxa_provedor
```

Todos os valores usam `Decimal`, duas casas decimais e arredondamento comercial
(`ROUND_HALF_UP`) antes da persistência.

## Natureza do registro

No Split 1:1 público, o Mercado Pago divide o pagamento automaticamente. Portanto,
`Repasse` é a razão contábil interna da venda e não uma conta de garantia. Nenhum status
local deve ser apresentado ao usuário como prova de que o dinheiro está fisicamente
retido ou foi liberado pela Obra Circular.

## Regras e transições

- A aprovação do pagamento cria um único repasse em `PAGO`, pois o provedor já confirmou
  o pagamento e o split automático.
- A confirmação do PIN altera o repasse para `EM_PERIODO_CONTESTACAO` e define
  `liberacao_prevista_em` igual a `prazo_contestacao_em`.
- Uma contestação ativa altera o repasse para `BLOQUEADO`.
- Sem contestação ativa, o job de conclusão pode concluir o pedido quando o prazo
  terminar. Ele não executa uma transferência financeira no Mercado Pago.
- `PRONTO_PARA_LIBERACAO` e `PROCESSANDO` ficam reservados para uma eventual solução
  comercial futura de retenção/liberação e não são produzidos pelo Split 1:1 do MVP.
- Uma falha altera o estado para `FALHOU`. A repetição reutiliza o mesmo registro,
  consulta antes o provedor, incrementa `tentativas` e retorna para `PROCESSANDO`.
- Depois de três falhas automáticas, o repasse permanece `FALHOU` para tratamento
  administrativo.
- Cancelamento antes do repasse altera o estado para `CANCELADO`; a confirmação do
  reembolso altera para `REEMBOLSADO`.

O job e a integração com o provedor devem ser idempotentes. `PAGO` significa que o
provedor confirmou o pagamento com split automático; não significa que a Obra Circular
controlou a data de disponibilização do saldo ao vendedor.

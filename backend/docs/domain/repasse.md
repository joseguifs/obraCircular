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

## Regras e transições

- A aprovação do pagamento cria um único repasse em `AGUARDANDO_ENTREGA`.
- A confirmação do PIN altera o repasse para `EM_PERIODO_CONTESTACAO` e define
  `liberacao_prevista_em` igual a `prazo_contestacao_em`.
- Uma contestação ativa altera o repasse para `BLOQUEADO`.
- Sem contestação ativa, o job de liberação muda o repasse para
  `PRONTO_PARA_LIBERACAO` quando o momento atual superar o prazo.
- O início da operação no provedor altera o estado para `PROCESSANDO`.
- A confirmação do provedor altera o estado para `PAGO`. Somente `PAGO` permite
  concluir o pedido.
- Uma falha altera o estado para `FALHOU`. A repetição reutiliza o mesmo registro,
  consulta antes o provedor, incrementa `tentativas` e retorna para `PROCESSANDO`.
- Depois de três falhas automáticas, o repasse permanece `FALHOU` para tratamento
  administrativo.
- Cancelamento antes do repasse altera o estado para `CANCELADO`; a confirmação do
  reembolso altera para `REEMBOLSADO`.

O job e a integração com o provedor devem ser idempotentes. `PRONTO_PARA_LIBERACAO`
significa apenas que o repasse está elegível; `PAGO` significa que o provedor
confirmou a disponibilização ou transferência ao vendedor, inclusive quando o
split financeiro ocorrer automaticamente.

# Regras de Domínio — Reembolso

O MVP permite no máximo um reembolso por pagamento, sempre integral.

## Status

- `SOLICITADO`
- `PROCESSANDO`
- `CONCLUIDO`
- `RECUSADO`
- `FALHOU`
- `CANCELADO`

## Regras

- O valor do reembolso deve ser exatamente igual ao valor do pagamento aprovado.
- Um segundo registro de reembolso para o mesmo pagamento não é permitido.
- O reembolso pode ser iniciado por um cancelamento anterior à entrega, por uma
  contestação aceita ou por um operador administrativo autorizado.
- `CONCLUIDO` somente pode ser definido após confirmação do provedor.
- Em caso de falha técnica, o mesmo registro passa de `FALHOU` novamente para
  `PROCESSANDO`; não se cria outro reembolso.
- A mesma `idempotency_key` deve ser reutilizada nas tentativas da mesma operação.

## Efeitos do reembolso concluído

Na mesma transação da confirmação:

1. o pagamento passa para `REEMBOLSADO`;
2. o pedido passa para `REEMBOLSADO`;
3. o repasse passa para `REEMBOLSADO`;
4. uma contestação `ACEITA`, quando existir, passa para `RESOLVIDA`;
5. a quantidade comprada volta ao estoque exatamente uma vez, exceto se já tiver
   sido devolvida durante o cancelamento.

O reembolso não pode ser concluído se o repasse já estiver `PAGO`.

No Split 1:1 do MVP, `PAGO` é criado junto com a aprovação e não impede o reembolso.
O item anterior aplica-se apenas a um eventual repasse manual futuro e fica substituído
por estas regras:

- o reembolso é solicitado com o token OAuth do vendedor e chave de idempotência;
- Mercado Pago e marketplace devolvem suas parcelas proporcionalmente;
- se faltar saldo do vendedor, o reembolso local passa para `FALHOU` e exige análise;
- a plataforma pode cobrir a diferença somente depois de confirmar saldo do fundo e
  executar a devolução por um meio autorizado;
- o valor coberto cria dívida contábil do vendedor; uma sobretaxa configurável em vendas
  futuras poderá amortizá-la até zerar;
- a API pública do Split 1:1 não completa automaticamente a parcela sem saldo. A saída
  do fundo e a cobrança futura serão implementadas quando o meio autorizado e o fluxo
  administrativo estiverem definidos.

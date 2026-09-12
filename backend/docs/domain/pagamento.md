# Regras de Domínio — Pagamento

## Métodos permitidos

- `PIX`
- `CARTAO_CREDITO`
- `CARTAO_DEBITO`
- `BOLETO`

## Status

- `CRIADO`
- `PENDENTE`
- `EM_PROCESSAMENTO`
- `APROVADO`
- `RECUSADO`
- `CANCELADO`
- `REEMBOLSADO_PARCIAL`
- `REEMBOLSADO`

`REEMBOLSADO_PARCIAL` permanece no schema por compatibilidade com o provedor, mas
não é produzido pelo fluxo de negócio do MVP, que aceita somente reembolso total.

## Regras

- Um pedido pode possuir várias tentativas recusadas ou canceladas.
- Apenas uma tentativa pode pertencer à sequência de sucesso do pedido, nos status
  `APROVADO` ou `REEMBOLSADO`.
- O backend gera uma `idempotency_key` por tentativa e reutiliza a mesma chave ao
  repetir a requisição daquela tentativa.
- O frontend e o webhook não são fontes definitivas do estado.
- Depois de receber o webhook, o backend consulta o pagamento no provedor.
- Somente a confirmação do provedor permite alterar pagamento e pedido para
  `APROVADO` e `PAGAMENTO_APROVADO`.
- A aprovação bloqueia o anúncio com `SELECT ... FOR UPDATE`, valida e reduz o
  estoque na mesma transação. Se o estoque for insuficiente, a operação não deve
  avançar e exige tratamento administrativo do pagamento.
- Um pagamento `RECUSADO` mantém o pedido em `AGUARDANDO_PAGAMENTO`, não altera o
  estoque e permite nova tentativa.

A atualização feita por webhook deve ser idempotente: receber novamente o mesmo
evento ou o mesmo estado não pode repetir a redução de estoque.

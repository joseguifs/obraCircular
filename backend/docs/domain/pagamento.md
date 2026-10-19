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
- O backend gera uma `idempotency_key` por tentativa para identificar operações
  locais e reembolsos idempotentes.
- Cada tentativa iniciada pelo Checkout Pro persiste o identificador da Preference em
  `preferencia_externa_id`. `ordem_externa_id` permanece somente para compatibilidade
  com tentativas criadas durante a integração anterior pela API de Orders.
- O frontend e o webhook não são fontes definitivas do estado.
- Depois de receber um webhook `type=payment`, o backend consulta
  `GET /v1/payments/{id}` com o token OAuth do vendedor.
- Somente a confirmação do provedor permite alterar pagamento e pedido para
  `APROVADO` e `PAGAMENTO_APROVADO`.
- O checkout reserva estoque antes de redirecionar o comprador. A aprovação confirma
  a reserva sem uma segunda redução. Uma aprovação recebida após a liberação da reserva
  não pode consumir estoque novamente. Ela é conciliada como `APROVADO`, mantém o
  pedido `CANCELADO` e inicia a devolução integral com chave idempotente. Falhas de
  devolução são reprocessadas pelo evento; ao esgotar tentativas exigem atendimento.
- Se o mesmo comprador repetir a mesma compra enquanto a reserva estiver ativa, o
  backend retorna o `init_point` da mesma Preference. Não cria outro pedido, outra
  cobrança ou uma segunda redução de estoque.
- Um pagamento `RECUSADO` mantém o pedido em `AGUARDANDO_PAGAMENTO`, não altera o
  estoque e permite nova tentativa.

A atualização feita por webhook deve ser idempotente: receber novamente o mesmo evento
ou o mesmo estado não pode repetir a confirmação, o repasse ou a devolução de estoque.
Consultas antigas com estados pendentes, recusados ou cancelados não podem rebaixar um
pagamento já aprovado ou reembolsado. Uma aprovação antiga não reabre um reembolso.

No Checkout Pro, o método pode permanecer desconhecido (`NULL`) enquanto a tentativa
está em `CRIADO` ou `PENDENTE`, porque o comprador escolhe o meio no Mercado Pago. O
webhook confirmado preenche o método efetivamente utilizado.

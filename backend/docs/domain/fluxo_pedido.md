# Fluxos do pedido

Os fluxos abaixo definem o comportamento mínimo do MVP. Cada transição deve ser
idempotente e operações que alterem mais de uma entidade devem ocorrer na mesma
transação.

## Fluxo principal — entrega

```text
Pedido criado
-> pagamento aprovado pelo provedor
-> estoque reduzido com bloqueio do anúncio
-> repasse criado como AGUARDANDO_ENTREGA
-> vendedor prepara e envia os materiais
-> comprador confere e fornece o PIN
-> vendedor valida o PIN
-> pedido e entrega passam para ENTREGUE
-> inicia janela de contestação de 7 dias corridos
-> prazo termina sem contestação ativa
-> repasse passa para PRONTO_PARA_LIBERACAO
-> provedor confirma o repasse como PAGO
-> pedido passa para CONCLUIDO
```

Na modalidade `RETIRADA`, não há etapa `EM_ROTA`. O comprador confere o material
no local combinado e fornece o PIN ao vendedor.

## Pagamento recusado

```text
Provedor confirma RECUSADO
-> tentativa de pagamento passa para RECUSADO
-> pedido permanece AGUARDANDO_PAGAMENTO
-> estoque não é alterado
-> comprador pode iniciar uma nova tentativa
```

## Cancelamento

Sem pagamento aprovado, o pedido passa diretamente para `CANCELADO`. Depois do
pagamento aprovado e antes do PIN, o pedido passa para `CANCELADO`, o estoque é
reposto uma única vez, o repasse passa para `CANCELADO` e é iniciado o reembolso
integral. Quando o provedor confirmar o reembolso, pedido, pagamento e repasse
passam para `REEMBOLSADO`.

## Contestação

```text
Comprador abre contestação dentro do prazo
-> pedido passa para EM_CONTESTACAO
-> repasse passa para BLOQUEADO
-> contestação é analisada
```

Se for recusada ou cancelada, o pedido retorna a `ENTREGUE` e o repasse retoma a
liberação. Se for aceita, permanece ativa em `ACEITA` até o reembolso integral ser
confirmado; então passa para `RESOLVIDA`.

## Falha no repasse

```text
Repasse PROCESSANDO
-> provedor não confirma a transferência
-> repasse passa para FALHOU
-> pedido não é concluído
-> consultar o provedor antes de tentar novamente
-> reutilizar o mesmo repasse e incrementar tentativas
```

Não se cria outro repasse. Após três falhas automáticas, ele permanece `FALHOU`
para tratamento administrativo.

## Reembolso

Existe um único reembolso integral por pagamento. Enquanto ele estiver pendente,
o pedido não pode ser concluído e o repasse não pode ser pago. Se falhar, reutiliza
o mesmo registro. Quando confirmado, os estados relacionados passam para
`REEMBOLSADO` e o estoque é reposto uma única vez, caso ainda não tenha sido.

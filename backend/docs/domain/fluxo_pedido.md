# Fluxos do pedido

Os fluxos abaixo definem o comportamento mínimo do MVP. Cada transição deve ser
idempotente e operações que alterem mais de uma entidade devem ocorrer na mesma
transação.

## Fluxo principal — entrega

```text
Pedido criado
-> estoque reservado com bloqueio do anúncio
-> comprador conclui o Checkout Pro
-> pagamento aprovado e confirmado consultando o provedor
-> reserva convertida em venda sem nova baixa
-> repasse criado como AGUARDANDO_ENTREGA, sem transferência ao vendedor
-> vendedor prepara e envia os materiais
-> comprador confere e fornece o PIN
-> vendedor valida o PIN
-> pedido e entrega passam para ENTREGUE
-> inicia janela de contestação de 7 dias corridos
-> prazo termina sem contestação ativa
-> repasse fica elegível para liberação
-> administrador ou job solicita a transferência Pix
-> provedor confirma o crédito ao vendedor
-> repasse passa para PAGO e pedido para CONCLUIDO
```

Na modalidade `RETIRADA`, não há etapa `EM_ROTA`. O comprador confere o material
no local combinado e fornece o PIN ao vendedor.

A geração e validação do PIN serão implementadas por outro membro da equipe. O
fluxo acima descreve o contrato esperado; a abertura de contestação já consome a
entrega confirmada, mas não implementa essa confirmação.

## Pagamento recusado

```text
Provedor confirma RECUSADO
-> tentativa de pagamento passa para RECUSADO
-> pedido permanece AGUARDANDO_PAGAMENTO
-> reserva permanece até nova tentativa, cancelamento ou expiração
-> comprador pode iniciar uma nova tentativa
```

## Cancelamento

Sem pagamento aprovado, o pedido passa diretamente para `CANCELADO` e a reserva é
devolvida. Depois do pagamento aprovado e antes do PIN, o pedido passa para
`CANCELADO`, inicia-se o reembolso integral e o estoque é reposto uma única vez na
confirmação. Quando o provedor confirmar o reembolso, pedido, pagamento e repasse
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

A abertura e a consulta pelo comprador estão implementadas na API e na tela
`/pedidos/{pedido_id}/contestacoes`. A análise e resolução administrativa descritas
acima são uma etapa futura, separada da abertura.

## Falha no repasse

```text
Repasse PROCESSANDO
-> provedor não confirma a transferência
-> repasse passa para FALHOU
-> pedido não é concluído
-> consultar o provedor antes de tentar novamente
-> reutilizar o mesmo repasse e incrementar tentativas
```

Não se cria outro repasse nem uma nova instrução após uma rejeição final. Uma
resposta incerta permanece em conciliação com a mesma chave de idempotência;
`FALHOU` exige tratamento administrativo.

## Reembolso

Existe um único reembolso integral por pagamento. Enquanto ele estiver pendente,
o pedido não pode ser concluído e o repasse não pode ser pago. Se falhar, reutiliza
o mesmo registro. Quando confirmado, os estados relacionados passam para
`REEMBOLSADO` e o estoque é reposto uma única vez, caso ainda não tenha sido.

## Compatibilidade financeira

O fluxo acima se aplica a `REPASSE_POSTERIOR`. Pedidos anteriores permanecem
`SPLIT_LEGADO`, com o split financeiro já executado; nenhum painel ou job pode
transferir dinheiro novamente para esses pedidos. Consulte [repasse.md](repasse.md).

As contas de teste utilizadas não possuem chave Pix. A verificação automatizada
simula o provedor e cobre o bloqueio por contestação inclusive após o prazo; a
transferência real ao vendedor não foi homologada nesse ambiente.

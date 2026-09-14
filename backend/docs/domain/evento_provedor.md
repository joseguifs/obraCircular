# Regras de Domínio — Evento do provedor

Os eventos representam webhooks recebidos do Mercado Pago.

## Status

- `PENDENTE`
- `PROCESSADO`
- `FALHOU`
- `IGNORADO`

## Regras

- A assinatura deve ser verificada antes de registrar ou processar o evento.
- Um evento com assinatura inválida é rejeitado e registrado apenas nos logs de
  segurança, sem criar `EventoProvedor`.
- A combinação de provedor e `evento_externo_id` identifica o evento de forma
  única.
- O registro deve usar inserção idempotente. Se já existir como `PROCESSADO` ou
  `IGNORADO`, a resposta é de sucesso e nenhum efeito é repetido.
- Eventos `PENDENTE` ou `FALHOU` podem ser processados novamente no mesmo registro.
- O payload válido é armazenado para auditoria e depuração.
- Nenhum pagamento é atualizado apenas com os dados do webhook; o backend sempre
  consulta o provedor usando o identificador recebido.

## Fluxo

```text
Webhook recebido
-> verificar assinatura
-> registrar ou localizar o evento de forma idempotente
-> consultar o pagamento no Mercado Pago
-> aplicar a transição de estado em uma transação
-> marcar o evento como PROCESSADO
```

Evento válido, mas sem efeito conhecido, passa para `IGNORADO`. Erro temporário
passa para `FALHOU` e incrementa `tentativas`.

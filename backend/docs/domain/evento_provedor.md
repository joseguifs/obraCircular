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
- Cada tentativa incrementa `tentativas`, registra `ultima_tentativa_em` e adquire um
  lease temporário. Workers concorrentes usam `FOR UPDATE SKIP LOCKED`; um lease
  expirado pode ser retomado após queda do worker, inclusive quando não existe
  `proxima_tentativa_em`. O dono antigo não pode concluir nem sobrescrever o novo lease.
  Uma queda na última tentativa transforma o evento abandonado em `FALHOU` visível.
- Falhas transitórias definem `proxima_tentativa_em` com backoff exponencial limitado.
  Ao atingir o máximo configurado, ou diante de erro permanente, o evento permanece
  `FALHOU` sem nova tentativa automática e deve gerar alerta operacional.
- O reprocessamento manual exige o UUID persistido do evento e não cria uma nova linha.
- O payload válido é armazenado para auditoria e depuração.
- Nenhum pagamento é atualizado apenas com os dados do webhook; o backend sempre
  consulta o provedor usando o identificador recebido.
- Uma aprovação tardia é conciliada antes de tentar devolver a cobrança. Falhas na
  devolução preservam o pagamento aprovado e o evento permanece reprocessável.

## Fluxo

```text
Webhook recebido
-> verificar assinatura
-> registrar ou localizar o evento de forma idempotente
-> responder HTTP 200 e processar fora da requisição
-> consultar o pagamento no Mercado Pago
-> aplicar a transição de estado em uma transação
-> marcar o evento como PROCESSADO
```

Evento válido, mas sem efeito conhecido, passa para `IGNORADO`. Erro temporário
passa para `FALHOU` e incrementa `tentativas`.

O endpoint `/health/webhooks` expõe somente contadores operacionais, sem payloads ou
identificadores. `critical` indica falha sem nova tentativa automática ou processamento
abandonado; `degraded` indica falhas agendadas ou evento não finalizado há mais de cinco
minutos. Estados diferentes de `ok` retornam HTTP 503 e código de saída 1 no job.

O lifespan da API inicia o worker periódico por padrão. O processamento imediato após
o HTTP 200 é uma otimização; eventos persistidos são recuperados pelo ciclo periódico.

## Eventos OAuth

- `application.authorized` confirma uma vinculação gerenciada pelo callback OAuth.
- `application.deauthorized` altera a conta para `DESCONECTADA`, remove os tokens
  criptografados persistidos e bloqueia novos checkouts até uma nova autorização.

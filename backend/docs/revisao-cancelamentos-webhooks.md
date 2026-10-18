# Revisão de cancelamento, reembolso e recuperação de webhooks

Data: 18/10/2026. Escopo: os seis achados da revisão anterior, suas correções e a
consistência entre frontend, API, worker e persistência.

## Resultado

Os dois bloqueadores anteriores foram corrigidos. Os testes de regressão passam nos
cenários reproduzidos abaixo; não foram encontrados novos bloqueadores nesses fluxos.

| Achado | Comportamento verificado após a correção | Evidência |
| --- | --- | --- |
| Worker cai com lease ativo | Lease expirado é retomado mesmo sem próxima tentativa; queda na última tentativa vira falha visível | `tests/test_webhook_reprocessing.py` |
| Aprovação chega depois do cancelamento | Cobrança é conciliada, pedido continua cancelado e devolução integral usa a mesma chave idempotente, sem nova baixa de estoque | `tests/test_aprovacao_tardia.py` |
| Queda entre conciliação e devolução | Novo worker retoma a devolução sem duplicar repasse nem reposição de estoque | `tests/test_aprovacao_tardia.py` |
| Reembolso assíncrono ou falho fica desatualizado | API retorna o registro do reembolso; frontend acompanha estados pendentes e reconcilia o pedido após erros | `frontend/src/features/pagamentos/PagamentoRetornoPage.test.tsx` |
| Consulta antiga sobrescreve ação nova | Respostas anteriores à ação são descartadas; worker antigo também não sobrescreve novo lease | Testes de pagamentos no frontend e `tests/test_webhook_reprocessing.py` |
| Ações só existem no retorno do checkout | Histórico e detalhes de pedidos podem ser acessados pelo menu e perfil, independentemente do último checkout | `frontend/src/features/pagamentos/PedidosPage.test.tsx` |
| Monitoramento não sinaliza abandono | Health retorna HTTP 503, job retorna saída 1; lifespan inicia worker periódico e o encerra no shutdown | `tests/test_webhook_worker.py` |

## Verificação

- Backend: `python -m pytest -q --tb=short` — 149 testes passaram.
- Frontend: `npm.cmd test` — 54 testes passaram.
- `python -m ruff check app tests` e `python -m mypy app` — aprovados.
- `npm.cmd run build` — aprovado.
- `python -m alembic check` — nenhuma alteração de esquema pendente.
- Assinatura HMAC, consulta ao provedor, titularidade dos pedidos e unicidade dos
  registros financeiros foram preservadas.

## Condições operacionais

- A validação financeira usa PostgreSQL e um gateway simulado; não foi executado
  pagamento/reembolso real nem homologação no Mercado Pago nesta revisão.
- Reiniciar a API ativa o worker pelo lifespan, habilitado por padrão. Instalações
  que desabilitarem o lifespan ou `WEBHOOK_WORKER_ENABLED` devem executar o job externo.
- O monitor de disponibilidade deve consumir `/api/v1/health/webhooks` e alertar em
  HTTP 503. Não há envio de e-mail ou configuração de um serviço externo de alertas.
- Falta de saldo ou autorização do vendedor ainda pode impedir uma devolução real.
  A cobrança permanece registrada e a falha é visível; esgotar as retentativas exige
  atendimento e reprocessamento explícito após corrigir a causa.
- O polling do frontend tem limite de 60 consultas por ciclo e permite atualização
  manual. A listagem de pedidos utiliza o endpoint existente, sem paginação; grandes
  históricos continuam exigindo evolução desse contrato.

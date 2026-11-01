# Regras de Domínio — Repasse

## Modelos financeiros

Novas vendas usam `REPASSE_POSTERIOR`: o marketplace recebe a cobrança e deve a
parcela congelada ao vendedor. Pedidos existentes permanecem `SPLIT_LEGADO`, sem
nova transferência financeira. A identificação do modelo é imutável.

## Cálculo por venda

A comissão inicial é 20% do valor bruto, configurável somente para novos pedidos.
No checkout, o pedido persiste percentual, comissão, valor do vendedor e recebedor.
Usar `Decimal`, duas casas e `ROUND_HALF_UP`. Retomada, webhook e repasse não podem
recalcular a comissão usando a configuração atual.

Para `REPASSE_POSTERIOR`:

```text
comissao = arredondar(valor_bruto * percentual_da_venda / 100)
valor_vendedor = valor_bruto - comissao
resultado_marketplace = comissao - tarifas_do_provedor
```

O marketplace absorve as tarifas do provedor. Uma venda de R$ 100 com 20% de comissão
paga R$ 80 ao vendedor. No split legado, preserva-se o cálculo histórico, incluindo
a tarifa do provedor descontada do vendedor. Cálculos e instruções são protegidos
contra alteração também no banco de dados.

## Estados e elegibilidade

- Pagamento confirmado cria o repasse em `AGUARDANDO_ENTREGA`, sem `pago_em`.
- Entrega confirmada pelo PIN inicia `EM_PERIODO_CONTESTACAO` e a janela de sete dias.
- Somente após o prazo, sem contestação ativa nem reembolso não cancelado, pode
  passar para `PRONTO_PARA_LIBERACAO`.
- O vendedor deve estar ativo e possuir destino Pix conferido por administrador.
- Uma contestação ativa coloca o repasse em `BLOQUEADO`.
- Reembolso confirmado antes da transferência coloca o repasse em `REEMBOLSADO`.
- A aprovação administrativa ou o job autorizado inicia `PROCESSANDO`.
- Somente confirmação externa do crédito leva a `PAGO` e permite concluir o pedido.
- Rejeição final leva a `FALHOU` para análise administrativa. Não criar outra
  instrução automaticamente nem trocar sua chave após uma resposta incerta.
- `CANCELADO` representa encerramento antes da transferência.

Um estorno do recebimento depois de iniciada a transferência exige conciliação e
tratamento administrativo; não comprova recuperação do valor já enviado ao vendedor.

Para teste manual, `OBRA_CIRCULAR_MP_PAYOUTS_TEST_SKIP_WAIT=true` permite liberar
após a confirmação da entrega, sem esperar sete dias. Só é aceito em ambiente
`local`/`test`, com `MP_PAYOUTS_TEST_MODE=true` e `MP_LIVE_MODE=false`. Mantém todos
os demais bloqueios, os prazos gravados na entrega e os valores da venda. A
instrução registra `PRAZO_DISPENSADO_EM_TESTE` na auditoria. Restaurar `false` e
reiniciar o backend ao terminar o teste.

## Instrução, auditoria e concorrência

O painel e o job usam o mesmo serviço. Somente administradores ativos autorizam a
saída de dinheiro. O navegador informa apenas o identificador do repasse; valores,
destino e referências vêm de dados persistidos. O destino e o corpo enviado são
criptografados, e a instrução congela destino, valor, ambiente e idempotência.

Pedido e repasse são bloqueados na preparação. Um lease impede envios simultâneos.
Retentativas reutilizam a mesma instrução. Estados HTTP aceitos e `approved` são
intermediários; confirmação ocorre por consulta ao provedor, inclusive após webhook.
As operações geram uma trilha de auditoria que não pode ser alterada nem excluída.

Uma instrução `PROCESSANDO` sem ID externo não permite consultar o payout. Após
o lease, um administrador pode retomar a mesma instrução, preservando chave,
destino e valor; a retomada exige nova confirmação e respeita todos os bloqueios.
O painel oferece **Retomar envio** nesse caso e **Consultar transferência** apenas
quando existe identificador externo. Erros registram a etapa e, quando disponível,
o status HTTP; o código técnico filtrado é exibido sem divulgar o payload bruto.

## Compatibilidade com o split

No `SPLIT_LEGADO`, `PAGO` representa o split automático confirmado com o pagamento.
Seus estados posteriores de contestação são operacionais e não retêm saldo. O
novo serviço recusa transferências para qualquer pedido desse modelo, mesmo quando
seu estado tenha sido alterado para acompanhar o pós-venda.

## Estado da implementação e testes

### Transferência entre contas de teste por e-mail

O destino `CONTA_MP_TESTE` representa uma conta Mercado Pago identificada por
e-mail `@testuser.com`, não uma chave Pix do tipo `EMAIL`. Ele é permitido somente
em `local`/`test`, com `MP_PAYOUTS_TEST_MODE=true` e `MP_LIVE_MODE=false`. No payload
de Payouts, usa `type=account` e `account.email`, sem objeto `pix`.

O teto por envio é `OBRA_CIRCULAR_MP_PAYOUTS_TEST_ACCOUNT_MAX_AMOUNT`, com padrão de
R$ 20. A confirmação administrativa, a entrega, os bloqueios, a auditoria e a
conciliação continuam obrigatórios. O limite e o modo de teste são verificados
também na retomada de uma instrução existente. O destino continua criptografado.
Uma instrução Pix já iniciada não pode ser convertida em transferência por e-mail.

Em produção, o destino por conta de teste é recusado; o destino Pix real precisa
ser cadastrado e conferido antes de iniciar uma nova instrução.

A abertura pela API e pela tela do comprador coloca pedido e repasse em
contestação/bloqueio na mesma transação. O painel e o job não liberam esse repasse,
mesmo quando o prazo termina. A geração e validação do PIN são responsabilidade de
outra feature da equipe; esta implementação exige os dados da entrega confirmada.

A tentativa externa em modo de teste por `account.email` recebeu HTTP 403
`PA_UNAUTHORIZED_RESULT_FROM_POLICIES` na criação do Payouts. Nenhum identificador
externo ou crédito foi confirmado. A autorização da conta de origem permanece
pendente de esclarecimento com o Mercado Pago. Os testes automatizados verificam
payload, modo de teste, limites, bloqueios e conciliação com um provedor simulado.

Contrato, configuração, painel e job: [repasse posterior](../repasse-posterior.md).

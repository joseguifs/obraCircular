# Recebimento centralizado e repasse posterior

Novas vendas usam `REPASSE_POSTERIOR`: a conta Mercado Pago da Obra Circular recebe
a cobrança do Checkout Pro sem split. A parcela do vendedor é transferida após a
entrega confirmada e o encerramento dos sete dias corridos de contestação.

## Comissão preservada por venda

O percentual padrão passa a ser 20%, configurado em
`OBRA_CIRCULAR_MARKETPLACE_FEE_PERCENT`. No início do checkout, o pedido congela:

- modelo financeiro e ID da conta recebedora;
- valor total e percentual de comissão, com duas casas decimais;
- comissão calculada com `Decimal` e `ROUND_HALF_UP`;
- valor do vendedor, igual ao total menos a comissão.

Em uma venda de R$ 100 com comissão de 20%, o vendedor recebe R$ 80. Se o provedor
cobrar R$ 5, eles são absorvidos pelos R$ 20 da plataforma. O repasse registra a
tarifa efetiva sem subtraí-la novamente da parcela do vendedor.

Uma alteração do percentual na configuração afeta somente novos pedidos. Retomada
do checkout, webhook, reembolso e repasse usam os dados gravados no pedido. Triggers
no PostgreSQL impedem alterações dos cálculos já persistidos, inclusive por SQL.

## Compatibilidade

Todos os pedidos existentes são identificados como `SPLIT_LEGADO`. Quando já há
repasse, seu percentual é preservado; nos demais pedidos antigos aplica-se o
percentual histórico de 25%. A migration nunca converte uma venda existente para o
novo recebimento, nem realiza qualquer transferência.

Preferências antigas são consultadas com o token OAuth do vendedor; cobranças novas
usam exclusivamente o token da plataforma. Os webhooks novos conferem o recebedor
externo da cobrança contra o snapshot do pedido. Reembolsos usam a credencial da
conta que recebeu aquela venda. Vendas com split são impedidas de gerar um segundo
pagamento pelo serviço de repasses, independentemente de seus estados operacionais.

## Configuração

```dotenv
OBRA_CIRCULAR_MP_ACCESS_TOKEN=token_da_conta_recebedora
OBRA_CIRCULAR_MP_MARKETPLACE_USER_ID=id_da_conta_recebedora
OBRA_CIRCULAR_MARKETPLACE_FEE_PERCENT=20.00
OBRA_CIRCULAR_MP_PAYOUTS_ENABLED=false
OBRA_CIRCULAR_MP_PAYOUTS_TEST_MODE=true
OBRA_CIRCULAR_MP_PAYOUTS_TEST_SKIP_WAIT=false
OBRA_CIRCULAR_MP_PAYOUTS_NOTIFICATION_URL=https://sua-api/api/v1/webhooks/mercado-pago/payouts
OBRA_CIRCULAR_MP_PAYOUTS_PRIVATE_KEY_PATH=
```

O token fica somente no backend. Para testes, configure a conta recebedora de teste
e mantenha `MP_LIVE_MODE=false` e `MP_PAYOUTS_TEST_MODE=true`. O envio de repasses
exige habilitar explicitamente `MP_PAYOUTS_ENABLED`. Não houve importação automática
de credenciais nem habilitação de transferências durante esta implementação.

Para um teste manual sem aguardar os sete dias, configure
`OBRA_CIRCULAR_MP_PAYOUTS_TEST_SKIP_WAIT=true` e reinicie o backend. Essa exceção
só é aceita em `local`/`test`, com `MP_PAYOUTS_TEST_MODE=true` e `MP_LIVE_MODE=false`.
A entrega ainda precisa estar confirmada pelo vendedor, e contestações,
reembolsos, disponibilidade do recebimento e demais verificações continuam
bloqueando a liberação. O prazo da entrega e a comissão permanecem gravados, e a
auditoria registra `PRAZO_DISPENSADO_EM_TESTE`. Para restaurar os sete dias, volte
a variável para `false` e reinicie o backend; nenhuma alteração de datas é necessária.

Em produção, use `MP_LIVE_MODE=true`, `MP_PAYOUTS_TEST_MODE=false` e uma chave privada
Ed25519 em arquivo protegido fora do repositório. A chave pública deve ser cadastrada
com a equipe de Integrações do Mercado Pago. As requisições assinam exatamente os
bytes enviados e as chaves e destinos não aparecem nas respostas administrativas.

O modelo comercial de recebimento de vendas de terceiros na conta da empresa e os
requisitos fiscais/contratuais devem ser confirmados antes da ativação produtiva.

## Administração

O cadastro de destino no admin oferece somente tipos de chave Pix, inclusive em
desenvolvimento. A opção **Conta Mercado Pago de teste por e-mail** foi removida
do formulário após a tentativa de homologação descrita abaixo.

O suporte interno de teste usa `CONTA_MP_TESTE` e exige e-mail `@testuser.com`.
O servidor o recusa fora de `local`/`test`, sem modo de teste
ou com `MP_LIVE_MODE=true`. O limite por repasse é R$ 20 por padrão, configurável por
`OBRA_CIRCULAR_MP_PAYOUTS_TEST_ACCOUNT_MAX_AMOUNT`. A modalidade em produção
continua sendo Pix; não basta trocar credenciais mantendo um destino de teste.

A tela `/admin/repasses` lista os valores congelados, percentual da venda, tarifas,
valor do vendedor, situação, prazo e motivo de bloqueio. O administrador cadastra uma
chave Pix após conferir sua titularidade e confirma expressamente cada liberação.
Alterar o destino cadastrado afeta somente instruções ainda não criadas.

Rotas autenticadas de administrador:

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/api/v1/admin/payouts` | Lista paginada e filtro por status |
| PUT | `/api/v1/admin/users/{id}/payout-destination` | Cadastra destino conferido |
| POST | `/api/v1/admin/payouts/{id}/release` | Libera ou retoma a mesma instrução |
| POST | `/api/v1/admin/payouts/{id}/reconcile` | Consulta o provedor |
| GET | `/api/v1/admin/payouts/{id}/events` | Histórico de operações |

A liberação recebe somente o ID do repasse. O backend carrega valor, destino e
referências de registros confiáveis. O cadastro do destino exige tipo de chave,
chave e `titularidade_conferida=true`; a chave e o corpo da instrução são criptografados.

## Execução e conciliação

O serviço exige pedido entregue, confirmação de entrega, prazo estritamente vencido,
pagamento aprovado, vendedor ativo, destino conferido e ausência de contestação ativa
ou reembolso não cancelado. Ele também consulta o recebimento no Mercado Pago,
conferindo recebedor, valor, aprovação, ausência de devolução e disponibilidade.
O provedor continua responsável por validar o saldo suficiente na transferência.

O pedido e o repasse são bloqueados na transação de preparação. Uma instrução durável
congela o corpo e a chave de idempotência antes da chamada externa. Um lease impede
execuções simultâneas, e qualquer retomada mantém a mesma chave e o mesmo destino.

Uma resposta de criação não prova o crédito. A consulta da transação confirma valor,
moeda e referência. Somente `success/accredited` ou `processed/approved` levam a
`PAGO`; `approved`, `created` e `success/in_progress` continuam `PROCESSANDO`.
Falhas finais ficam `FALHOU` para análise. A aplicação não cria automaticamente uma
segunda instrução após rejeição. Resultado incerto conserva `PROCESSANDO`.

### Envio sem identificador ou erro de acesso

`PROCESSANDO` sem identificador externo representa uma tentativa sem resultado
confirmado; não comprova envio, débito ou crédito no Mercado Pago. Sem esse ID,
o painel oculta **Consultar transferência**. Após o lease de dois minutos, se os
demais critérios continuarem válidos, oferece **Retomar envio**, com confirmação
expressa do administrador. A retomada reutiliza a instrução, a chave de
idempotência, o destino e os valores originais; não cria outra transferência local.
O job de conciliação não reenvia automaticamente uma instrução sem identificador.

Falhas na consulta do recebimento são diferenciadas de falhas no envio e na
consulta do payout. Erros HTTP do provedor chegam ao painel com status HTTP e
código técnico filtrado, sem corpo bruto, tokens ou dados bancários. O histórico
registra a etapa, por exemplo `ERRO_ENVIO_HTTP_403`. Erros 401/403 indicam conferir
a credencial e a autorização de Payouts da conta de origem; cadastrar uma chave
Pix no destino não altera as permissões da conta que envia.

Tentativas antigas que registraram somente `CONFIRMACAO_PENDENTE` não permitem
reconstruir o erro HTTP original. Não atribuir a elas a causa de uma consulta de
diagnóstico posterior, nem marcar como `PAGO` sem confirmação externa.

Notificações usam o endpoint dedicado de repasses, validação HMAC e o worker
persistente existente. O conteúdo recebido apenas provoca uma consulta ao provedor.
O job também concilia instruções pendentes, inclusive quando um webhook não chega.
O histórico financeiro é protegido contra alteração e exclusão por trigger.

Um estorno do recebimento após a saída de dinheiro gera o evento
`RECEBIMENTO_ESTORNADO_APOS_LIBERACAO`; ele não deve ser tratado como devolução
automática da transferência ao vendedor.

## Job

Somente conciliação, sem iniciar novas transferências:

```powershell
python -m app.jobs.repasses
```

Liberação dos pedidos elegíveis, com operador administrativo identificado:

```powershell
python -m app.jobs.repasses --liberar --admin-email financeiro@empresa.com
```

O job e o painel usam o mesmo serviço. Configure um scheduler somente quando a
execução automática estiver autorizada e o provedor estiver habilitado. O processo
de geração e validação do PIN será desenvolvido por outro membro da equipe. A
contestação e o repasse consomem os dados da entrega confirmada, conforme o contrato
descrito em [abertura de contestação](abertura-contestacao.md).

## Estado da validação

A abertura e o histórico estão disponíveis ao comprador em
`/pedidos/{pedido_id}/contestacoes`, pelo detalhe do pedido. A abertura bloqueia o
repasse na mesma transação e impede a liberação pelo painel e pelo job.

O operador informou cadastrar uma chave Pix na conta do vendedor de teste; a
transferência externa ainda não foi homologada nesse ambiente. Os
testes automatizados usam gateways simulados para verificar envio, conciliação,
idempotência e bloqueios, incluindo abrir uma contestação pela API e tentar liberar
o repasse depois do prazo. Uma resposta simulada de crédito não comprova uma
transferência no Mercado Pago.

## Contrato do provedor e limites de verificação

### Teste externo por e-mail — 1 de novembro de 2026

Foi executada uma tentativa autorizada de R$ 16,00 no pedido `7646d6e5`, usando uma
conta de origem identificada pela API como conta de teste e o destinatário de teste
informado pelo operador. O envio usou `type=account`, `account.email`, BRL e
`X-test-token: true`, mantendo a instrução durável, autorização administrativa,
idempotência e conciliação do serviço existente. O recebimento foi verificado antes
do POST. A entrega foi preparada manualmente para esse teste, sem implementar PIN.

A criação retornou HTTP 403 `PA_UNAUTHORIZED_RESULT_FROM_POLICIES`, sem payout ID
ou confirmação de crédito. O repasse permanece `PROCESSANDO` com uma única
instrução; não houve reenvio automático. A tentativa Pix anterior do pedido
`2e22c6c9` não foi alterada. Alterar o tipo de destino não resolveu a autorização
exigida pelo Mercado Pago.

O relatório local fica em `.codex-e2e/artifacts/payout-account-result.json`, fora
do código da aplicação e sem credenciais. O script de teste recusa repetir a
preparação se o pedido já tiver uma instrução.

A referência brasileira de Payouts confirma `account.email` para identificar uma
conta Mercado Pago. Esse fluxo não depende do cadastro de chave Pix:
[API de criação de Payouts](https://www.mercadopago.com.br/developers/pt/reference/online-payments/payouts/create-bank-transaction/post).

### Fontes e verificações

A adaptação seguiu a skill `mercadopago:mp-integrate` e a referência pública
brasileira consultada para `POST /v1/payouts`. O verificador estático empacotado
`validate-payouts-integration.mjs . BR` foi executado, mas não aprovou o projeto:
exige rotas JavaScript específicas e o contrato anterior de Transaction Intent.
Isso diverge do contrato publicado e usado nesta aplicação Python. Não é uma
certificação desta implementação. Os testes locais e o POST externo são
verificações distintas; a recusa HTTP 403 continua impedindo homologar o repasse.

A implementação segue o contrato público de Payouts com Pix/BRL atualmente publicado
no domínio brasileiro: criação em `/v1/payouts` e consulta de transações do lote.
Cada instrução deste sistema contém uma única transferência.

A referência empacotada da skill `mp-integrate` descreve para o Brasil o contrato
anterior de Transaction Intent, diferente da documentação pública consultada. Seu
verificador estático também exige estruturas JavaScript; não certifica esta integração
Python. Os contratos efetivamente usados são cobertos por testes de HTTP, assinatura,
persistência, autorização e conciliação. Nenhuma transferência real foi executada.

Referências oficiais:

- [Payouts](https://www.mercadopago.com.br/developers/pt/docs/payouts/overview)
- [Transferências Pix/BRL](https://www.mercadopago.com.br/developers/pt/docs/payouts/integration-configuration/money-transfers)
- [Status e erros](https://www.mercadopago.com.br/developers/pt/docs/payouts/resources/transaction-status-and-errors)
- [Produção e assinatura](https://www.mercadopago.com.br/developers/pt/docs/payouts/go-to-production)

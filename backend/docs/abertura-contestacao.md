# Abertura de contestação

O comprador autenticado pode comunicar um problema de um pedido entregue. As regras
estão em [domain/contestacao.md](domain/contestacao.md),
[domain/entrega.md](domain/entrega.md) e [domain/repasse.md](domain/repasse.md).

## Abrir

```http
POST /api/v1/orders/{pedido_id}/disputes
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "motivo": "PRODUTO_DANIFICADO",
  "descricao": "Parte das telhas chegou quebrada."
}
```

O motivo deve ser um dos valores definidos no domínio. A descrição é obrigatória,
tem de 1 a 5.000 caracteres e perde espaços no início e no fim. Campos extras são
rejeitados; comprador e status são definidos pelo backend.

A resposta `201` contém identificador, pedido, comprador, motivo, descrição,
status `ABERTA`, resolução e datas de criação, atualização e resolução.

Na mesma transação, o backend:

1. bloqueia o pedido do comprador com `SELECT ... FOR UPDATE`;
2. verifica que não existe contestação ativa, inclusive uma já `ACEITA`;
3. exige pedido e entrega `ENTREGUE`, com confirmação e prazo registrados;
4. bloqueia o repasse e recusa estados `PROCESSANDO`, `PAGO`, `CANCELADO` ou
   `REEMBOLSADO`;
5. verifica o horário UTC após adquirir os bloqueios, aceitando o instante exato
   de `prazo_contestacao_em`;
6. cria a contestação, altera o pedido para `EM_CONTESTACAO` e o repasse para
   `BLOQUEADO`, preenchendo `bloqueado_em`.

O bloqueio do pedido serializa aberturas simultâneas. O índice parcial existente
`uq_contestacoes_uma_ativa_por_pedido` também garante a unicidade no banco. Uma
requisição repetida recebe `409`, sem criar outra contestação. Qualquer falha desfaz
as três alterações.

## Consultar o histórico

```http
GET /api/v1/orders/{pedido_id}/disputes
Authorization: Bearer {access_token}
```

Retorna `items` e `total`, com as contestações mais recentes primeiro. Somente o
comprador pode consultar. Pedidos inexistentes ou de outra pessoa retornam `404`
nos dois endpoints.

## Erros

| HTTP | Código | Situação |
|---|---|---|
| 401 | `AUTHENTICATION_REQUIRED` | Autenticação ausente ou inválida |
| 404 | `ORDER_NOT_FOUND` | Pedido inexistente ou de outro comprador |
| 409 | `DISPUTE_ALREADY_ACTIVE` | Já há contestação ativa |
| 409 | `DISPUTE_ORDER_NOT_DELIVERED` | Pedido não está entregue |
| 409 | `DISPUTE_DELIVERY_NOT_CONFIRMED` | Entrega sem confirmação ou prazo |
| 409 | `DISPUTE_PAYOUT_NOT_FOUND` | Repasse ausente |
| 409 | `DISPUTE_PAYOUT_NOT_ALLOWED` | Estado incompatível do repasse |
| 409 | `DISPUTE_DEADLINE_EXPIRED` | Prazo encerrado |
| 422 | Validação da requisição | Motivo, descrição ou campos inválidos |

## Tela do comprador

O caminho **Meus pedidos → Ver pedido → Abrir contestação** leva à rota autenticada
`/pedidos/{pedido_id}/contestacoes`, incluída no build de produção. Para os demais
estados do pedido, o link aparece como **Ver contestações**, permitindo consultar o
histórico mesmo depois de encerrada a solicitação.

A tela mostra identificação, situação e total do pedido, motivo, descrição de até
5.000 caracteres, protocolo, datas, status e resolução registrada no histórico.
Pedidos ainda não entregues ou com contestação ativa ficam com a abertura
desabilitada. O backend verifica confirmação da entrega, prazo e estado do repasse
ao enviar; uma recusa aparece na tela e preserva a descrição digitada.

Durante o envio, novos cliques são bloqueados. Após sucesso ou erro, pedido e
histórico são consultados novamente, inclusive quando a resposta da abertura se
perde na rede. Falhas de consulta permitem nova tentativa.

A página auxiliar `/testes/contestacao?pedido={pedido_id}` continua disponível
somente em desenvolvimento, com um seletor dos pedidos do comprador. Ela reutiliza
o mesmo formulário e histórico da tela definitiva. A abertura nas duas telas é
real no backend conectado.

## Integração com o pagamento atual

Novas vendas usam `REPASSE_POSTERIOR`, detalhado em
[repasse-posterior.md](repasse-posterior.md). O Checkout Pro recebe na conta da
plataforma, sem split. O pagamento aprovado cria o repasse em
`AGUARDANDO_ENTREGA`, sem transferência ao vendedor.

Com entrega confirmada e prazo válido, a contestação muda o repasse para
`BLOQUEADO`. O painel e o job de liberação recusam a transferência desse repasse,
mesmo após o prazo. A abertura não chama o Mercado Pago para bloquear saldo, não
realiza transferência e não solicita chargeback ou reembolso automaticamente.

Em pedidos `SPLIT_LEGADO`, o split já foi executado: o bloqueio tem efeito apenas
operacional e contábil, sem recuperar ou reter o dinheiro enviado. Um repasse ainda
`PAGO` impede a abertura. O serviço de repasses nunca realiza outra transferência
para esse modelo.

## Dependência da entrega/PIN e escopo

A geração e validação do PIN serão implementadas por outro membro da equipe. Esta
feature consome o resultado dessa confirmação e não cria nem valida PINs.
O módulo de entrega deverá persistir, de forma atômica:

- pedido e entrega com status `ENTREGUE`;
- `confirmado_em` em UTC e `confirmado_por` com o vendedor do pedido;
- `prazo_contestacao_em = confirmado_em + 7 dias corridos`.

O serviço de repasses atualiza o repasse para `EM_PERIODO_CONTESTACAO` ao encontrar
essa entrega. A abertura também aceita `AGUARDANDO_ENTREGA` quando os dados da
entrega já estão válidos, sem depender da execução prévia do job.

Até a integração do PIN, testes usam registros de pós-entrega preparados por
fixtures. A tela não altera dados para tornar um pedido elegível. Análise e
resolução administrativa das contestações permanecem uma etapa separada; os
status e regras dessa etapa estão especificados no domínio.

## Verificação e limites

No backend:

```powershell
python -m pytest tests/test_contestacao.py tests/test_repasse_posterior.py -q
```

Os testes de abertura exercitam `SPLIT_LEGADO` e `REPASSE_POSTERIOR`, autenticação,
titularidade, validação, histórico, estados ativos, prazo inclusivo em UTC,
estados de pedido/repasse e rollback. O teste integrado abre pela API no modelo
novo, avança o relógio para depois do prazo e verifica que o job e a liberação
administrativa mantêm o bloqueio, sem criar instrução ou chamar a transferência.

No frontend:

```powershell
npm.cmd test -- src/features/pagamentos/ContestacaoPage.test.tsx src/features/pagamentos/ContestacaoTestePage.test.tsx
npm.cmd run build
```

Há cobertura da navegação real a partir de Meus pedidos, formulário, sessão,
histórico, erros, retomada após login e prevenção de duplicações.

As contas de teste usadas neste projeto não possuem chave Pix para receber o
repasse. Por isso, a liberação e a confirmação financeira são verificadas com
gateways simulados, sem uma transferência real entre contas Mercado Pago. Esses
testes validam o comportamento da aplicação, não a homologação financeira do
provedor. Essa limitação não impede testar a abertura e seu bloqueio do repasse.

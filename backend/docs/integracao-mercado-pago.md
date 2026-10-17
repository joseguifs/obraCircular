# Integração Mercado Pago — Checkout Pro Marketplace

## Decisões do MVP

- Produto: Checkout Pro com Split de Pagamentos 1:1.
- Comissão da Obra Circular: 25% do valor bruto da venda.
- Credencial: token OAuth individual do vendedor.
- Meios iniciais: Pix, cartão de crédito e cartão de débito.
- Boleto: desabilitado enquanto a política de reserva longa não for definida.
- Repasse: razão contábil do split automático, não retenção financeira.
- Estoque: reserva atômica de 30 minutos ao criar o checkout.
- Fonte de verdade: consulta do backend ao Mercado Pago após webhook assinado.

## Pré-requisitos do vendedor

Para anunciar e receber pagamentos, o vendedor deve:

1. possuir uma conta Mercado Pago;
2. concluir o nível de identificação exigido pelo Split 1:1 (KYC 6 segundo a
   documentação atual do produto);
3. aceitar a autorização OAuth solicitada pela Obra Circular;
4. manter a conta ativa e com dados verdadeiros;
5. aceitar as políticas de venda, reembolso, contestação, chargeback e recuperação de
   valores cobertos pelo fundo do marketplace.

A API não fornece neste fluxo uma garantia suficiente para substituir toda a validação
de KYC. O onboarding deve informar o requisito, e a ativação produtiva deve ser validada
também no painel/retorno operacional do Mercado Pago.

## Configuração local com um túnel ngrok

Execute API e frontend em terminais diferentes:

```powershell
cd backend
python -m alembic upgrade head
python -m fastapi dev app/main.py
```

```powershell
cd frontend
npm.cmd run dev
```

Abra o túnel para a API:

```powershell
ngrok http 8000
```

Copie a URL HTTPS apresentada, por exemplo:

```text
https://exemplo-1234.ngrok-free.app
```

No painel da aplicação Mercado Pago, configure:

- Redirect URL OAuth:
  `https://exemplo-1234.ngrok-free.app/api/v1/integrations/mercado-pago/oauth/callback`
- Webhook de pagamentos:
  `https://exemplo-1234.ngrok-free.app/api/v1/webhooks/mercado-pago`
- Evento: Pagamentos.
- Revele e copie a assinatura secreta do webhook.
- Habilite Authorization Code com PKCE.

O backend possui um retorno intermediário público. O Mercado Pago retorna pelo ngrok e
o backend redireciona o navegador para `http://localhost:5173`. Isso evita precisar de
um segundo túnel apenas para o frontend.

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

```env
OBRA_CIRCULAR_MP_CLIENT_ID=ID_DA_APLICACAO
OBRA_CIRCULAR_MP_CLIENT_SECRET=SEGREDO_DA_APLICACAO
OBRA_CIRCULAR_MP_WEBHOOK_SECRET=ASSINATURA_SECRETA_DO_WEBHOOK
OBRA_CIRCULAR_MP_TOKEN_ENCRYPTION_KEY=CHAVE_ALEATORIA_COM_32_OU_MAIS_CARACTERES
OBRA_CIRCULAR_MP_PUBLIC_BASE_URL=https://exemplo-1234.ngrok-free.app
OBRA_CIRCULAR_MP_OAUTH_REDIRECT_URI=https://exemplo-1234.ngrok-free.app/api/v1/integrations/mercado-pago/oauth/callback
OBRA_CIRCULAR_MP_WEBHOOK_URL=https://exemplo-1234.ngrok-free.app/api/v1/webhooks/mercado-pago
OBRA_CIRCULAR_MARKETPLACE_FEE_PERCENT=25.00
OBRA_CIRCULAR_STOCK_RESERVATION_MINUTES=30
```

Para gerar a chave local sem gravá-la no histórico do terminal:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Reinicie o backend quando a URL do ngrok mudar. No plano gratuito, a URL normalmente
muda a cada nova sessão; atualize também o painel do Mercado Pago.

## Fluxo do vendedor

1. O vendedor abre `/perfil/mercado-pago`.
2. O frontend chama `POST /api/v1/payment-accounts/mercado-pago/connect`.
3. O backend cria `state` de uso único e PKCE S256, persistindo somente o hash do
   `state` e o verifier criptografado.
4. O navegador é redirecionado para a autorização do Mercado Pago.
5. O callback troca o código por access/refresh tokens.
6. Tokens são criptografados com AES-GCM antes da persistência.
7. A conta local passa para `ATIVA`.
8. Tokens próximos da expiração são renovados automaticamente.

## Fluxo do comprador e reserva de estoque

1. O comprador informa quantidade, entrega/retirada e endereço.
2. `POST /api/v1/orders/checkout` bloqueia o anúncio com `SELECT ... FOR UPDATE`.
3. Reservas vencidas daquele anúncio são liberadas.
4. O backend valida estoque, vendedor, endereço e impede autocompra.
5. A quantidade é removida do estoque disponível e o pedido registra a expiração.
6. Uma preferência é criada com o token OAuth do vendedor, `marketplace_fee` de 25%,
   `external_reference` igual ao pedido e IDs locais em `metadata`.
7. O frontend redireciona para o `sandbox_init_point` fora de produção.
8. Falha ao criar a preferência cancela o pedido e devolve a reserva.

Execute o job abaixo pelo menos uma vez por minuto em desenvolvimento/staging:

```powershell
python -m app.jobs.liberar_reservas
```

Em produção, configure um scheduler externo. O job usa `FOR UPDATE SKIP LOCKED`, pode
rodar em mais de uma instância e devolve cada reserva no máximo uma vez.

## Webhook e confirmação

O endpoint valida `x-signature` usando HMAC-SHA256 sobre o manifesto oficial:

```text
id:{data.id};request-id:{x-request-id};ts:{ts};
```

Depois da validação:

1. registra/localiza o evento por identificador externo;
2. consulta `GET /v1/payments/{id}` com o token do vendedor;
3. confere referência, valor, vendedor e ambiente;
4. atualiza pagamento e pedido em uma transação;
5. cria uma única linha de `Repasse` como `PAGO` após aprovação;
6. marca o evento como processado.

Um retorno de navegador nunca aprova o pedido. A tela apenas consulta o status local
enquanto o webhook é validado.

## Cancelamento e reembolso

- `POST /api/v1/orders/{id}/cancel`: cancela pedido ainda não pago e libera a reserva.
- `POST /api/v1/orders/{id}/refund`: solicita reembolso integral antes da confirmação
  da entrega.
- A mesma chave de idempotência é reutilizada nas retentativas do reembolso.
- O estoque só é devolvido quando o provedor confirmar o reembolso.

No Split 1:1, cada parte devolve sua parcela. Se o vendedor não tiver saldo, o Mercado
Pago pode recusar a operação. Nesse caso o registro local passa para `FALHOU`.

### Fundo de cobertura e recuperação futura

A política aprovada é:

1. calcular a parcela que o vendedor não conseguiu restituir;
2. verificar o saldo disponível do fundo do marketplace;
3. se houver saldo, devolver a diferença por um meio autorizado;
4. registrar o valor como dívida do vendedor;
5. elevar temporariamente a comissão das vendas futuras desse vendedor;
6. aplicar somente o adicional à amortização até zerar a dívida;
7. voltar automaticamente aos 25%.

A API pública do Split 1:1 não disponibiliza a etapa 3 como complemento do mesmo
reembolso. Por isso, o MVP não movimenta o fundo automaticamente. Antes de habilitar
essa cobertura são necessários:

- definir o meio autorizado de devolução/transferência;
- obter acesso ao saldo do fundo por API ou conciliação;
- definir a sobretaxa e um teto que preserve valor líquido positivo ao vendedor;
- criar autorização administrativa com trilha de auditoria;
- formalizar a cláusula de compensação com o vendedor.

Nunca se deve marcar um reembolso como concluído apenas porque a plataforma decidiu
cobri-lo; é necessária confirmação do meio externo utilizado.

## Políticas essenciais antes da produção

Publicar e obter aceite versionado para:

- termos do marketplace e autorização para cobrança da comissão de 25%;
- responsabilidade do vendedor por descrição, origem e entrega do material;
- materiais proibidos, perigosos ou sujeitos a licença;
- política de cancelamento, reembolso, contestação interna e chargeback bancário;
- autorização de compensação de dívida em vendas futuras;
- política de privacidade/LGPD e finalidade dos dados compartilhados;
- canal e prazo de atendimento;
- responsabilidades por documento fiscal e tributos de cada parte.

Chargeback bancário e contestação interna são processos diferentes. Produção deve
assinar também o tópico de chargebacks e implementar o respectivo caso administrativo
antes de ampliar volume.

## Testes de homologação

Use contas de teste separadas de integrador, vendedor e comprador, todas do Brasil.
Validar no mínimo:

- OAuth concluído, negado, expirado e repetido;
- renovação e revogação de token;
- compra Pix e cartões aprovada, pendente e recusada;
- duas compras simultâneas da última unidade;
- expiração e cancelamento de reserva;
- webhook duplicado, fora de ordem, inválido e temporariamente indisponível;
- valor ou referência divergente;
- reembolso aprovado e recusado por saldo;
- retorno do checkout sem webhook;
- indisponibilidade do Mercado Pago durante criação da preferência.

## Referências oficiais

- Split 1:1: https://www.mercadopago.com.br/developers/pt/docs/split-payments/split-1-1/overview
- Integração marketplace: https://www.mercadopago.com.br/developers/pt/docs/split-payments/split-1-1/integration-configuration/integrate-marketplace
- OAuth: https://www.mercadopago.com.br/developers/pt/docs/security/oauth/creation
- Checkout Pro: https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-pro-preferences/overview
- Webhooks: https://www.mercadopago.com.br/developers/pt/docs/checkout-pro-preferences/payment-notifications
- Reembolsos: https://www.mercadopago.com.br/developers/pt/docs/checkout-pro-orders/refunds-cancellations

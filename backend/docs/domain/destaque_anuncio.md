# Regras de Domínio — Destaque de Anúncio

O vendedor pode pagar para que um anúncio próprio apareça antes dos demais nas
listagens. O pagamento segue o mesmo fluxo do checkout de pedidos: uma Preference do
Checkout Pro criada com a credencial da Obra Circular e confirmada somente pelo
webhook, após consulta ao Mercado Pago.

## Preço e duração

- Valor fixo configurado em `OBRA_CIRCULAR_FEATURED_AD_PRICE` (padrão `10.00` BRL).
- Duração configurada em `OBRA_CIRCULAR_FEATURED_AD_DURATION_DAYS` (padrão 7 dias).
- Valor e duração são congelados na compra (`destaques_anuncio`); alterar a
  configuração não afeta compras já iniciadas.

## Status

- `AGUARDANDO_PAGAMENTO`
- `ATIVO`
- `CANCELADO`
- `REEMBOLSADO`

O status do pagamento (`status_pagamento`) usa os mesmos valores de `pagamentos`.

## Regras

- Somente o vendedor do anúncio pode destacá-lo, e apenas anúncios `ATIVO` e não
  excluídos podem iniciar uma compra de destaque.
- Existe no máximo uma compra `AGUARDANDO_PAGAMENTO` por anúncio (índice único
  parcial). Repetir a solicitação enquanto o checkout é válido retorna o
  `init_point` da mesma Preference; um checkout vencido é cancelado e substituído.
- O `external_reference` enviado ao Mercado Pago é `destaque:<id>`. O webhook usa esse
  prefixo para separar o destaque dos pedidos, cujo `external_reference` é o UUID do
  pedido.
- O webhook confere recebedor (`collector_id`), valor e modo do pagamento antes de
  aplicar qualquer mudança.
- A aprovação ativa o destaque e grava o fim do período em `anuncios.destaque_ate`.
  Se o anúncio já estiver em destaque, o novo período começa ao fim do atual
  (extensão, sem sobreposição).
- Pagamento aprovado é sempre honrado, mesmo que o checkout local já tenha vencido.
- Pagamento recusado mantém a compra `AGUARDANDO_PAGAMENTO` para nova tentativa;
  cancelado encerra a compra.
- Estorno ou chargeback marca a compra como `REEMBOLSADO` e retira de
  `anuncios.destaque_ate` apenas o tempo ainda não usufruído daquela compra.
- O processamento é idempotente: reaplicar o mesmo evento ou o mesmo estado não
  estende o destaque novamente, e estados antigos não rebaixam uma compra aprovada.
- As listagens de anúncios ordenam primeiro os anúncios com `destaque_ate` futuro e,
  em seguida, pela data de publicação.

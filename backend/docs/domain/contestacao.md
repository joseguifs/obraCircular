# Regras de Domínio — Contestação

Uma contestação trata problemas comunicados pelo comprador durante a janela
operacional anterior ao repasse.

## Motivos

- `PEDIDO_NAO_RECEBIDO`
- `PRODUTO_DANIFICADO`
- `QUANTIDADE_INCORRETA`
- `PRODUTO_DIFERENTE`
- `ENTREGA_PARCIAL`
- `OUTRO`

## Status

- `ABERTA`
- `EM_ANALISE`
- `AGUARDANDO_VENDEDOR`
- `ACEITA`
- `RECUSADA`
- `CANCELADA`
- `RESOLVIDA`

São ativas as contestações com status `ABERTA`, `EM_ANALISE`,
`AGUARDANDO_VENDEDOR` ou `ACEITA`. `ACEITA` continua ativa até que o reembolso
seja confirmado pelo provedor.

## Abertura

- Somente o comprador do pedido pode abrir a contestação.
- O pedido precisa estar `ENTREGUE`.
- O momento atual deve ser menor ou igual a `prazo_contestacao_em`.
- O repasse ainda não pode estar `PROCESSANDO` nem `PAGO`.
- Apenas uma contestação ativa pode existir por pedido.
- A abertura altera o pedido para `EM_CONTESTACAO` e o repasse para `BLOQUEADO`,
  na mesma transação.

Não é possível abrir uma contestação interna após o prazo ou após o repasse. Isso
não elimina direitos legais eventualmente aplicáveis, inclusive reclamações por
vícios do produto; esses casos devem seguir pelo atendimento administrativo fora
do fluxo automatizado de contestação.

## Resolução prevista

Estas regras especificam a etapa administrativa, ainda separada da implementação
de abertura e consulta do comprador.

- `ACEITA`: cria o único reembolso integral e mantém pedido e repasse bloqueados.
- `RECUSADA` ou `CANCELADA`: o pedido retorna para `ENTREGUE`. Se o prazo ainda não
  terminou, o repasse retorna para `EM_PERIODO_CONTESTACAO`; caso contrário, retorna
  para `PAGO`, conforme a razão contábil do Split 1:1 descrita em `repasse.md`.
  Isso não executa uma transferência financeira.
- `RESOLVIDA`: somente pode ser definido depois que o reembolso estiver
  `CONCLUIDO`.
- Se o reembolso falhar, a contestação permanece `ACEITA` e ativa.

As mudanças da contestação, do pedido e do repasse devem ocorrer na mesma
transação do banco.

## API de abertura

O comprador abre uma contestação com `POST /api/v1/orders/{pedido_id}/disputes` e
consulta o histórico com `GET /api/v1/orders/{pedido_id}/disputes`. No modelo atual
`REPASSE_POSTERIOR`, o bloqueio impede a liberação da transferência Pix ao vendedor,
conforme [repasse.md](repasse.md). Nos pedidos `SPLIT_LEGADO`, é apenas operacional
e contábil: não desfaz o split já executado pelo Mercado Pago.

A interface autenticada está em `/pedidos/{pedido_id}/contestacoes`, acessível pelo
detalhe do pedido e incluída no build de produção. A geração e validação do PIN pertencem
a outra feature da equipe; a abertura exige os dados de confirmação já gravados.

Contrato, validações e códigos de erro: [abertura de contestação](../abertura-contestacao.md).

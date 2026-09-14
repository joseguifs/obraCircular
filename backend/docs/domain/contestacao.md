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

## Resolução

- `ACEITA`: cria o único reembolso integral e mantém pedido e repasse bloqueados.
- `RECUSADA` ou `CANCELADA`: o pedido retorna para `ENTREGUE`. Se o prazo ainda não
  terminou, o repasse retorna para `EM_PERIODO_CONTESTACAO`; caso contrário, passa
  para `PRONTO_PARA_LIBERACAO`.
- `RESOLVIDA`: somente pode ser definido depois que o reembolso estiver
  `CONCLUIDO`.
- Se o reembolso falhar, a contestação permanece `ACEITA` e ativa.

As mudanças da contestação, do pedido e do repasse devem ocorrer na mesma
transação do banco.

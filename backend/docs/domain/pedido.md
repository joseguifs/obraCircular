# Regras de Domínio — Pedido

Este documento define as regras do recurso `Pedido`. Para o MVP, cada pedido
contém um único anúncio e uma quantidade desse anúncio.

## Modalidade de entrega

Valores permitidos:

- `ENTREGA`
- `RETIRADA`

Para `ENTREGA`, `endereco_entrega_id` e `endereco_entrega_snapshot` são
obrigatórios. Para `RETIRADA`, ambos devem ser `NULL`.

As duas modalidades possuem um registro de entrega, confirmação por PIN e prazo
de contestação. Na retirada, o PIN confirma que o material foi recebido no local
combinado.

## Status

- `AGUARDANDO_PAGAMENTO`
- `PAGAMENTO_APROVADO`
- `PREPARANDO_ENTREGA`
- `EM_ENTREGA`
- `ENTREGUE`
- `EM_CONTESTACAO`
- `CONCLUIDO`
- `CANCELADO`
- `REEMBOLSADO`

## Transições principais

```text
AGUARDANDO_PAGAMENTO -> PAGAMENTO_APROVADO -> PREPARANDO_ENTREGA
PREPARANDO_ENTREGA -> EM_ENTREGA -> ENTREGUE -> CONCLUIDO
```

- Na modalidade `RETIRADA`, `PREPARANDO_ENTREGA` pode passar diretamente para
  `ENTREGUE` após a validação do PIN.
- O pedido passa para `ENTREGUE` somente após a validação do PIN.
- Ao abrir uma contestação, `ENTREGUE` passa para `EM_CONTESTACAO`.
- Se a contestação for recusada ou cancelada, o pedido retorna para `ENTREGUE`.
- O pedido passa para `CONCLUIDO` somente quando o prazo de contestação terminar
  sem contestação ativa e o repasse estiver `PAGO`.
- Um reembolso confirmado altera o pedido para `REEMBOLSADO`.

## Cancelamento

- Enquanto estiver `AGUARDANDO_PAGAMENTO`, o comprador pode cancelar o pedido e a
  reserva de estoque é devolvida exatamente uma vez.
- Depois da aprovação do pagamento e antes da confirmação do PIN, o comprador
  pode solicitar cancelamento. O pedido passa para `CANCELADO`, o estoque é
  devolvido uma única vez e inicia-se o reembolso integral.
- Depois da confirmação do PIN, não há cancelamento comum. O comprador deve abrir
  uma contestação dentro do prazo.
- Após a confirmação do reembolso de um pedido cancelado, o estado final do pedido
  passa de `CANCELADO` para `REEMBOLSADO`.

## Independência dos processos

O status do pedido representa apenas seu estado geral. Pagamento, entrega,
contestação, reembolso e repasse possuem estados próprios e continuam sendo suas
respectivas fontes de verdade.

## Reserva de estoque

- A criação do checkout bloqueia o anúncio e reduz sua quantidade disponível.
- `estoque_reservado_em` e `reserva_expira_em` delimitam a reserva.
- `estoque_liberado_em` impede devolução duplicada por jobs, cancelamentos ou webhooks.
- A reserva inicial expira em 30 minutos, configurável por ambiente.
- Boleto fica desabilitado no MVP porque seu prazo assíncrono é incompatível com essa
  reserva curta. Pix e cartões permanecem disponíveis.
- Um job deve executar `python -m app.jobs.liberar_reservas` periodicamente.

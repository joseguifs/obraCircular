import type { Pedido } from './types'

export const STATUS_PEDIDO: Record<Pedido['status'], string> = {
  AGUARDANDO_PAGAMENTO: 'Aguardando pagamento',
  PAGAMENTO_APROVADO: 'Pagamento aprovado',
  PREPARANDO_ENTREGA: 'Preparando entrega',
  EM_ENTREGA: 'Em entrega',
  ENTREGUE: 'Entregue',
  EM_CONTESTACAO: 'Em contestação',
  CONCLUIDO: 'Concluído',
  CANCELADO: 'Cancelado',
  REEMBOLSADO: 'Reembolsado',
}

export function reembolsoPendente(pedido: Pedido): boolean {
  return pedido.reembolso?.status === 'SOLICITADO' || pedido.reembolso?.status === 'PROCESSANDO'
}

export function deveAtualizarPedido(pedido: Pedido): boolean {
  return pedido.status === 'AGUARDANDO_PAGAMENTO' || reembolsoPendente(pedido) || (
    pedido.status === 'CANCELADO' && pedido.pagamento?.status === 'APROVADO' && !pedido.reembolso
  )
}

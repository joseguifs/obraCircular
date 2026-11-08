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
  return aguardaEntrega(pedido) || pedido.status === 'AGUARDANDO_PAGAMENTO' || reembolsoPendente(pedido) || (
    pedido.status === 'CANCELADO' && pedido.pagamento?.status === 'APROVADO' && !pedido.reembolso
  )
}

export function aguardaEntrega(pedido: Pedido): boolean {
  return ['PAGAMENTO_APROVADO', 'PREPARANDO_ENTREGA', 'EM_ENTREGA'].includes(pedido.status)
    && !reembolsoPendente(pedido)
}

// A API repete todas as validações ao abrir, inclusive em caso de alterações concorrentes.
export function impedimentoContestacao(pedido: Pedido, agora: number): string {
  if (pedido.status !== 'ENTREGUE') return 'Este pedido precisa estar entregue para abrir uma contestação.'
  if (pedido.entrega !== undefined && (!pedido.entrega || pedido.entrega.status !== 'ENTREGUE'
    || !pedido.entrega.confirmado_em || !pedido.entrega.prazo_contestacao_em)) {
    return 'A entrega precisa estar confirmada com um prazo de contestação.'
  }
  if (pedido.repasse_status === null) return 'O repasse deste pedido ainda não está disponível.'
  if (['PROCESSANDO', 'PAGO', 'CANCELADO', 'REEMBOLSADO'].includes(pedido.repasse_status ?? '')) {
    return 'A situação do repasse não permite abrir uma contestação.'
  }
  const prazo = pedido.entrega?.prazo_contestacao_em
  if (prazo && agora > new Date(prazo).getTime()) return 'O prazo para abrir uma contestação terminou.'
  return ''
}

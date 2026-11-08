import type { ContestacaoMotivo, ContestacaoStatus } from './types'

export const MOTIVOS_CONTESTACAO: Record<ContestacaoMotivo, string> = {
  PEDIDO_NAO_RECEBIDO: 'Pedido não recebido',
  PRODUTO_DANIFICADO: 'Produto danificado',
  QUANTIDADE_INCORRETA: 'Quantidade incorreta',
  PRODUTO_DIFERENTE: 'Produto diferente do anunciado',
  ENTREGA_PARCIAL: 'Entrega parcial',
  OUTRO: 'Outro motivo',
}

export const STATUS_CONTESTACAO: Record<ContestacaoStatus, string> = {
  ABERTA: 'Aberta',
  EM_ANALISE: 'Em análise',
  AGUARDANDO_VENDEDOR: 'Aguardando vendedor',
  ACEITA: 'Aceita',
  RECUSADA: 'Recusada',
  CANCELADA: 'Cancelada',
  RESOLVIDA: 'Resolvida',
}

// Espelham STATUS_PENDENTES e STATUS_ATIVOS de backend/app/services/contestacao.py.
const PENDENTES: readonly ContestacaoStatus[] = ['ABERTA', 'EM_ANALISE', 'AGUARDANDO_VENDEDOR']

/** Aguarda decisão do administrador. */
export function contestacaoPendente(status: ContestacaoStatus): boolean {
  return PENDENTES.includes(status)
}

/** Impede abrir outra contestação no mesmo pedido (ACEITA segue ativa até o reembolso). */
export function contestacaoAtiva(status: ContestacaoStatus): boolean {
  return contestacaoPendente(status) || status === 'ACEITA'
}

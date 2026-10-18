export interface ContaMercadoPago {
  provedor: 'MERCADO_PAGO'
  status: 'PENDENTE' | 'ATIVA' | 'BLOQUEADA' | 'DESCONECTADA'
  conta_externa_id: string | null
  autorizado_em: string | null
  token_expira_em: string | null
}

export interface CheckoutPayload {
  anuncio_id: string
  quantidade: number
  modalidade_entrega: 'ENTREGA' | 'RETIRADA'
  endereco_entrega_id: string | null
}

export interface CheckoutResponse {
  pedido_id: string
  pagamento_id: string
  preferencia_externa_id: string
  init_point: string
  reserva_expira_em: string
  valor_total: string
  taxa_marketplace: string
}

export interface Pedido {
  id: string
  anuncio_id: string
  comprador_id: string
  quantidade: number
  preco_unitario: string
  valor_total: string
  modalidade_entrega: 'ENTREGA' | 'RETIRADA'
  status:
    | 'AGUARDANDO_PAGAMENTO'
    | 'PAGAMENTO_APROVADO'
    | 'PREPARANDO_ENTREGA'
    | 'EM_ENTREGA'
    | 'ENTREGUE'
    | 'EM_CONTESTACAO'
    | 'CONCLUIDO'
    | 'CANCELADO'
    | 'REEMBOLSADO'
  pagamento: {
    id: string
    status: string
    pagamento_externo_id: string | null
    status_detalhe: string | null
  } | null
  reembolso?: Reembolso | null
}

export interface Reembolso {
  id: string
  pedido_id: string
  status: 'SOLICITADO' | 'PROCESSANDO' | 'CONCLUIDO' | 'RECUSADO' | 'FALHOU' | 'CANCELADO'
  valor: string
  reembolso_externo_id: string | null
}

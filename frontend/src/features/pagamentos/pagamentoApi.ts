import { apiRequest } from '../../lib/api'
import type {
  CheckoutPayload,
  CheckoutResponse,
  ContaMercadoPago,
  Pedido,
  Reembolso,
} from './types'

const MP_RETURN_TO_KEY = 'obraCircular:mercadoPagoReturnTo'

export function consultarContaMercadoPago(): Promise<ContaMercadoPago> {
  return apiRequest<ContaMercadoPago>('/payment-accounts/mercado-pago')
}

export async function conectarContaMercadoPago(returnTo?: string): Promise<void> {
  if (returnTo) sessionStorage.setItem(MP_RETURN_TO_KEY, returnTo)
  try {
    const resposta = await apiRequest<{ authorization_url: string }>(
      '/payment-accounts/mercado-pago/connect',
      { method: 'POST' },
    )
    window.location.assign(resposta.authorization_url)
  } catch (erro) {
    if (returnTo) sessionStorage.removeItem(MP_RETURN_TO_KEY)
    throw erro
  }
}

export function consumirRetornoMercadoPago(): string | null {
  const returnTo = sessionStorage.getItem(MP_RETURN_TO_KEY)
  sessionStorage.removeItem(MP_RETURN_TO_KEY)
  if (!returnTo || !returnTo.startsWith('/') || returnTo.startsWith('//')) return null
  return returnTo
}

export async function createPreferenceCheckout(
  dados: CheckoutPayload,
  endpoint = '/orders/checkout',
): Promise<CheckoutResponse> {
  const resposta = await apiRequest<CheckoutResponse>(endpoint, {
    method: 'POST',
    body: JSON.stringify(dados),
  })
  sessionStorage.setItem('obraCircular:lastOrderId', resposta.pedido_id)
  return resposta
}

export function consultarPedido(pedidoId: string): Promise<Pedido> {
  return apiRequest<Pedido>(`/orders/${pedidoId}`)
}

export function listarPedidos(): Promise<{ items: Pedido[]; total: number }> {
  return apiRequest<{ items: Pedido[]; total: number }>('/orders')
}

export function cancelarCheckout(pedidoId: string): Promise<void> {
  return apiRequest<void>(`/orders/${pedidoId}/cancel`, { method: 'POST' })
}

export function solicitarReembolso(pedidoId: string): Promise<Reembolso> {
  return apiRequest<Reembolso>(`/orders/${pedidoId}/refund`, { method: 'POST' })
}

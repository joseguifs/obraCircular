import { apiRequest } from '../../lib/api'
import type {
  CheckoutPayload,
  CheckoutResponse,
  ContaMercadoPago,
  Pedido,
} from './types'

export function consultarContaMercadoPago(): Promise<ContaMercadoPago> {
  return apiRequest<ContaMercadoPago>('/payment-accounts/mercado-pago')
}

export async function conectarContaMercadoPago(): Promise<void> {
  const resposta = await apiRequest<{ authorization_url: string }>(
    '/payment-accounts/mercado-pago/connect',
    { method: 'POST' },
  )
  window.location.assign(resposta.authorization_url)
}

export async function iniciarCheckout(dados: CheckoutPayload): Promise<void> {
  const resposta = await apiRequest<CheckoutResponse>('/orders/checkout', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
  sessionStorage.setItem('obraCircular:lastOrderId', resposta.pedido_id)
  window.location.assign(resposta.checkout_url)
}

export function consultarPedido(pedidoId: string): Promise<Pedido> {
  return apiRequest<Pedido>(`/orders/${pedidoId}`)
}

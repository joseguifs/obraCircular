import { apiRequest } from '../../lib/api'
import type { DestaqueCheckout, DestaqueCompra, DestaquePreco } from './types'

export const REFERENCIA_DESTAQUE = 'destaque:'
const ULTIMO_DESTAQUE_KEY = 'obraCircular:lastFeaturedId'

export function consultarPrecoDestaque(): Promise<DestaquePreco> {
  return apiRequest<DestaquePreco>('/featured-ads/pricing')
}

export async function iniciarCheckoutDestaque(anuncioId: string): Promise<DestaqueCheckout> {
  const resposta = await apiRequest<DestaqueCheckout>('/featured-ads/checkout', {
    method: 'POST',
    body: JSON.stringify({ anuncio_id: anuncioId }),
  })
  sessionStorage.setItem(ULTIMO_DESTAQUE_KEY, resposta.destaque_id)
  return resposta
}

export function consultarDestaque(destaqueId: string): Promise<DestaqueCompra> {
  return apiRequest<DestaqueCompra>(`/featured-ads/${destaqueId}`)
}

/** Extrai o id da compra de destaque do `external_reference` devolvido pelo Mercado Pago. */
export function destaqueDaReferencia(referencia: string | null): string | null {
  if (!referencia?.startsWith(REFERENCIA_DESTAQUE)) return null
  return referencia.slice(REFERENCIA_DESTAQUE.length) || null
}

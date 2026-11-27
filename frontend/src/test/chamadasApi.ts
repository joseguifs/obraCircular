/**
 * Chamadas feitas à API, sem contar a listagem pública de anúncios que a vitrine
 * "Em destaque agora" das telas públicas faz ao abrir.
 */
export function chamadasAlemDaVitrine(fetchMock: { mock: { calls: unknown[][] } }): unknown[][] {
  return fetchMock.mock.calls.filter(([url]) => !String(url).includes('/ads?'))
}

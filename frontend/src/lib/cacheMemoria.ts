interface Entrada<T> {
  promessa: Promise<T>
  expiraEm: number
}

export interface CacheMemoria<T> {
  /** Devolve o valor guardado ou chama `carregar`, compartilhando a mesma requisição em andamento. */
  obter(chave: string, carregar: () => Promise<T>): Promise<T>
  /** Descarta uma chave, ou todas quando nenhuma é informada. */
  invalidar(chave?: string): void
}

const todosOsCaches = new Set<Map<string, Entrada<unknown>>>()

/**
 * Cache em memória com validade, para dados públicos que quase nunca mudam
 * (categorias, preço do destaque). Fica só na aba aberta: recarregar a página limpa tudo.
 *
 * Não use para dados de um usuário específico nem para o que muda a cada compra,
 * como anúncios, estoque e pedidos.
 */
export function criarCacheMemoria<T>(validadeMs: number): CacheMemoria<T> {
  const entradas = new Map<string, Entrada<T>>()
  todosOsCaches.add(entradas as Map<string, Entrada<unknown>>)

  return {
    obter(chave, carregar) {
      const atual = entradas.get(chave)
      if (atual && atual.expiraEm > Date.now()) return atual.promessa

      const promessa = carregar()
      entradas.set(chave, { promessa, expiraEm: Date.now() + validadeMs })
      // Falhas não ficam guardadas: a próxima chamada tenta de novo.
      promessa.catch(() => {
        if (entradas.get(chave)?.promessa === promessa) entradas.delete(chave)
      })
      return promessa
    },
    invalidar(chave) {
      if (chave === undefined) entradas.clear()
      else entradas.delete(chave)
    },
  }
}

/** Esvazia todos os caches em memória (usado entre os testes). */
export function limparCachesMemoria(): void {
  todosOsCaches.forEach((entradas) => entradas.clear())
}

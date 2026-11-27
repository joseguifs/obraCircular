import { afterEach, describe, expect, it, vi } from 'vitest'
import { criarCacheMemoria, limparCachesMemoria } from './cacheMemoria'

afterEach(() => {
  vi.useRealTimers()
})

describe('criarCacheMemoria', () => {
  it('reaproveita o valor dentro da validade', async () => {
    const cache = criarCacheMemoria<number>(1000)
    const carregar = vi.fn(async () => 42)

    expect(await cache.obter('a', carregar)).toBe(42)
    expect(await cache.obter('a', carregar)).toBe(42)
    expect(carregar).toHaveBeenCalledTimes(1)
  })

  it('compartilha a mesma requisição quando duas telas pedem ao mesmo tempo', async () => {
    const cache = criarCacheMemoria<string>(1000)
    let resolver: (valor: string) => void = () => {}
    const carregar = vi.fn(() => new Promise<string>((resolve) => { resolver = resolve }))

    const primeira = cache.obter('a', carregar)
    const segunda = cache.obter('a', carregar)
    resolver('pronto')

    await expect(Promise.all([primeira, segunda])).resolves.toEqual(['pronto', 'pronto'])
    expect(carregar).toHaveBeenCalledTimes(1)
  })

  it('busca de novo depois que a validade passa', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-27T12:00:00Z'))
    const cache = criarCacheMemoria<number>(1000)
    const carregar = vi.fn().mockResolvedValueOnce(1).mockResolvedValueOnce(2)

    expect(await cache.obter('a', carregar)).toBe(1)
    vi.setSystemTime(new Date('2026-11-27T12:00:01.001Z'))
    expect(await cache.obter('a', carregar)).toBe(2)
  })

  it('não guarda falhas', async () => {
    const cache = criarCacheMemoria<number>(1000)
    const carregar = vi.fn().mockRejectedValueOnce(new Error('sem rede')).mockResolvedValueOnce(7)

    await expect(cache.obter('a', carregar)).rejects.toThrow('sem rede')
    expect(await cache.obter('a', carregar)).toBe(7)
    expect(carregar).toHaveBeenCalledTimes(2)
  })

  it('invalida uma chave, todas as chaves ou todos os caches', async () => {
    const cache = criarCacheMemoria<string>(60_000)
    const carregar = vi.fn(async () => 'valor')

    await cache.obter('a', carregar)
    await cache.obter('b', carregar)
    cache.invalidar('a')
    await cache.obter('a', carregar)
    await cache.obter('b', carregar)
    expect(carregar).toHaveBeenCalledTimes(3)

    cache.invalidar()
    await cache.obter('b', carregar)
    expect(carregar).toHaveBeenCalledTimes(4)

    limparCachesMemoria()
    await cache.obter('b', carregar)
    expect(carregar).toHaveBeenCalledTimes(5)
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'
import { atualizarCategoria, buscarCategoria, listarCategoriasAtivas } from './categoriaApi'

const categoria = {
  id: '0cdf91cd-132f-4e64-bfd9-aac74442f1fd',
  nome: 'Estrutura',
  descricao: null,
  status: 'ATIVA',
}

function resposta(body: unknown) {
  return { ok: true, status: 200, json: async () => body }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('cache de categorias', () => {
  it('busca as categorias ativas uma vez e reaproveita entre telas', async () => {
    const fetchMock = vi.fn(async () => resposta({ items: [categoria], total: 1, offset: 0, limit: 100 }))
    vi.stubGlobal('fetch', fetchMock)

    expect(await listarCategoriasAtivas()).toEqual([categoria])
    expect(await listarCategoriasAtivas()).toEqual([categoria])
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('reaproveita a categoria consultada pelo id', async () => {
    const fetchMock = vi.fn(async () => resposta(categoria))
    vi.stubGlobal('fetch', fetchMock)

    await buscarCategoria(categoria.id)
    await buscarCategoria(categoria.id)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('descarta o que estava guardado depois que uma categoria é alterada', async () => {
    const renomeada = { ...categoria, nome: 'Estruturas metálicas' }
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === 'PATCH') return resposta(renomeada)
      return resposta({ items: [categoria], total: 1, offset: 0, limit: 100 })
    })
    vi.stubGlobal('fetch', fetchMock)

    await listarCategoriasAtivas()
    await atualizarCategoria(categoria.id, { nome: renomeada.nome })
    await listarCategoriasAtivas()

    const listagens = fetchMock.mock.calls.filter(([url]) => String(url).includes('/categories?'))
    expect(listagens).toHaveLength(2)
  })
})

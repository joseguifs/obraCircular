import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MeusAnunciosPage } from './MeusAnunciosPage'

const anuncio = {
  id: '9b9dbe1c-c0df-414d-b82f-b5fe97b284b2',
  titulo: 'Perfis metálicos para drywall',
  descricao: 'Sobra de obra em bom estado.',
  categoria_id: '0cdf91cd-132f-4e64-bfd9-aac74442f1fd',
  vendedor_id: 'd68c0c92-ab56-4f8e-862e-bbc91e31eb70',
  endereco_id: '6e2d754a-71fc-490f-b98c-66140c9a32ac',
  preco: '420.00',
  imagem_url: null,
  imagem_capa_url: '/uploads/anuncios/9b9dbe1c-c0df-414d-b82f-b5fe97b284b2/capa.webp',
  quantidade: 40,
  status: 'ATIVO',
  postado_em: new Date(Date.now() - 2 * 86_400_000).toISOString(),
  atualizado_em: new Date().toISOString(),
  encerrado_em: null,
}

const encerrado = {
  ...anuncio,
  id: 'a1a1a1a1-c0df-414d-b82f-b5fe97b284b2',
  titulo: 'Cimento sobrando',
  imagem_capa_url: null,
  quantidade: 0,
  status: 'ENCERRADO',
  encerrado_em: new Date().toISOString(),
}

beforeEach(() => {
  window.history.replaceState({}, '', '/anuncios/meus')
  sessionStorage.setItem(
    'obra-circular:sessao',
    JSON.stringify({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      expiraEm: Date.now() + 900_000,
      usuario: { id: anuncio.vendedor_id, nome: 'Ana Silva' },
    }),
  )
})

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

function respostaJson(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function renderPagina() {
  return render(
    <BrowserRouter>
      <MeusAnunciosPage />
    </BrowserRouter>,
  )
}

describe('MeusAnunciosPage', () => {
  it('lista os anúncios do usuário autenticado com status e link para o detalhe', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respostaJson({ items: [anuncio, encerrado], total: 2, offset: 0, limit: 10 }))
    vi.stubGlobal('fetch', fetchMock)

    renderPagina()

    expect(await screen.findByText('Perfis metálicos para drywall')).toBeInTheDocument()
    expect(screen.getByText('Cimento sobrando')).toBeInTheDocument()
    expect(screen.getByText('Disponível')).toBeInTheDocument()
    expect(screen.getByText('Encerrado')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: `Ver anúncio ${anuncio.titulo}` })).toHaveAttribute(
      'href',
      `/anuncios/${anuncio.id}`,
    )
    expect(fetchMock.mock.calls[0][0]).toContain('/ads/mine?offset=0&limit=10')
  })

  it('refaz a busca ao filtrar por situação', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respostaJson({ items: [anuncio, encerrado], total: 2, offset: 0, limit: 10 }))
      .mockResolvedValueOnce(respostaJson({ items: [encerrado], total: 1, offset: 0, limit: 10 }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderPagina()
    await screen.findByText('Perfis metálicos para drywall')

    await user.click(screen.getByRole('button', { name: 'Encerrados' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(fetchMock.mock.calls[1][0]).toContain('status=ENCERRADO')
    expect(await screen.findByText('Cimento sobrando')).toBeInTheDocument()
    expect(screen.queryByText('Perfis metálicos para drywall')).not.toBeInTheDocument()
  })

  it('mostra mensagem quando o usuário ainda não publicou anúncios', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(respostaJson({ items: [], total: 0, offset: 0, limit: 10 })),
    )

    renderPagina()

    expect(await screen.findByText('Nenhum anúncio por aqui')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Novo anúncio' })).toHaveAttribute('href', '/anuncios/novo')
  })
})

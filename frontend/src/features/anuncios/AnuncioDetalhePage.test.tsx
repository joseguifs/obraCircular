import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AnuncioDetalhePage } from './AnuncioDetalhePage'

const anuncio = {
  id: '9b9dbe1c-c0df-414d-b82f-b5fe97b284b2',
  titulo: 'Perfis metálicos para drywall',
  descricao: 'Quarenta perfis sem uso, armazenados em local coberto.',
  categoria_id: '0cdf91cd-132f-4e64-bfd9-aac74442f1fd',
  vendedor_id: 'e6d754a7-1fc4-490f-b98c-66140c9a32ac',
  endereco_id: '6e2d754a-71fc-490f-b98c-66140c9a32ac',
  preco: '420.00',
  imagem_url: null,
  quantidade: 40,
  status: 'ATIVO',
  postado_em: new Date(Date.now() - 2 * 86_400_000).toISOString(),
  atualizado_em: new Date().toISOString(),
  encerrado_em: null,
}

const categoria = {
  id: anuncio.categoria_id,
  nome: 'Estrutura',
  descricao: null,
  status: 'ATIVA',
  criado_em: new Date().toISOString(),
  atualizado_em: new Date().toISOString(),
}

function resposta(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function renderPagina() {
  return render(
    <MemoryRouter initialEntries={[`/anuncios/${anuncio.id}`]}>
      <Routes>
        <Route path="/anuncios/:anuncioId" element={<AnuncioDetalhePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('AnuncioDetalhePage', () => {
  it('exibe os dados completos e permite navegar pela galeria', async () => {
    const imagens = [
      {
        id: 'imagem-1',
        anuncio_id: anuncio.id,
        url: `/uploads/anuncios/${anuncio.id}/foto-1.png`,
        nome_original: 'foto-1.png',
        mime_type: 'image/png',
        tamanho_bytes: 120,
        ordem: 0,
        criado_em: new Date().toISOString(),
      },
      {
        id: 'imagem-2',
        anuncio_id: anuncio.id,
        url: `/uploads/anuncios/${anuncio.id}/foto-2.webp`,
        nome_original: 'foto-2.webp',
        mime_type: 'image/webp',
        tamanho_bytes: 240,
        ordem: 1,
        criado_em: new Date().toISOString(),
      },
    ]
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(resposta(anuncio))
      .mockResolvedValueOnce(resposta(categoria))
      .mockResolvedValueOnce(resposta({ items: imagens }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderPagina()

    expect(await screen.findByRole('heading', { name: anuncio.titulo })).toBeInTheDocument()
    expect(screen.getByText(categoria.nome)).toBeInTheDocument()
    expect(screen.getByText(anuncio.descricao)).toBeInTheDocument()
    expect(screen.getByText('40 unidades disponíveis')).toBeInTheDocument()
    expect(screen.getByText(/R\$\s*420,00/)).toBeInTheDocument()
    expect(screen.getByText('Preço por unidade')).toBeInTheDocument()

    const fotoPrincipal = screen.getByRole('img', {
      name: `Foto do anúncio ${anuncio.titulo}`,
    })
    expect(fotoPrincipal).toHaveAttribute('src', expect.stringContaining('foto-1.png'))
    await user.click(screen.getByRole('button', { name: 'Ver foto 2' }))
    expect(fotoPrincipal).toHaveAttribute('src', expect.stringContaining('foto-2.webp'))
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      expect.stringContaining(`/ads/${anuncio.id}`),
      expect.stringContaining(`/categories/${anuncio.categoria_id}`),
      expect.stringContaining(`/ads/${anuncio.id}/images`),
    ])
  })

  it('permite tentar novamente e tolera falha nos dados complementares', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(resposta({ detail: 'Anúncio temporariamente indisponível.' }, 503))
      .mockResolvedValueOnce(resposta(anuncio))
      .mockResolvedValueOnce(resposta({ detail: 'Categoria indisponível.' }, 503))
      .mockResolvedValueOnce(resposta({ items: [] }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderPagina()

    expect(
      await screen.findByText('Anúncio temporariamente indisponível.'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    expect(await screen.findByRole('heading', { name: anuncio.titulo })).toBeInTheDocument()
    expect(screen.getByText('Material')).toBeInTheDocument()
    expect(screen.getByText('Sem foto disponível')).toBeInTheDocument()
  })
})

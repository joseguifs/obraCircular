import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../autenticacao/AuthProvider'
import { HomePage } from './HomePage'

const usuarioId = 'd68c0c92-ab56-4f8e-862e-bbc91e31eb70'

const categoriaEstrutura = {
  id: '0cdf91cd-132f-4e64-bfd9-aac74442f1fd',
  nome: 'Estrutura',
  descricao: null,
  status: 'ATIVA',
}

const anuncio = {
  id: '9b9dbe1c-c0df-414d-b82f-b5fe97b284b2',
  titulo: 'Perfis metálicos para drywall',
  descricao: 'Sobra de obra em bom estado.',
  categoria_id: categoriaEstrutura.id,
  vendedor_id: 'e6d754a7-1fc4-490f-b98c-66140c9a32ac',
  endereco_id: '6e2d754a-71fc-490f-b98c-66140c9a32ac',
  preco: '420.00',
  imagem_url: null,
  imagem_capa_url: `/uploads/anuncios/9b9dbe1c-c0df-414d-b82f-b5fe97b284b2/capa.webp`,
  quantidade: 40,
  status: 'ATIVO',
  postado_em: new Date(Date.now() - 2 * 86_400_000).toISOString(),
  atualizado_em: new Date().toISOString(),
  encerrado_em: null,
}

beforeEach(() => {
  window.history.replaceState({}, '', '/home')
  sessionStorage.setItem(
    'obra-circular:sessao',
    JSON.stringify({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      expiraEm: Date.now() + 900_000,
      usuario: { id: usuarioId, nome: 'Ana Silva' },
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
      <AuthProvider>
        <HomePage />
      </AuthProvider>
    </BrowserRouter>,
  )
}

describe('HomePage', () => {
  it('carrega e exibe os anúncios ativos vindos da API', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        respostaJson({ items: [categoriaEstrutura], total: 1, offset: 0, limit: 100 }),
      )
      .mockResolvedValueOnce(respostaJson({ items: [], total: 3, offset: 0, limit: 1 }))
      .mockResolvedValueOnce(respostaJson({ items: [anuncio], total: 1, offset: 0, limit: 24 }))
    vi.stubGlobal('fetch', fetchMock)

    renderPagina()

    expect(await screen.findByText('Olá, Ana')).toBeInTheDocument()
    expect(await screen.findByText('Perfis metálicos para drywall')).toBeInTheDocument()
    expect(screen.getByText(/R\$\s*420,00/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: `Foto de ${anuncio.titulo}` })).toHaveAttribute(
      'src',
      expect.stringContaining('/uploads/anuncios/'),
    )
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Estrutura' })).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: `Ver anúncio ${anuncio.titulo}` }),
    ).toHaveAttribute('href', `/anuncios/${anuncio.id}`)
  })

  it('refaz a busca ao selecionar uma categoria', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        respostaJson({ items: [categoriaEstrutura], total: 1, offset: 0, limit: 100 }),
      )
      .mockResolvedValueOnce(respostaJson({ items: [], total: 0, offset: 0, limit: 1 }))
      .mockResolvedValueOnce(respostaJson({ items: [anuncio], total: 1, offset: 0, limit: 24 }))
      .mockResolvedValueOnce(respostaJson({ items: [anuncio], total: 1, offset: 0, limit: 24 }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderPagina()
    await screen.findByText('Perfis metálicos para drywall')

    await user.click(screen.getByRole('button', { name: 'Estrutura' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
    const ultimaChamada = fetchMock.mock.calls[3][0] as string
    expect(ultimaChamada).toContain(`category_id=${categoriaEstrutura.id}`)
  })
})

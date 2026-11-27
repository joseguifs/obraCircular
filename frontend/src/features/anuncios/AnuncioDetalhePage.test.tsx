import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../autenticacao/AuthProvider'
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

const endereco = {
  id: '3b3b3b3b-71fc-490f-b98c-66140c9a32ac',
  logradouro: 'Rua das Acácias',
  numero: '120',
  cidade: 'Palmas',
  estado: 'TO',
}

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

const semPerguntas = { items: [], total: 0, offset: 0, limit: 10 }

function resposta(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

interface Cenario {
  anuncio?: unknown
  imagens?: unknown[]
  enderecos?: unknown[]
  vitrine?: unknown[]
}

/** Responde cada endpoint pela URL, sem depender da ordem das chamadas. */
function apiPorUrl(cenario: Cenario = {}) {
  return vi.fn(async (url: string) => {
    if (url.includes('/questions')) return resposta(semPerguntas)
    if (url.includes('/images')) return resposta({ items: cenario.imagens ?? [] })
    if (url.includes('/categories/')) return resposta(categoria)
    if (url.includes('/addresses')) return resposta({ items: cenario.enderecos ?? [], total: 0 })
    if (url.includes('/ads?')) {
      const itens = cenario.vitrine ?? []
      return resposta({ items: itens, total: itens.length, offset: 0, limit: 12 })
    }
    if (url.includes(`/ads/`)) return resposta(cenario.anuncio ?? anuncio)
    return resposta({})
  })
}

function renderPagina() {
  return render(
    <MemoryRouter initialEntries={[`/anuncios/${anuncio.id}`]}>
      <AuthProvider>
        <Routes>
          <Route path="/anuncios/:anuncioId" element={<AnuncioDetalhePage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('AnuncioDetalhePage', () => {
  it('exibe os dados completos e permite navegar pela galeria', async () => {
    const fetchMock = apiPorUrl({ imagens, enderecos: [endereco] })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderPagina()

    expect(await screen.findByRole('heading', { level: 1, name: anuncio.titulo })).toBeInTheDocument()
    const ficha = screen.getByRole('region', { name: 'Ficha do material' })
    expect(within(ficha).getByText(categoria.nome)).toBeInTheDocument()
    expect(within(ficha).getByText('40 unidades')).toBeInTheDocument()
    expect(screen.getByText(anuncio.descricao)).toBeInTheDocument()
    expect(screen.getByText('40 unidades disponíveis')).toBeInTheDocument()
    expect(screen.getByText(/^R\$\s*420,00$/, { selector: '.ad-detail-preco' })).toBeInTheDocument()
    expect(screen.getByText('por unidade')).toBeInTheDocument()

    const fotoPrincipal = screen.getByRole('img', {
      name: `Foto do anúncio ${anuncio.titulo}`,
    })
    expect(fotoPrincipal).toHaveAttribute('src', expect.stringContaining('foto-1.png'))
    expect(screen.getByText('1 / 2')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Ver foto 2' }))
    expect(fotoPrincipal).toHaveAttribute('src', expect.stringContaining('foto-2.webp'))
    expect(screen.getByRole('button', { name: 'Ver foto 2' })).toHaveAttribute('aria-pressed', 'true')

    const urls = fetchMock.mock.calls.map(([url]) => String(url))
    expect(urls).toEqual(
      expect.arrayContaining([
        expect.stringContaining(`/ads/${anuncio.id}`),
        expect.stringContaining(`/categories/${anuncio.categoria_id}`),
        expect.stringContaining(`/ads/${anuncio.id}/images`),
        expect.stringContaining(`/ads/${anuncio.id}/questions`),
        expect.stringContaining('/users/me/addresses?limit=100'),
      ]),
    )
  })

  it('calcula o total pela quantidade e esconde o endereço na retirada', async () => {
    vi.stubGlobal('fetch', apiPorUrl({ enderecos: [endereco] }))
    const user = userEvent.setup()

    renderPagina()

    const total = await screen.findByText(/^R\$\s*420,00$/, { selector: '.ad-detail-total strong' })
    expect(screen.getByRole('button', { name: 'Diminuir quantidade' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Aumentar quantidade' }))
    await user.click(screen.getByRole('button', { name: 'Aumentar quantidade' }))
    expect(screen.getByRole('spinbutton', { name: /Quantidade/ })).toHaveValue(3)
    expect(total).toHaveTextContent(/R\$\s*1\.260,00/)

    expect(await screen.findByRole('option', { name: /Rua das Acácias, 120/ })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Retirada/ }))
    expect(screen.getByRole('button', { name: /Retirada/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByRole('combobox', { name: 'Endereço de entrega' })).not.toBeInTheDocument()
  })

  it('leva para o cadastro de endereço quando o comprador não tem nenhum', async () => {
    vi.stubGlobal('fetch', apiPorUrl({ enderecos: [] }))

    renderPagina()

    expect(await screen.findByRole('link', { name: 'Cadastrar endereço' })).toHaveAttribute(
      'href',
      '/perfil/enderecos',
    )
  })

  it('marca o anúncio pago e mostra outros destaques sem repetir o atual', async () => {
    const emDestaque = {
      ...anuncio,
      em_destaque: true,
      destaque_ate: new Date(Date.now() + 86_400_000).toISOString(),
    }
    const outro = {
      ...emDestaque,
      id: '7c7c7c7c-c0df-414d-b82f-b5fe97b284b2',
      titulo: 'Telhas de fibrocimento',
    }
    const comum = { ...anuncio, id: '8d8d8d8d-c0df-414d-b82f-b5fe97b284b2', titulo: 'Tubos PVC' }
    vi.stubGlobal('fetch', apiPorUrl({ anuncio: emDestaque, vitrine: [emDestaque, outro, comum] }))

    renderPagina()

    await screen.findByRole('heading', { level: 1, name: anuncio.titulo })
    expect(screen.getByText('Em destaque')).toBeInTheDocument()

    const outros = await screen.findByRole('region', { name: 'Também em destaque' })
    expect(
      within(outros).getByRole('link', { name: `Ver anúncio ${outro.titulo} (em destaque)` }),
    ).toHaveAttribute('href', `/anuncios/${outro.id}`)
    expect(within(outros).queryByText(anuncio.titulo)).not.toBeInTheDocument()
    expect(within(outros).queryByText(comum.titulo)).not.toBeInTheDocument()
  })

  it('permite tentar novamente e tolera falha nos dados complementares', async () => {
    let tentativas = 0
    const fetchMock = vi.fn(async (url: string) => {
      if (url.endsWith(`/ads/${anuncio.id}`)) {
        tentativas += 1
        return tentativas === 1
          ? resposta({ detail: 'Anúncio temporariamente indisponível.' }, 503)
          : resposta(anuncio)
      }
      if (url.includes('/categories/')) return resposta({ detail: 'Categoria indisponível.' }, 503)
      if (url.includes('/questions')) return resposta(semPerguntas)
      return resposta({ items: [] })
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderPagina()

    expect(
      await screen.findByText('Anúncio temporariamente indisponível.'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    expect(await screen.findByRole('heading', { level: 1, name: anuncio.titulo })).toBeInTheDocument()
    expect(screen.getAllByText('Material').length).toBeGreaterThan(0)
    expect(screen.getByText('Sem foto disponível')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Também em destaque' })).not.toBeInTheDocument()
  })
})

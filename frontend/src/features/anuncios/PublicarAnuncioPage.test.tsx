import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AnuncioPublicadoPage } from './AnuncioPublicadoPage'
import { PublicarAnuncioPage } from './PublicarAnuncioPage'

const categoria = {
  id: '0cdf91cd-132f-4e64-bfd9-aac74442f1fd',
  nome: 'Tijolos e blocos',
  descricao: null,
  status: 'ATIVA',
}

const endereco = {
  id: '6e2d754a-71fc-490f-b98c-66140c9a32ac',
  usuario_id: 'd68c0c92-ab56-4f8e-862e-bbc91e31eb70',
  cep: '01310100',
  logradouro: 'Avenida Paulista',
  numero: '1000',
  complemento: null,
  bairro: 'Bela Vista',
  cidade: 'São Paulo',
  estado: 'SP',
}

beforeEach(() => {
  window.history.replaceState({}, '', '/anuncios/novo')
  sessionStorage.setItem(
    'obra-circular:sessao',
    JSON.stringify({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      expiraEm: Date.now() + 900_000,
      usuario: { id: endereco.usuario_id, nome: 'Ana Silva' },
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
      <Routes>
        <Route path="/anuncios/novo" element={<PublicarAnuncioPage />} />
        <Route path="/anuncios/:anuncioId/publicado" element={<AnuncioPublicadoPage />} />
      </Routes>
    </BrowserRouter>,
  )
}

describe('PublicarAnuncioPage', () => {
  it('valida os campos antes de criar o anúncio', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respostaJson({ items: [categoria], total: 1, offset: 0, limit: 100 }))
      .mockResolvedValueOnce(respostaJson({ items: [endereco], total: 1, offset: 0, limit: 100 }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    renderPagina()

    await screen.findByRole('heading', { name: 'Publique seu anúncio' })
    await user.click(screen.getByRole('button', { name: 'Publicar anúncio' }))

    expect(screen.getByText('Informe um título com pelo menos 3 caracteres.')).toBeInTheDocument()
    expect(screen.getByText('Selecione uma categoria.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('publica os dados válidos e abre a confirmação', async () => {
    const anuncioId = '9b9dbe1c-c0df-414d-b82f-b5fe97b284b2'
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respostaJson({ items: [categoria], total: 1, offset: 0, limit: 100 }))
      .mockResolvedValueOnce(respostaJson({ items: [endereco], total: 1, offset: 0, limit: 100 }))
      .mockResolvedValueOnce(
        respostaJson(
          {
            id: anuncioId,
            titulo: 'Blocos de concreto',
            descricao: 'Material novo e sem avarias.',
            categoria_id: categoria.id,
            vendedor_id: endereco.usuario_id,
            endereco_id: endereco.id,
            preco: '12.50',
            quantidade: 20,
            status: 'ATIVO',
          },
          201,
        ),
      )
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    renderPagina()

    await screen.findByRole('heading', { name: 'Publique seu anúncio' })
    await user.type(screen.getByLabelText('Título'), 'Blocos de concreto')
    await user.type(screen.getByLabelText('Descrição'), 'Material novo e sem avarias.')
    await user.selectOptions(screen.getByLabelText('Categoria'), categoria.id)
    await user.type(screen.getByLabelText('Preço unitário'), '12.50')
    await user.clear(screen.getByLabelText('Quantidade'))
    await user.type(screen.getByLabelText('Quantidade'), '20')
    await user.click(screen.getByRole('radio'))
    await user.click(screen.getByRole('button', { name: 'Publicar anúncio' }))

    expect(await screen.findByText('Seu material já está no marketplace')).toBeInTheDocument()
    expect(window.location.pathname).toBe(`/anuncios/${anuncioId}/publicado`)
    expect(fetchMock).toHaveBeenCalledTimes(3)

    const [url, opcoes] = fetchMock.mock.calls[2] as [string, RequestInit]
    expect(url).toBe('http://localhost:8000/api/v1/ads')
    expect(JSON.parse(opcoes.body as string)).toEqual({
      titulo: 'Blocos de concreto',
      descricao: 'Material novo e sem avarias.',
      categoria_id: categoria.id,
      endereco_id: endereco.id,
      preco: '12.5',
      quantidade: 20,
    })
    expect((opcoes.headers as Headers).get('Authorization')).toBe('Bearer access-token')
  })

  it('permite cadastrar um endereço dentro do fluxo', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respostaJson({ items: [categoria], total: 1, offset: 0, limit: 100 }))
      .mockResolvedValueOnce(respostaJson({ items: [], total: 0, offset: 0, limit: 100 }))
      .mockResolvedValueOnce(respostaJson(endereco, 201))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    renderPagina()

    await screen.findByRole('heading', { name: 'Novo endereço' })
    await user.type(screen.getByLabelText('CEP'), '01310100')
    await user.type(screen.getByLabelText('Estado'), 'sp')
    await user.type(screen.getByLabelText('Logradouro'), 'Avenida Paulista')
    await user.type(screen.getByLabelText('Número'), '1000')
    await user.type(screen.getByLabelText('Bairro'), 'Bela Vista')
    await user.type(screen.getByLabelText('Cidade'), 'São Paulo')
    await user.click(screen.getByRole('button', { name: 'Salvar endereço' }))

    await waitFor(() => expect(screen.getByRole('radio')).toBeChecked())
    expect(screen.queryByRole('heading', { name: 'Novo endereço' })).not.toBeInTheDocument()
    const [url, opcoes] = fetchMock.mock.calls[2] as [string, RequestInit]
    expect(url).toBe('http://localhost:8000/api/v1/users/me/addresses')
    expect(JSON.parse(opcoes.body as string)).toEqual(
      expect.objectContaining({ cep: '01310100', estado: 'SP' }),
    )
  })
})

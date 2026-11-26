import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MinhasPerguntasPage } from './MinhasPerguntasPage'
import type { PerguntaUsuario } from './types'

const USUARIO_ID = 'd68c0c92-ab56-4f8e-862e-bbc91e31eb70'

function pergunta(dados: Partial<PerguntaUsuario>): PerguntaUsuario {
  return {
    id: crypto.randomUUID(),
    anuncio_id: '9b9dbe1c-c0df-414d-b82f-b5fe97b284b2',
    autor_id: USUARIO_ID,
    pergunta: 'Pergunta de teste?',
    resposta: null,
    criado_em: new Date(Date.now() - 3_600_000).toISOString(),
    respondido_em: null,
    anuncio: {
      id: '9b9dbe1c-c0df-414d-b82f-b5fe97b284b2',
      titulo: 'Telhas cerâmicas',
      status: 'ATIVO',
      imagem_capa_url: null,
    },
    ...dados,
  }
}

const feita = pergunta({
  pergunta: 'Entregam no Plano Diretor Sul?',
  resposta: 'Entregamos, sim.',
  respondido_em: new Date().toISOString(),
})

const recebida = pergunta({
  autor_id: 'outro-usuario',
  pergunta: 'Aceitam Pix?',
  anuncio_id: 'a1a1a1a1-c0df-414d-b82f-b5fe97b284b2',
  anuncio: {
    id: 'a1a1a1a1-c0df-414d-b82f-b5fe97b284b2',
    titulo: 'Blocos de concreto',
    status: 'ESGOTADO',
    imagem_capa_url: null,
  },
})

function lista(items: PerguntaUsuario[]) {
  return { items, total: items.length, offset: 0, limit: 10 }
}

function respostaJson(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

beforeEach(() => {
  window.history.replaceState({}, '', '/perguntas')
  sessionStorage.setItem(
    'obra-circular:sessao',
    JSON.stringify({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      expiraEm: Date.now() + 900_000,
      usuario: { id: USUARIO_ID, nome: 'Ana Silva' },
    }),
  )
})

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

function renderPagina() {
  return render(
    <BrowserRouter>
      <MinhasPerguntasPage />
    </BrowserRouter>,
  )
}

describe('MinhasPerguntasPage', () => {
  it('carrega só as perguntas feitas por mim ao abrir a tela', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(respostaJson(lista([feita])))
    vi.stubGlobal('fetch', fetchMock)

    renderPagina()

    expect(await screen.findByText('Entregam no Plano Diretor Sul?')).toBeInTheDocument()
    expect(screen.getByText('Entregamos, sim.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Perguntas feitas por mim' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('link', { name: 'Ver anúncio Telhas cerâmicas' })).toHaveAttribute(
      'href',
      `/anuncios/${feita.anuncio.id}`,
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toContain('/users/me/questions?tipo=FEITAS&offset=0&limit=10')
  })

  it('busca as perguntas dos meus anúncios apenas ao trocar o filtro', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respostaJson(lista([feita])))
      .mockResolvedValueOnce(respostaJson(lista([recebida])))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderPagina()
    await screen.findByText('Entregam no Plano Diretor Sul?')

    await user.click(screen.getByRole('button', { name: 'Perguntas em meus anúncios' }))

    expect(await screen.findByText('Aceitam Pix?')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[1][0]).toContain('tipo=RECEBIDAS')
    expect(screen.queryByText('Entregam no Plano Diretor Sul?')).not.toBeInTheDocument()
    expect(screen.getByText('Aguardando sua resposta')).toBeInTheDocument()
    expect(screen.getByText('Esgotado')).toBeInTheDocument()
    expect(window.location.search).toBe('?tipo=recebidas')
  })

  it('permite responder uma pergunta recebida direto da lista', async () => {
    window.history.replaceState({}, '', '/perguntas?tipo=recebidas')
    const respondida = {
      ...recebida,
      resposta: 'Aceitamos, sim.',
      respondido_em: new Date().toISOString(),
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respostaJson(lista([recebida])))
      .mockResolvedValueOnce(respostaJson(respondida))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderPagina()
    await user.type(
      await screen.findByLabelText('Responder: Aceitam Pix?'),
      'Aceitamos, sim.',
    )
    await user.click(screen.getByRole('button', { name: 'Responder' }))

    expect(await screen.findByText('Aceitamos, sim.')).toBeInTheDocument()
    expect(fetchMock.mock.calls[0][0]).toContain('tipo=RECEBIDAS')
    expect(fetchMock.mock.calls[1][0]).toContain(
      `/ads/${recebida.anuncio.id}/questions/${recebida.id}/answer`,
    )
    expect(screen.queryByText('Aguardando sua resposta')).not.toBeInTheDocument()
  })

  it('mostra um estado vazio e permite tentar de novo após erro', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respostaJson({ detail: 'Serviço indisponível.' }, 503))
      .mockResolvedValueOnce(respostaJson(lista([])))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderPagina()
    expect(await screen.findByText('Serviço indisponível.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('Você ainda não fez perguntas')).toBeInTheDocument()
  })
})

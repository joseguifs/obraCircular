import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../autenticacao/AuthProvider'
import { PerguntasAnuncio } from './PerguntasAnuncio'
import type { Anuncio, AnuncioPergunta } from './types'

const VENDEDOR_ID = 'e6d754a7-1fc4-490f-b98c-66140c9a32ac'
const COMPRADOR_ID = '1b6f1d0a-6a43-4a39-9f0e-2f5b7f1e9c11'

const anuncio: Anuncio = {
  id: '9b9dbe1c-c0df-414d-b82f-b5fe97b284b2',
  titulo: 'Telhas cerâmicas',
  descricao: 'Lote de telhas cerâmicas que sobraram da obra.',
  categoria_id: '0cdf91cd-132f-4e64-bfd9-aac74442f1fd',
  vendedor_id: VENDEDOR_ID,
  endereco_id: '6e2d754a-71fc-490f-b98c-66140c9a32ac',
  preco: '1.80',
  imagem_url: null,
  imagem_capa_url: null,
  quantidade: 300,
  status: 'ATIVO',
  postado_em: new Date().toISOString(),
  atualizado_em: new Date().toISOString(),
  encerrado_em: null,
}

function pergunta(dados: Partial<AnuncioPergunta>): AnuncioPergunta {
  return {
    id: crypto.randomUUID(),
    anuncio_id: anuncio.id,
    autor_id: 'outro-usuario',
    pergunta: 'Pergunta de teste?',
    resposta: null,
    criado_em: new Date(Date.now() - 3_600_000).toISOString(),
    respondido_em: null,
    ...dados,
  }
}

function lista(items: AnuncioPergunta[], total = items.length) {
  return { items, total, offset: 0, limit: 10 }
}

function resposta(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function entrarComo(usuarioId: string) {
  sessionStorage.setItem(
    'obra-circular:sessao',
    JSON.stringify({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      expiraEm: Date.now() + 900_000,
      usuario: {
        id: usuarioId,
        nome: 'Usuário',
        email: 'usuario@example.com',
        telefone: null,
        status: 'ATIVO',
        criado_em: new Date().toISOString(),
        atualizado_em: new Date().toISOString(),
      },
    }),
  )
}

function renderSecao(dadosAnuncio: Anuncio = anuncio) {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <PerguntasAnuncio anuncio={dadosAnuncio} />
      </AuthProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

describe('PerguntasAnuncio', () => {
  it('lista perguntas respondidas e pendentes e permite ao comprador perguntar', async () => {
    entrarComo(COMPRADOR_ID)
    const nova = pergunta({ pergunta: 'Entregam em Palmas?', autor_id: COMPRADOR_ID })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        resposta(
          lista([
            pergunta({
              pergunta: 'Ainda tem as 300 unidades?',
              resposta: 'Tem sim, pode vir buscar.',
              respondido_em: new Date().toISOString(),
            }),
            pergunta({ pergunta: 'Aceitam Pix?' }),
          ]),
        ),
      )
      .mockResolvedValueOnce(resposta(nova, 201))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderSecao()

    expect(await screen.findByText('Ainda tem as 300 unidades?')).toBeInTheDocument()
    expect(screen.getByText('Tem sim, pode vir buscar.')).toBeInTheDocument()
    expect(screen.getByText('Aguardando resposta do vendedor')).toBeInTheDocument()
    expect(screen.getByText('2 perguntas')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Responder' })).not.toBeInTheDocument()

    await user.type(screen.getByLabelText('Pergunte ao vendedor'), '  Entregam em Palmas?  ')
    await user.click(screen.getByRole('button', { name: 'Perguntar' }))

    expect(await screen.findByText('Entregam em Palmas?')).toBeInTheDocument()
    expect(screen.getByText('Sua pergunta')).toBeInTheDocument()
    expect(screen.getByText('3 perguntas')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Pergunta enviada!')
    expect(screen.getByLabelText('Pergunte ao vendedor')).toHaveValue('')

    const [url, init] = fetchMock.mock.calls[1]
    expect(url).toEqual(expect.stringContaining(`/ads/${anuncio.id}/questions`))
    expect(init).toMatchObject({ method: 'POST' })
    expect(JSON.parse(init.body as string)).toEqual({ pergunta: 'Entregam em Palmas?' })
  })

  it('valida pergunta curta sem chamar a API', async () => {
    entrarComo(COMPRADOR_ID)
    const fetchMock = vi.fn().mockResolvedValueOnce(resposta(lista([])))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderSecao()

    expect(
      await screen.findByText('Ninguém perguntou nada ainda. Seja o primeiro!'),
    ).toBeInTheDocument()
    await user.type(screen.getByLabelText('Pergunte ao vendedor'), 'oi')
    await user.click(screen.getByRole('button', { name: 'Perguntar' }))

    expect(screen.getByRole('alert')).toHaveTextContent('pelo menos 3 caracteres')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('permite ao vendedor responder perguntas pendentes e não exibe o campo de pergunta', async () => {
    entrarComo(VENDEDOR_ID)
    const pendente = pergunta({ pergunta: 'Tem nota fiscal?' })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(resposta(lista([pendente])))
      .mockResolvedValueOnce(
        resposta({
          ...pendente,
          resposta: 'Tem sim, emitimos na retirada.',
          respondido_em: new Date().toISOString(),
        }),
      )
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderSecao()

    const item = (await screen.findByText('Tem nota fiscal?')).closest('li') as HTMLElement
    expect(screen.queryByLabelText('Pergunte ao vendedor')).not.toBeInTheDocument()
    expect(screen.getByText(/1 pergunta aguardando resposta/)).toBeInTheDocument()

    await user.type(
      within(item).getByLabelText('Responder: Tem nota fiscal?'),
      'Tem sim, emitimos na retirada.',
    )
    await user.click(within(item).getByRole('button', { name: 'Responder' }))

    expect(await within(item).findByText('Tem sim, emitimos na retirada.')).toBeInTheDocument()
    expect(within(item).queryByRole('button', { name: 'Responder' })).not.toBeInTheDocument()
    expect(fetchMock.mock.calls[1][0]).toEqual(
      expect.stringContaining(`/ads/${anuncio.id}/questions/${pendente.id}/answer`),
    )
  })

  it('mostra o erro da API quando a resposta falha', async () => {
    entrarComo(VENDEDOR_ID)
    const pendente = pergunta({ pergunta: 'Ainda disponível?' })
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(resposta(lista([pendente])))
        .mockResolvedValueOnce(
          resposta(
            { detail: 'Esta pergunta já foi respondida.', code: 'QUESTION_ALREADY_ANSWERED' },
            409,
          ),
        ),
    )
    const user = userEvent.setup()

    renderSecao()

    await user.type(await screen.findByLabelText('Responder: Ainda disponível?'), 'Sim')
    await user.click(screen.getByRole('button', { name: 'Responder' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Esta pergunta já foi respondida.')
  })

  it('não oferece o campo de pergunta em anúncio encerrado', async () => {
    entrarComo(COMPRADOR_ID)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(resposta(lista([]))))

    renderSecao({ ...anuncio, status: 'ENCERRADO' })

    expect(
      await screen.findByText('Este anúncio foi encerrado e não recebe novas perguntas.'),
    ).toBeInTheDocument()
    expect(screen.queryByLabelText('Pergunte ao vendedor')).not.toBeInTheDocument()
  })

  it('carrega mais perguntas quando há outra página', async () => {
    entrarComo(COMPRADOR_ID)
    const primeiras = Array.from({ length: 10 }, (_, indice) =>
      pergunta({ pergunta: `Pergunta ${indice + 1}?` }),
    )
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(resposta(lista(primeiras, 11)))
      .mockResolvedValueOnce(
        resposta({ ...lista([pergunta({ pergunta: 'Pergunta 11?' })], 11), offset: 10 }),
      )
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderSecao()

    await user.click(await screen.findByRole('button', { name: 'Ver mais perguntas' }))

    expect(await screen.findByText('Pergunta 11?')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ver mais perguntas' })).not.toBeInTheDocument()
    expect(fetchMock.mock.calls[1][0]).toEqual(expect.stringContaining('offset=10'))
  })
})

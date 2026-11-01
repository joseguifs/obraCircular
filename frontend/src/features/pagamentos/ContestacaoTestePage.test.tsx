import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AppRouter } from '../../app/router'
import { AuthProvider } from '../autenticacao/AuthProvider'
import { salvarSessaoArmazenada } from '../autenticacao/sessaoStorage'
import { ContestacaoTestePage } from './ContestacaoTestePage'
import type { Contestacao, Pedido } from './types'

const pedidoBase: Pedido = {
  id: 'pedido-1', anuncio_id: 'anuncio-1', comprador_id: 'comprador-1', quantidade: 2,
  preco_unitario: '25.00', valor_total: '50.00', modalidade_entrega: 'RETIRADA', status: 'ENTREGUE',
  pagamento: { id: 'pagamento-1', status: 'APROVADO', pagamento_externo_id: 'mp-1', status_detalhe: null },
}

const contestacaoBase: Contestacao = {
  id: 'contestacao-1', pedido_id: 'pedido-1', comprador_id: 'comprador-1',
  motivo: 'PRODUTO_DANIFICADO', descricao: 'As telhas chegaram quebradas.', status: 'ABERTA',
  resolucao: null, resolvida_em: null, criado_em: '2026-10-31T12:00:00Z', atualizado_em: '2026-10-31T12:00:00Z',
}

function resposta(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function prepararApi(pedido: Pedido = pedidoBase, historico: Contestacao[] = []) {
  const dados = { pedidos: [pedido], pedido, historico }
  const post = vi.fn(async (_init: RequestInit) => {
    dados.pedido = { ...dados.pedido, status: 'EM_CONTESTACAO' }
    dados.historico = [contestacaoBase]
    return resposta(contestacaoBase, 201)
  })
  const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/orders')) return resposta({ items: dados.pedidos, total: dados.pedidos.length })
    if (url.endsWith('/disputes')) {
      return init.method === 'POST' ? post(init) : resposta({ items: dados.historico, total: dados.historico.length })
    }
    return resposta(dados.pedido)
  })
  vi.stubGlobal('fetch', fetchMock)
  return { dados, fetchMock, post }
}

function renderizar(url = '/testes/contestacao?pedido=pedido-1', roteadorCompleto = false) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <AuthProvider>{roteadorCompleto ? <AppRouter /> : <ContestacaoTestePage />}</AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  salvarSessaoArmazenada({
    accessToken: 'token-comprador', refreshToken: 'refresh-comprador', expiraEm: Date.now() + 900_000,
    usuario: {
      id: 'comprador-1', nome: 'Comprador', email: 'comprador3@gmail.com', telefone: null,
      status: 'ATIVO', criado_em: '', atualizado_em: '',
    },
  })
})

afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals() })

it('abre pela rota autenticada, envia o formulário e atualiza o histórico', async () => {
  const { fetchMock, post } = prepararApi()
  const user = userEvent.setup()
  renderizar(undefined, true)
  expect(await screen.findByText('Nenhuma contestação neste pedido.')).toBeInTheDocument()
  expect(screen.getByText('comprador3@gmail.com')).toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('Motivo'), 'PRODUTO_DANIFICADO')
  await user.type(screen.getByLabelText('Descreva o problema'), '  As telhas chegaram quebradas.  ')
  await user.click(screen.getByRole('button', { name: 'Abrir contestação' }))
  expect(await screen.findByText(/Contestação aberta com sucesso/)).toBeInTheDocument()
  expect(await screen.findByText('As telhas chegaram quebradas.')).toBeInTheDocument()
  expect(screen.getByText('Aberta')).toBeInTheDocument()
  expect(screen.getByText('Em contestação')).toBeInTheDocument()
  expect(post).toHaveBeenCalledOnce()
  const chamada = fetchMock.mock.calls.find(([, init]) => init.method === 'POST')!
  expect(chamada[0]).toBe('http://localhost:8000/api/v1/orders/pedido-1/disputes')
  expect(JSON.parse(chamada[1].body as string)).toEqual({
    motivo: 'PRODUTO_DANIFICADO', descricao: 'As telhas chegaram quebradas.',
  })
  expect(new Headers(chamada[1].headers).get('Authorization')).toBe('Bearer token-comprador')
  await waitFor(() => expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeDisabled())
})

it('não envia descrição vazia ou somente espaços', async () => {
  const { post } = prepararApi()
  const user = userEvent.setup()
  renderizar()
  await screen.findByText('Nenhuma contestação neste pedido.')
  expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeDisabled()
  await user.type(screen.getByLabelText('Descreva o problema'), '   ')
  expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeDisabled()
  fireEvent.submit(screen.getByRole('button', { name: 'Abrir contestação' }).closest('form')!)
  expect(post).not.toHaveBeenCalled()
})

it('bloqueia abertura para pedido ainda não entregue', async () => {
  prepararApi({ ...pedidoBase, status: 'PAGAMENTO_APROVADO' })
  renderizar()
  expect(await screen.findByText('Este pedido precisa estar entregue para abrir uma contestação.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeDisabled()
})

it.each(['ABERTA', 'EM_ANALISE', 'AGUARDANDO_VENDEDOR', 'ACEITA'] as const)(
  'impede duplicação quando já existe contestação %s', async (status) => {
    prepararApi(pedidoBase, [{ ...contestacaoBase, status }])
    renderizar()
    expect(await screen.findByText('Este pedido já está em contestação. Acompanhe o histórico abaixo.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeDisabled()
  },
)

it('mostra o erro do backend e conserva a descrição para correção', async () => {
  const { post } = prepararApi()
  post.mockResolvedValue(resposta({ detail: 'O prazo para abrir uma contestação terminou.' }, 409))
  const user = userEvent.setup()
  renderizar()
  await screen.findByText('Nenhuma contestação neste pedido.')
  await user.type(screen.getByLabelText('Descreva o problema'), 'Material danificado.')
  await user.click(screen.getByRole('button', { name: 'Abrir contestação' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('O prazo para abrir uma contestação terminou.')
  await waitFor(() => expect(screen.getByLabelText('Descreva o problema')).toBeEnabled())
  expect(screen.getByLabelText('Descreva o problema')).toHaveValue('Material danificado.')
  expect(screen.queryByText(/Contestação aberta com sucesso/)).not.toBeInTheDocument()
})

it('mantém o sucesso quando a atualização seguinte falha e permite atualizar novamente', async () => {
  const { dados, fetchMock, post } = prepararApi()
  post.mockImplementation(async () => {
    dados.pedido = { ...pedidoBase, status: 'EM_CONTESTACAO' }
    dados.historico = [contestacaoBase]
    fetchMock.mockRejectedValue(new Error('Sem conexão'))
    return resposta(contestacaoBase, 201)
  })
  const user = userEvent.setup()
  renderizar()
  await screen.findByText('Nenhuma contestação neste pedido.')
  await user.type(screen.getByLabelText('Descreva o problema'), 'Telhas quebradas.')
  await user.click(screen.getByRole('button', { name: 'Abrir contestação' }))
  expect(await screen.findByText(/Contestação aberta com sucesso/)).toBeInTheDocument()
  expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível conectar ao servidor.')
  expect(screen.getByText('As telhas chegaram quebradas.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeDisabled()
  fetchMock.mockImplementation(async (url) => url.endsWith('/disputes')
    ? resposta({ items: dados.historico, total: 1 }) : resposta(dados.pedido))
  await user.click(screen.getByRole('button', { name: 'Atualizar pedido e histórico' }))
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
})

it('não consulta pedido de outra pessoa informado na URL', async () => {
  const { fetchMock } = prepararApi()
  renderizar('/testes/contestacao?pedido=pedido-de-outra-pessoa')
  expect(await screen.findByRole('alert')).toHaveTextContent('O pedido informado não está entre os seus pedidos.')
  expect(fetchMock).toHaveBeenCalledOnce()
  expect(screen.queryByRole('button', { name: 'Abrir contestação' })).not.toBeInTheDocument()
})

it('ignora respostas antigas quando o usuário seleciona outro pedido', async () => {
  const outroPedido: Pedido = { ...pedidoBase, id: 'pedido-2', status: 'CONCLUIDO' }
  let concluir!: (value: ReturnType<typeof resposta>) => void
  const atrasada = new Promise<ReturnType<typeof resposta>>((resolve) => { concluir = resolve })
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/orders')) return resposta({ items: [pedidoBase, outroPedido], total: 2 })
    if (url.endsWith('/pedido-1')) return atrasada
    if (url.endsWith('/pedido-2')) return resposta(outroPedido)
    return resposta({ items: [], total: 0 })
  }))
  const user = userEvent.setup()
  renderizar()
  await user.selectOptions(await screen.findByLabelText('Pedido'), 'pedido-2')
  await screen.findByText('Este pedido precisa estar entregue para abrir uma contestação.')
  await act(async () => { concluir(resposta(pedidoBase)) })
  expect(screen.getByText('Concluído')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeDisabled()
})

it('impede cliques duplicados durante o envio', async () => {
  const { post } = prepararApi()
  let concluir!: (value: ReturnType<typeof resposta>) => void
  post.mockImplementation(() => new Promise((resolve) => { concluir = resolve }))
  const user = userEvent.setup()
  renderizar()
  await screen.findByText('Nenhuma contestação neste pedido.')
  await user.type(screen.getByLabelText('Descreva o problema'), 'Telhas quebradas.')
  const botao = screen.getByRole('button', { name: 'Abrir contestação' })
  await user.dblClick(botao)
  expect(post).toHaveBeenCalledOnce()
  expect(screen.getByRole('button', { name: 'Abrindo contestação...' })).toBeDisabled()
  await act(async () => { concluir(resposta(contestacaoBase, 201)) })
})

it('oferece nova tentativa quando a listagem falha', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Sem conexão')))
  const user = userEvent.setup()
  renderizar()
  expect(await screen.findByRole('alert')).toBeInTheDocument()
  prepararApi()
  await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))
  expect(await screen.findByText('Nenhuma contestação neste pedido.')).toBeInTheDocument()
})

it('exibe estado vazio sem enviar requisições de contestação', async () => {
  const { dados, fetchMock } = prepararApi()
  dados.pedidos = []
  renderizar()
  expect(await screen.findByText('Você ainda não tem pedidos para testar.')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledOnce()
})

it('exige login para acessar a rota de teste', async () => {
  sessionStorage.clear()
  const { fetchMock } = prepararApi()
  renderizar(undefined, true)
  expect(await screen.findByRole('button', { name: 'Entrar na plataforma' })).toBeInTheDocument()
  expect(fetchMock).not.toHaveBeenCalled()
})

it('preserva o pedido da URL ao redirecionar para o login', async () => {
  sessionStorage.clear()
  const segundo: Pedido = { ...pedidoBase, id: 'pedido-2' }
  const usuario = {
    id: 'comprador-1', nome: 'Comprador', email: 'comprador3@gmail.com', telefone: null,
    status: 'ATIVO', criado_em: '', atualizado_em: '',
  }
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/auth/login')) return resposta({
      access_token: 'token', refresh_token: 'refresh', expires_in: 900,
    })
    if (url.endsWith('/auth/me')) return resposta(usuario)
    if (url.endsWith('/orders')) return resposta({ items: [pedidoBase, segundo], total: 2 })
    if (url.endsWith('/disputes')) return resposta({ items: [], total: 0 })
    return resposta(segundo)
  }))
  const user = userEvent.setup()
  renderizar('/testes/contestacao?pedido=pedido-2', true)
  await user.type(await screen.findByLabelText('E-mail'), 'comprador3@gmail.com')
  await user.type(screen.getByLabelText('Senha'), 'senha-de-teste')
  await user.click(screen.getByRole('button', { name: 'Entrar na plataforma' }))
  expect(await screen.findByText('Nenhuma contestação neste pedido.')).toBeInTheDocument()
  expect(screen.getByLabelText('Pedido')).toHaveValue('pedido-2')
})

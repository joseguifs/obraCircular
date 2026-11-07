import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AppRouter } from '../../app/router'
import { AuthProvider } from '../autenticacao/AuthProvider'
import { salvarSessaoArmazenada } from '../autenticacao/sessaoStorage'
import type { Contestacao, Pedido } from './types'

const pedido: Pedido = {
  id: 'pedido-1', anuncio_id: 'anuncio-1', comprador_id: 'comprador-1', quantidade: 2,
  preco_unitario: '25.00', valor_total: '50.00', modalidade_entrega: 'RETIRADA', status: 'ENTREGUE',
  pagamento: { id: 'pagamento-1', status: 'APROVADO', pagamento_externo_id: 'mp-1', status_detalhe: null },
}

const contestacao: Contestacao = {
  id: 'protocolo-1', pedido_id: pedido.id, comprador_id: pedido.comprador_id,
  motivo: 'QUANTIDADE_INCORRETA', descricao: 'Recebi apenas uma unidade.', status: 'ABERTA',
  resolucao: null, resolvida_em: null, criado_em: '2026-11-01T12:00:00Z', atualizado_em: '2026-11-01T12:00:00Z',
}

function resposta(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function prepararApi(atual = pedido, historico: Contestacao[] = []) {
  const dados = { pedido: atual, historico }
  const post = vi.fn(async () => {
    dados.pedido = { ...dados.pedido, status: 'EM_CONTESTACAO' }
    dados.historico = [contestacao]
    return resposta(contestacao, 201)
  })
  const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/orders')) return resposta({ items: [dados.pedido], total: 1 })
    if (url.endsWith('/disputes')) {
      return init.method === 'POST' ? post() : resposta({ items: dados.historico, total: dados.historico.length })
    }
    return resposta(dados.pedido)
  })
  vi.stubGlobal('fetch', fetchMock)
  return { post, fetchMock, dados }
}

function renderizar(url = '/pedidos/pedido-1/contestacoes') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <AuthProvider><AppRouter /></AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  salvarSessaoArmazenada({
    accessToken: 'token-comprador', refreshToken: 'refresh', expiraEm: Date.now() + 900_000,
    usuario: {
      id: pedido.comprador_id, nome: 'Comprador', email: 'comprador@example.com', telefone: null,
      status: 'ATIVO', criado_em: '', atualizado_em: '',
    },
  })
})

afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals() })

it('permite abrir contestação a partir de Meus pedidos e voltar ao detalhe atualizado', async () => {
  const { post, fetchMock } = prepararApi()
  const user = userEvent.setup()
  renderizar('/pedidos')
  await user.click(await screen.findByRole('link', { name: /Ver pedido/ }))
  await user.click(await screen.findByRole('link', { name: 'Abrir contestação' }))
  expect(await screen.findByRole('heading', { name: 'Contestação do pedido' })).toBeInTheDocument()
  await screen.findByText('Nenhuma contestação neste pedido.')
  expect(screen.queryByText('Ambiente de teste')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Descreva o problema')).toHaveAttribute('maxlength', '5000')
  await user.selectOptions(screen.getByLabelText('Motivo'), 'QUANTIDADE_INCORRETA')
  await user.type(screen.getByLabelText('Descreva o problema'), '  Recebi apenas uma unidade.  ')
  await user.click(screen.getByRole('button', { name: 'Abrir contestação' }))
  expect(await screen.findByText(/Contestação aberta com sucesso/)).toBeInTheDocument()
  expect(screen.getByText('Protocolo: protocolo-1')).toBeInTheDocument()
  expect(screen.getByText('Recebi apenas uma unidade.')).toBeInTheDocument()
  expect(post).toHaveBeenCalledOnce()
  const chamada = fetchMock.mock.calls.find(([, init]) => init.method === 'POST')!
  expect(chamada[0]).toBe('http://localhost:8000/api/v1/orders/pedido-1/disputes')
  expect(JSON.parse(chamada[1].body as string)).toEqual({
    motivo: 'QUANTIDADE_INCORRETA', descricao: 'Recebi apenas uma unidade.',
  })
  expect(new Headers(chamada[1].headers).get('Authorization')).toBe('Bearer token-comprador')
  await waitFor(() => expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeDisabled())
  await user.click(screen.getByRole('link', { name: '← Voltar ao pedido' }))
  expect(await screen.findByRole('heading', { name: 'Pedido em contestação' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Ver contestações' })).toHaveAttribute('href', '/pedidos/pedido-1/contestacoes')
})

it('exige autenticação antes de consultar o pedido', async () => {
  sessionStorage.clear()
  const { fetchMock } = prepararApi()
  renderizar()
  expect(await screen.findByRole('button', { name: 'Entrar na plataforma' })).toBeInTheDocument()
  expect(fetchMock).not.toHaveBeenCalled()
})

it('mantém a rota do pedido depois do login', async () => {
  sessionStorage.clear()
  const { fetchMock } = prepararApi()
  const consultar = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation(async (url, init) => {
    if (url.endsWith('/auth/login')) return resposta({ access_token: 'token', refresh_token: 'refresh', expires_in: 900 })
    if (url.endsWith('/auth/me')) return resposta({
      id: pedido.comprador_id, nome: 'Comprador', email: 'comprador@example.com', telefone: null,
      status: 'ATIVO', criado_em: '', atualizado_em: '',
    })
    return consultar(url, init)
  })
  const user = userEvent.setup()
  renderizar()
  await user.type(await screen.findByLabelText('E-mail'), 'comprador@example.com')
  await user.type(screen.getByLabelText('Senha'), 'senha-de-teste')
  await user.click(screen.getByRole('button', { name: 'Entrar na plataforma' }))
  expect(await screen.findByText('Nenhuma contestação neste pedido.')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Contestação do pedido' })).toBeInTheDocument()
})

it('não exibe dados nem habilita abertura para pedido inexistente ou de outro comprador', async () => {
  const { fetchMock, post } = prepararApi()
  fetchMock.mockResolvedValue(resposta({ detail: 'Pedido não encontrado.', code: 'ORDER_NOT_FOUND' }, 404))
  renderizar('/pedidos/pedido-alheio/contestacoes')
  expect(await screen.findByRole('alert')).toHaveTextContent('Pedido não encontrado.')
  expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeDisabled()
  expect(screen.queryByText('Pedido pedido-1')).not.toBeInTheDocument()
  expect(post).not.toHaveBeenCalled()
})

it('mostra falha de elegibilidade do backend e preserva o texto digitado', async () => {
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
})

it('permite consultar resolução e abrir outra contestação quando a anterior foi recusada', async () => {
  prepararApi(pedido, [{ ...contestacao, status: 'RECUSADA', resolucao: 'Quantidade conferida.' }])
  const user = userEvent.setup()
  renderizar()
  expect(await screen.findByText('Resolução: Quantidade conferida.')).toBeInTheDocument()
  expect(screen.getByText('Recusada')).toBeInTheDocument()
  await user.type(screen.getByLabelText('Descreva o problema'), 'Outro problema com o material.')
  expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeEnabled()
})

it('reconcilia o histórico após erro de conexão sem duplicar uma contestação já criada', async () => {
  const { dados, post } = prepararApi()
  post.mockImplementation(async () => {
    dados.pedido = { ...pedido, status: 'EM_CONTESTACAO' }
    dados.historico = [contestacao]
    throw new Error('Resposta perdida')
  })
  const user = userEvent.setup()
  renderizar()
  await screen.findByText('Nenhuma contestação neste pedido.')
  await user.type(screen.getByLabelText('Descreva o problema'), 'Recebi apenas uma unidade.')
  await user.click(screen.getByRole('button', { name: 'Abrir contestação' }))
  expect(await screen.findByText('Protocolo: protocolo-1')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeDisabled()
  expect(post).toHaveBeenCalledOnce()
})

it('permite tentar novamente após uma falha ao carregar o pedido e histórico', async () => {
  const { fetchMock } = prepararApi()
  const consultar = fetchMock.getMockImplementation()!
  fetchMock.mockRejectedValue(new Error('Sem conexão'))
  const user = userEvent.setup()
  renderizar()
  expect(await screen.findByRole('alert')).toBeInTheDocument()
  fetchMock.mockImplementation(consultar)
  await user.click(screen.getByRole('button', { name: 'Atualizar pedido e histórico' }))
  expect(await screen.findByText('Nenhuma contestação neste pedido.')).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it('impede envio duplicado enquanto a abertura está em andamento', async () => {
  const { post } = prepararApi()
  let concluir!: (value: ReturnType<typeof resposta>) => void
  post.mockImplementation(() => new Promise((resolve) => { concluir = resolve }))
  const user = userEvent.setup()
  renderizar()
  await screen.findByText('Nenhuma contestação neste pedido.')
  await user.type(screen.getByLabelText('Descreva o problema'), 'Material danificado.')
  await user.dblClick(screen.getByRole('button', { name: 'Abrir contestação' }))
  expect(post).toHaveBeenCalledOnce()
  expect(screen.getByRole('button', { name: 'Abrindo contestação...' })).toBeDisabled()
  await act(async () => { concluir(resposta(contestacao, 201)) })
})

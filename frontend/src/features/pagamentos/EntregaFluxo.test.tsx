import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AppRouter } from '../../app/router'
import { AuthProvider } from '../autenticacao/AuthProvider'
import { salvarSessaoArmazenada } from '../autenticacao/sessaoStorage'
import type { Contestacao, Entrega, Pedido } from './types'

const pedidoBase: Pedido = {
  id: 'pedido-1', anuncio_id: 'anuncio-1', comprador_id: 'comprador-1', quantidade: 2,
  preco_unitario: '25.00', valor_total: '50.00', modalidade_entrega: 'RETIRADA', status: 'PAGAMENTO_APROVADO',
  pagamento: { id: 'pagamento-1', status: 'APROVADO', pagamento_externo_id: 'mp-1', status_detalhe: null },
  entrega: null, repasse_status: 'AGUARDANDO_ENTREGA',
}

function sessao(papel = 'comprador') {
  salvarSessaoArmazenada({
    accessToken: `token-${papel}`, refreshToken: 'refresh', expiraEm: Date.now() + 900_000,
    usuario: { id: `${papel}-1`, nome: papel, email: `${papel}@example.com`, telefone: null,
      status: 'ATIVO', criado_em: '', atualizado_em: '' },
  })
}

function resposta(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function prepararApi(pedido: Pedido = pedidoBase) {
  const entrega: Entrega = { id: 'entrega-1', pedido_id: pedido.id, status: 'ENTREGUE',
    confirmado_em: new Date().toISOString(), prazo_contestacao_em: new Date(Date.now() + 7 * 86400_000).toISOString() }
  const dados = { pedido: { ...pedido }, historico: [] as Contestacao[] }
  const gerar = vi.fn(async () => resposta({ pin: '00345', expira_em: new Date(Date.now() + 86400_000).toISOString(), tentativas_restantes: 5 }, 201))
  const confirmar = vi.fn(async () => {
    dados.pedido = { ...dados.pedido, status: 'ENTREGUE', entrega, repasse_status: 'EM_PERIODO_CONTESTACAO' }
    return resposta(entrega)
  })
  const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/delivery/pin')) return gerar()
    if (url.endsWith('/delivery/confirm')) return confirmar()
    if (url.endsWith('/orders/sales')) return resposta({ items: [dados.pedido], total: 1 })
    if (url.endsWith('/disputes')) {
      if (init.method === 'POST') {
        dados.pedido = { ...dados.pedido, status: 'EM_CONTESTACAO', repasse_status: 'BLOQUEADO' }
        dados.historico = [{ id: 'contestacao-1', pedido_id: pedido.id, comprador_id: pedido.comprador_id,
          motivo: 'PRODUTO_DANIFICADO', descricao: 'Material danificado.', status: 'ABERTA',
          resolucao: null, resolvida_em: null, criado_em: new Date().toISOString(), atualizado_em: new Date().toISOString() }]
        return resposta(dados.historico[0], 201)
      }
      return resposta({ items: dados.historico, total: dados.historico.length })
    }
    return resposta(dados.pedido)
  })
  vi.stubGlobal('fetch', fetchMock)
  return { dados, entrega, gerar, confirmar, fetchMock }
}

function renderEm(url = '/pedidos/pedido-1') {
  return render(<MemoryRouter initialEntries={[url]}><AuthProvider><AppRouter /></AuthProvider></MemoryRouter>)
}

beforeEach(() => sessao())
afterEach(() => { cleanup(); vi.useRealTimers(); sessionStorage.clear(); localStorage.clear(); vi.unstubAllGlobals() })

it('completa geração pelo comprador, confirmação pelo vendedor e abertura de contestação', async () => {
  const { fetchMock, dados } = prepararApi()
  const user = userEvent.setup()
  const comprador = renderEm()
  await user.click(await screen.findByRole('button', { name: 'Gerar PIN da entrega' }))
  expect(await screen.findByText('00345')).toBeInTheDocument()
  expect(JSON.stringify(sessionStorage)).not.toContain('00345')
  expect(JSON.stringify(localStorage)).not.toContain('00345')
  comprador.unmount()
  sessao('vendedor')
  const vendedor = renderEm('/vendas')
  await user.click(await screen.findByRole('button', { name: 'Confirmar retirada' }))
  await user.type(screen.getByLabelText('PIN informado pelo comprador'), '00345')
  await user.click(screen.getByRole('button', { name: 'Validar PIN e confirmar entrega' }))
  expect(await screen.findByText(/Entrega do pedido pedido-1 confirmada/)).toBeInTheDocument()
  const chamada = fetchMock.mock.calls.find(([url]) => url.endsWith('/delivery/confirm'))!
  expect(JSON.parse(chamada[1].body as string)).toEqual({ pin: '00345' })
  expect(new Headers(chamada[1].headers).get('Authorization')).toBe('Bearer token-vendedor')
  expect(screen.queryByRole('button', { name: 'Confirmar retirada' })).not.toBeInTheDocument()
  vendedor.unmount()
  sessao()
  renderEm()
  expect(await screen.findByRole('heading', { name: 'Entregue' })).toBeInTheDocument()
  expect(screen.queryByText('00345')).not.toBeInTheDocument()
  await user.click(screen.getByRole('link', { name: 'Abrir contestação' }))
  await screen.findByText('Nenhuma contestação neste pedido.')
  await user.type(screen.getByLabelText('Descreva o problema'), 'Material danificado.')
  await user.click(screen.getByRole('button', { name: 'Abrir contestação' }))
  expect(await screen.findByText(/Contestação aberta com sucesso/)).toBeInTheDocument()
  expect(dados.pedido.status).toBe('EM_CONTESTACAO')
  expect(dados.pedido.repasse_status).toBe('BLOQUEADO')
})

it('atualiza automaticamente a compra quando o vendedor confirma em outra sessão', async () => {
  vi.useFakeTimers()
  const { dados, entrega } = prepararApi()
  await act(async () => { renderEm() })
  expect(screen.getByRole('button', { name: 'Gerar PIN da entrega' })).toBeInTheDocument()
  dados.pedido = { ...dados.pedido, status: 'ENTREGUE', entrega, repasse_status: 'EM_PERIODO_CONTESTACAO' }
  await act(async () => { await vi.advanceTimersByTimeAsync(10_000) })
  expect(screen.getByRole('link', { name: 'Abrir contestação' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Gerar PIN da entrega' })).not.toBeInTheDocument()
})

it('oculta PIN expirado e descarta o anterior quando a regeneração falha', async () => {
  vi.useFakeTimers()
  const { gerar } = prepararApi()
  gerar.mockResolvedValueOnce(resposta({ pin: '00345', expira_em: new Date(Date.now() + 1000).toISOString(), tentativas_restantes: 5 }, 201))
  await act(async () => { renderEm() })
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Gerar PIN da entrega' })) })
  expect(screen.getByText('00345')).toBeInTheDocument()
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(screen.queryByText('00345')).not.toBeInTheDocument()
  expect(screen.getByText('O PIN expirou. Gere um novo código.')).toBeInTheDocument()
  gerar.mockResolvedValueOnce(resposta({ detail: 'Não foi possível gerar outro PIN.' }, 409))
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Gerar novo PIN' })) })
  expect(screen.queryByText('00345')).not.toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveTextContent('Não foi possível gerar outro PIN.')
})

it.each([
  [400, 'PIN incorreto. Tentativas restantes: 4.'],
  [409, 'O PIN expirou. Peça ao comprador para gerar um novo.'],
  [409, 'O PIN está bloqueado. Peça ao comprador para gerar um novo.'],
])('apresenta a recusa do backend (%s) sem marcar o pedido como entregue', async (status, detail) => {
  const { confirmar, dados } = prepararApi()
  confirmar.mockResolvedValueOnce(resposta({ detail }, status))
  sessao('vendedor')
  const user = userEvent.setup()
  renderEm('/vendas')
  await user.click(await screen.findByRole('button', { name: 'Confirmar retirada' }))
  const entrada = screen.getByLabelText('PIN informado pelo comprador')
  await user.type(entrada, '12x34')
  expect(entrada).toHaveValue('1234')
  expect(screen.getByRole('button', { name: 'Validar PIN e confirmar entrega' })).toBeDisabled()
  await user.type(entrada, '5')
  await user.click(screen.getByRole('button', { name: 'Validar PIN e confirmar entrega' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(detail)
  expect(dados.pedido.status).toBe('PAGAMENTO_APROVADO')
})

it('reconcilia uma confirmação cuja resposta se perdeu e impede reenvio', async () => {
  const { confirmar, dados, entrega } = prepararApi()
  confirmar.mockImplementationOnce(async () => {
    dados.pedido = { ...dados.pedido, status: 'ENTREGUE', entrega }
    throw new TypeError('Resposta perdida')
  })
  sessao('vendedor')
  const user = userEvent.setup()
  renderEm('/vendas')
  await user.click(await screen.findByRole('button', { name: 'Confirmar retirada' }))
  await user.type(screen.getByLabelText('PIN informado pelo comprador'), '00345')
  await user.click(screen.getByRole('button', { name: 'Validar PIN e confirmar entrega' }))
  expect(await screen.findByText('Entregue')).toBeInTheDocument()
  expect(screen.queryByLabelText('PIN informado pelo comprador')).not.toBeInTheDocument()
  expect(confirmar).toHaveBeenCalledOnce()
})

it('impede confirmações duplicadas durante o envio', async () => {
  const { confirmar, entrega } = prepararApi()
  let concluir!: (value: ReturnType<typeof resposta>) => void
  confirmar.mockImplementationOnce(() => new Promise((resolve) => { concluir = resolve }))
  sessao('vendedor')
  const user = userEvent.setup()
  renderEm('/vendas')
  await user.click(await screen.findByRole('button', { name: 'Confirmar retirada' }))
  await user.type(screen.getByLabelText('PIN informado pelo comprador'), '00345')
  const form = screen.getByRole('button', { name: 'Validar PIN e confirmar entrega' }).closest('form')!
  fireEvent.submit(form)
  fireEvent.submit(form)
  expect(confirmar).toHaveBeenCalledOnce()
  await act(async () => { concluir(resposta(entrega)) })
})

it('desabilita a abertura quando o prazo termina com a tela de contestação aberta', async () => {
  vi.useFakeTimers()
  const { dados, entrega } = prepararApi()
  dados.pedido = { ...dados.pedido, status: 'ENTREGUE', repasse_status: 'EM_PERIODO_CONTESTACAO',
    entrega: { ...entrega, prazo_contestacao_em: new Date(Date.now() + 500).toISOString() } }
  await act(async () => { renderEm('/pedidos/pedido-1/contestacoes') })
  fireEvent.change(screen.getByLabelText('Descreva o problema'), { target: { value: 'Material danificado.' } })
  expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeEnabled()
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeDisabled()
  expect(screen.getByText('O prazo para abrir uma contestação terminou.')).toBeInTheDocument()
})

it.each(['PROCESSANDO', 'PAGO', 'CANCELADO', 'REEMBOLSADO'] as const)(
  'bloqueia a abertura com repasse %s', async (repasse_status) => {
    const { dados, entrega } = prepararApi()
    dados.pedido = { ...dados.pedido, status: 'ENTREGUE', entrega, repasse_status }
    renderEm('/pedidos/pedido-1/contestacoes')
    expect(await screen.findByText('A situação do repasse não permite abrir uma contestação.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Abrir contestação' })).toBeDisabled()
  },
)

it('exige login para consultar vendas', async () => {
  sessionStorage.clear()
  const { fetchMock } = prepararApi()
  renderEm('/vendas')
  expect(await screen.findByRole('button', { name: 'Entrar na plataforma' })).toBeInTheDocument()
  expect(fetchMock).not.toHaveBeenCalled()
})

it('permite recuperar a listagem de vendas após uma falha de consulta', async () => {
  const { fetchMock } = prepararApi()
  fetchMock.mockRejectedValueOnce(new TypeError('Sem conexão'))
  sessao('vendedor')
  const user = userEvent.setup()
  renderEm('/vendas')
  expect(await screen.findByRole('alert')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Atualizar vendas' }))
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  expect(screen.getByRole('button', { name: 'Confirmar retirada' })).toBeEnabled()
})

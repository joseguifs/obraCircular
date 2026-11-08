import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, it, vi } from 'vitest'
import { AppRouter } from '../../app/router'
import { AuthProvider } from '../autenticacao/AuthProvider'
import { salvarSessaoArmazenada } from '../autenticacao/sessaoStorage'

const repasse = {
  id: 'repasse-1', pedido_id: 'pedido-1', vendedor_id: 'vendedor-1', vendedor_nome: 'Carlos Vendedor',
  modelo_financeiro: 'REPASSE_POSTERIOR', valor_bruto: '100.00', percentual_marketplace: '20.00',
  taxa_marketplace: '20.00', taxa_provedor: '5.00', valor_liquido: '80.00',
  taxas_por_conta_marketplace: true, status: 'PRONTO_PARA_LIBERACAO',
  liberacao_prevista_em: '2026-10-25T12:00:00Z', pago_em: null,
  destino_cadastrado: true, pode_liberar: true, pode_consultar: false, motivo_bloqueio: null as string | null,
}

function resposta(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function renderizar(admin = true) {
  salvarSessaoArmazenada({ accessToken: 'token', refreshToken: 'refresh', expiraEm: Date.now() + 900_000,
    usuario: { id: 'admin-1', nome: 'Admin', email: 'admin@test.invalid', telefone: null,
      status: 'ATIVO', administrador: admin, criado_em: '', atualizado_em: '' } })
  return render(<MemoryRouter initialEntries={['/admin/repasses']}>
    <AuthProvider><AppRouter /></AuthProvider>
  </MemoryRouter>)
}

afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals() })

it('exige confirmação e envia somente o identificador do repasse', async () => {
  let atual = { ...repasse }
  const fetchMock = vi.fn(async (_url: string, init: RequestInit) => {
    if (init.method === 'POST') {
      atual = { ...atual, status: 'PROCESSANDO', pode_liberar: false, pode_consultar: true }
      return resposta(atual)
    }
    return resposta({ items: [atual], total: 1, offset: 0, limit: 10 })
  })
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderizar()
  await user.click(await screen.findByRole('button', { name: 'Liberar repasse' }))
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('group', { name: 'Confirmar liberação' })).toHaveTextContent('80,00')
  await user.click(screen.getByRole('button', { name: 'Confirmar transferência' }))
  expect(await screen.findByText(/Solicitação enviada/)).toBeInTheDocument()
  const chamada = fetchMock.mock.calls.find(([, init]) => init.method === 'POST')!
  expect(chamada[0]).toBe('http://localhost:8000/api/v1/admin/payouts/repasse-1/release')
  expect(chamada[1].body).toBeUndefined()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Liberar repasse' })).toBeDisabled())
  expect(screen.getByRole('button', { name: 'Consultar transferência' })).toBeInTheDocument()
})

it('não permite liberar venda antiga com split', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(resposta({ items: [{ ...repasse,
    modelo_financeiro: 'SPLIT_LEGADO', status: 'PAGO', pode_liberar: false,
    motivo_bloqueio: 'Venda com split legado; não executar outra transferência.',
  }], total: 1 })))
  renderizar()
  expect(await screen.findByRole('button', { name: 'Liberar repasse' })).toBeDisabled()
  expect(screen.getByText(/Venda anterior com split automático/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /destino Pix/ })).not.toBeInTheDocument()
})

it('mostra bloqueio de prazo e comissão congelada da venda', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(resposta({ items: [{ ...repasse,
    percentual_marketplace: '25.00', pode_liberar: false,
    motivo_bloqueio: 'O período de contestação ainda não terminou.',
  }], total: 1 })))
  renderizar()
  expect(await screen.findByText('O período de contestação ainda não terminou.')).toBeInTheDocument()
  expect(screen.getByText('Comissão da venda (25%)')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Liberar repasse' })).toBeDisabled()
})

it('exige conferência de titularidade antes de cadastrar destino', async () => {
  const fetchMock = vi.fn(async (_url: string, init: RequestInit) => init.method === 'PUT'
    ? resposta({ ativo: true }) : resposta({ items: [{ ...repasse, destino_cadastrado: false }], total: 1 }))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderizar()
  await user.click(await screen.findByRole('button', { name: 'Cadastrar destino' }))
  await user.selectOptions(screen.getByLabelText('Tipo de destino'), 'EMAIL')
  await user.type(screen.getByLabelText('Chave Pix'), 'vendedor@test.invalid')
  expect(screen.getByRole('button', { name: 'Salvar destino conferido' })).toBeDisabled()
  await user.click(screen.getByLabelText('Conferi a titularidade do vendedor'))
  await user.click(screen.getByRole('button', { name: 'Salvar destino conferido' }))
  expect(await screen.findByText(/Destino conferido e cadastrado/)).toBeInTheDocument()
  const chamada = fetchMock.mock.calls.find(([, init]) => init.method === 'PUT')!
  expect(JSON.parse(chamada[1].body as string)).toEqual({ tipo_chave: 'EMAIL',
    chave: 'vendedor@test.invalid', titularidade_conferida: true })
})

it('reconsulta após erro e não exibe confirmação de pagamento', async () => {
  const fetchMock = vi.fn(async (_url: string, init: RequestInit) => init.method === 'POST'
    ? resposta({ detail: 'Repasse sem confirmação.' }, 409)
    : resposta({ items: [repasse], total: 1 }))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderizar()
  await user.click(await screen.findByRole('button', { name: 'Liberar repasse' }))
  await user.click(screen.getByRole('button', { name: 'Confirmar transferência' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Repasse sem confirmação.')
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(screen.queryByText(/Solicitação enviada/)).not.toBeInTheDocument()
})

it('não oferece conta Mercado Pago de teste no cadastro de destino, inclusive em desenvolvimento', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(resposta({
    items: [{ ...repasse, destino_cadastrado: false }], total: 1,
  })))
  const user = userEvent.setup()
  renderizar()
  await user.click(await screen.findByRole('button', { name: 'Cadastrar destino' }))
  expect(screen.queryByRole('option', { name: 'Conta Mercado Pago de teste por e-mail' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('Chave Pix')).toBeInTheDocument()
  expect(screen.queryByLabelText('E-mail da conta de teste')).not.toBeInTheDocument()
})

it('restringe a página a administradores', async () => {
  const fetchMock = vi.fn().mockResolvedValue(resposta({ administrador: false }))
  vi.stubGlobal('fetch', fetchMock)
  renderizar(false)
  expect(await screen.findByText(/Acesso restrito/)).toBeInTheDocument()
  expect(fetchMock.mock.calls.every(([url]) => !String(url).includes('/admin/payouts'))).toBe(true)
})

it('oferece retomada da mesma instrução e oculta consulta quando não há identificador', async () => {
  const pendente = { ...repasse, status: 'PROCESSANDO', pode_consultar: false }
  const fetchMock = vi.fn(async (_url: string, init: RequestInit) => init.method === 'POST'
    ? resposta({ detail: 'O Mercado Pago retornou erro durante o envio do repasse (HTTP 403, PA_UNAUTHORIZED_RESULT_FROM_POLICIES).' }, 409)
    : resposta({ items: [pendente], total: 1 }))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderizar()
  await user.click(await screen.findByRole('button', { name: 'Retomar envio' }))
  expect(screen.queryByRole('button', { name: 'Consultar transferência' })).not.toBeInTheDocument()
  expect(screen.getByText(/O envio ainda não tem identificador/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Confirmar transferência' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 403, PA_UNAUTHORIZED_RESULT_FROM_POLICIES')
  const chamada = fetchMock.mock.calls.find(([, init]) => init.method === 'POST')!
  expect(chamada[0]).toBe('http://localhost:8000/api/v1/admin/payouts/repasse-1/release')
  expect(chamada[1].body).toBeUndefined()
})

it('aguarda o bloqueio temporário antes de habilitar retomada', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(resposta({ items: [{ ...repasse,
    status: 'PROCESSANDO', pode_liberar: false, pode_consultar: false,
    motivo_bloqueio: 'Envio sem identificação confirmada. Aguarde dois minutos.',
  }], total: 1 })))
  renderizar()
  expect(await screen.findByRole('button', { name: 'Retomar envio' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: 'Consultar transferência' })).not.toBeInTheDocument()
})

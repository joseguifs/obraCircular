import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, it, vi } from 'vitest'
import { PagamentoRetornoPage } from './PagamentoRetornoPage'
import type { Pedido } from './types'

const pedidoBase: Pedido = {
  id: 'pedido-1',
  anuncio_id: 'anuncio-1',
  comprador_id: 'comprador-1',
  quantidade: 2,
  preco_unitario: '25.00',
  valor_total: '50.00',
  modalidade_entrega: 'RETIRADA',
  status: 'AGUARDANDO_PAGAMENTO',
  pagamento: {
    id: 'pagamento-1',
    status: 'PENDENTE',
    pagamento_externo_id: null,
    status_detalhe: null,
  },
}

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

function renderizarPagina() {
  return render(
    <MemoryRouter initialEntries={['/pagamento/retorno?external_reference=pedido-1']}>
      <PagamentoRetornoPage />
    </MemoryRouter>,
  )
}

function respostaJson(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

it('cancela um checkout que ainda aguarda pagamento', async () => {
  const pedidoCancelado: Pedido = {
    ...pedidoBase,
    status: 'CANCELADO',
    pagamento: { ...pedidoBase.pagamento!, status: 'CANCELADO' },
  }
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(respostaJson(pedidoBase))
    .mockResolvedValueOnce(respostaJson(null, 204))
    .mockResolvedValueOnce(respostaJson(pedidoCancelado))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()

  renderizarPagina()
  await user.click(await screen.findByRole('button', { name: 'Cancelar checkout' }))

  expect(await screen.findByText('Checkout cancelado. A quantidade reservada foi liberada.'))
    .toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Checkout cancelado' })).toBeInTheDocument()
  expect(screen.getByText('Cancelado')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    'http://localhost:8000/api/v1/orders/pedido-1/cancel',
    expect.objectContaining({ method: 'POST' }),
  )
})

it('solicita reembolso de um pedido com pagamento aprovado', async () => {
  const pedidoAprovado: Pedido = {
    ...pedidoBase,
    status: 'PAGAMENTO_APROVADO',
    pagamento: {
      ...pedidoBase.pagamento!,
      status: 'APROVADO',
      pagamento_externo_id: 'mp-123',
    },
  }
  const pedidoReembolsado: Pedido = {
    ...pedidoAprovado,
    status: 'REEMBOLSADO',
    pagamento: { ...pedidoAprovado.pagamento!, status: 'REEMBOLSADO' },
  }
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(respostaJson(pedidoAprovado))
    .mockResolvedValueOnce(
      respostaJson({
        id: 'reembolso-1',
        pedido_id: 'pedido-1',
        status: 'CONCLUIDO',
        valor: '50.00',
        reembolso_externo_id: 'refund-123',
      }),
    )
    .mockResolvedValueOnce(respostaJson(pedidoReembolsado))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()

  renderizarPagina()
  await user.click(await screen.findByRole('button', { name: 'Solicitar reembolso' }))

  expect(await screen.findByText('Reembolso concluído com sucesso.')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Reembolso concluído' })).toBeInTheDocument()
  expect(screen.getByText('Reembolsado')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    'http://localhost:8000/api/v1/orders/pedido-1/refund',
    expect.objectContaining({ method: 'POST' }),
  )
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Solicitar reembolso' })).toBeNull())
})

const pedidoAprovado: Pedido = {
  ...pedidoBase,
  status: 'PAGAMENTO_APROVADO',
  pagamento: { ...pedidoBase.pagamento!, status: 'APROVADO', pagamento_externo_id: 'mp-123' },
}

const reembolso = {
  id: 'reembolso-1', pedido_id: 'pedido-1', valor: '50.00', reembolso_externo_id: 'refund-123',
}

it('acompanha reembolso assíncrono e impede nova solicitação enquanto processa', async () => {
  vi.useFakeTimers()
  const emProcessamento: Pedido = {
    ...pedidoAprovado, status: 'CANCELADO',
    reembolso: { ...reembolso, status: 'PROCESSANDO' },
  }
  const concluido: Pedido = {
    ...emProcessamento, status: 'REEMBOLSADO',
    pagamento: { ...pedidoAprovado.pagamento!, status: 'REEMBOLSADO' },
    reembolso: { ...reembolso, status: 'CONCLUIDO' },
  }
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(respostaJson(pedidoAprovado))
    .mockResolvedValueOnce(respostaJson(emProcessamento.reembolso))
    .mockResolvedValueOnce(respostaJson(emProcessamento))
    .mockResolvedValueOnce(respostaJson(concluido))
  vi.stubGlobal('fetch', fetchMock)
  await act(async () => { renderizarPagina() })
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Solicitar reembolso' })) })
  expect(screen.getByRole('heading', { name: 'Reembolso em andamento' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Solicitar reembolso' })).toBeNull()
  await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
  expect(screen.getByRole('heading', { name: 'Reembolso concluído' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(4)
})

it('reconcilia o pedido após falha de reembolso e exibe a falha real', async () => {
  const falhou: Pedido = {
    ...pedidoAprovado, status: 'CANCELADO', reembolso: { ...reembolso, status: 'FALHOU' },
  }
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(respostaJson(pedidoAprovado))
    .mockResolvedValueOnce(respostaJson({ detail: 'Saldo insuficiente do vendedor.' }, 409))
    .mockResolvedValueOnce(respostaJson(falhou))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderizarPagina()
  await user.click(await screen.findByRole('button', { name: 'Solicitar reembolso' }))
  expect(await screen.findByRole('heading', { name: 'Reembolso não concluído' })).toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveTextContent('Saldo insuficiente do vendedor.')
  expect(screen.getByRole('button', { name: 'Solicitar reembolso' })).toBeEnabled()
  expect(fetchMock).toHaveBeenCalledTimes(3)
})

it('descarta polling anterior à ação mesmo quando responde depois do cancelamento', async () => {
  vi.useFakeTimers()
  let responderPolling!: (resposta: ReturnType<typeof respostaJson>) => void
  const pollingAtrasado = new Promise<ReturnType<typeof respostaJson>>((resolve) => {
    responderPolling = resolve
  })
  const cancelado: Pedido = { ...pedidoBase, status: 'CANCELADO' }
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(respostaJson(pedidoBase))
    .mockReturnValueOnce(pollingAtrasado)
    .mockResolvedValueOnce(respostaJson(null, 204))
    .mockResolvedValueOnce(respostaJson(cancelado))
  vi.stubGlobal('fetch', fetchMock)
  await act(async () => { renderizarPagina() })
  await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Cancelar checkout' })) })
  expect(screen.getByRole('heading', { name: 'Checkout cancelado' })).toBeInTheDocument()
  await act(async () => { responderPolling(respostaJson(pedidoBase)) })
  expect(screen.getByRole('heading', { name: 'Checkout cancelado' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Cancelar checkout' })).toBeNull()
  await act(async () => { await vi.advanceTimersByTimeAsync(4000) })
  expect(fetchMock).toHaveBeenCalledTimes(4)
})

it('oferece reembolso quando o cancelamento conflita com uma aprovação recém-confirmada', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(respostaJson(pedidoBase))
    .mockResolvedValueOnce(respostaJson({ detail: 'Este pedido exige reembolso.' }, 409))
    .mockResolvedValueOnce(respostaJson(pedidoAprovado))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderizarPagina()
  await user.click(await screen.findByRole('button', { name: 'Cancelar checkout' }))
  expect(await screen.findByRole('heading', { name: 'Pagamento confirmado' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Cancelar checkout' })).toBeNull()
  expect(screen.getByRole('button', { name: 'Solicitar reembolso' })).toBeEnabled()
  expect(screen.getByRole('alert')).toHaveTextContent('Este pedido exige reembolso.')
})

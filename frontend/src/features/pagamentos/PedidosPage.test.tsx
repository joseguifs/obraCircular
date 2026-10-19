import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, expect, it, vi } from 'vitest'
import { PagamentoRetornoPage } from './PagamentoRetornoPage'
import { PedidosPage } from './PedidosPage'

afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals() })

it('permite recuperar pedido anterior sem depender do último checkout armazenado', async () => {
  sessionStorage.setItem('obraCircular:lastOrderId', 'checkout-mais-novo')
  const pedido = {
    id: 'pedido-antigo', status: 'CANCELADO', quantidade: 2, valor_total: '50.00',
    pagamento: { status: 'CANCELADO' }, reembolso: null,
  }
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ items: [pedido], total: 1 }) })
    .mockResolvedValueOnce({ ok: true, status: 200, json: async () => pedido })
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={['/pedidos']}>
      <Routes>
        <Route path="/pedidos" element={<PedidosPage />} />
        <Route path="/pedidos/:pedidoId" element={<PagamentoRetornoPage />} />
      </Routes>
    </MemoryRouter>,
  )
  await user.click(await screen.findByRole('link', { name: /Pedido pedido-a/ }))
  expect(await screen.findByRole('heading', { name: 'Checkout cancelado' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenNthCalledWith(2,
    'http://localhost:8000/api/v1/orders/pedido-antigo', expect.any(Object))
})

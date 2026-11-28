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

it('mostra o anúncio de cada pedido na lista', async () => {
  const pedidos = [
    {
      id: 'a1b2c3d4-0000-0000-0000-000000000000', status: 'PAGAMENTO_APROVADO', quantidade: 2,
      valor_total: '179.80', pagamento: null, reembolso: null,
      anuncio: {
        id: 'anuncio-1', titulo: 'Porcelanato 60x60 acetinado', status: 'ESGOTADO',
        imagem_capa_url: '/uploads/anuncios/anuncio-1/capa.webp',
      },
    },
    {
      id: 'e5f6a7b8-0000-0000-0000-000000000000', status: 'CANCELADO', quantidade: 1,
      valor_total: '10.00', pagamento: null, reembolso: null, anuncio: null,
    },
  ]
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => ({ items: pedidos, total: 2 }),
  }))
  const { container } = render(
    <MemoryRouter initialEntries={['/pedidos']}>
      <PedidosPage />
    </MemoryRouter>,
  )

  const link = await screen.findByRole('link', { name: /Pedido a1b2c3d4: Porcelanato 60x60 acetinado/ })
  expect(link).toHaveAttribute('href', '/pedidos/a1b2c3d4-0000-0000-0000-000000000000')
  expect(screen.getByText('Pedido a1b2c3d4 · 2 unidades')).toBeInTheDocument()
  expect(container.querySelector('.payment-order-foto img')).toHaveAttribute(
    'src', expect.stringContaining('/uploads/anuncios/anuncio-1/capa.webp'),
  )
  expect(screen.getByText('Anúncio indisponível')).toBeInTheDocument()
})

import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { mensagemApiErro } from '../../lib/api'
import { formatarMoeda } from '../../lib/formatarTempo'
import { listarPedidos } from './pagamentoApi'
import { STATUS_PEDIDO } from './pedidoApresentacao'
import type { Pedido } from './types'

export function PedidosPage() {
  const [pedidos, setPedidos] = useState<Pedido[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [revisao, setRevisao] = useState(0)

  useEffect(() => {
    let ativo = true
    listarPedidos()
      .then((resposta) => {
        if (ativo) setPedidos(resposta.items)
      })
      .catch((falha) => {
        if (ativo) setErro(mensagemApiErro(falha, 'Não foi possível carregar seus pedidos.'))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => { ativo = false }
  }, [revisao])

  return (
    <main className="payment-page">
      <section className="payment-card">
        <span className="step-label">Minhas compras</span>
        <h1>Meus pedidos</h1>
        <p>Acompanhe seus pagamentos, cancele checkouts e consulte seus reembolsos.</p>
        {carregando && <p role="status">Carregando pedidos...</p>}
        {erro && <p className="form-alert" role="alert">{erro}</p>}
        {!carregando && !erro && pedidos.length === 0 && <p>Você ainda não tem pedidos.</p>}
        {!carregando && !erro && (
          <ul className="payment-order-list">
            {pedidos.map((pedido) => (
              <li key={pedido.id}>
                <Link to={`/pedidos/${pedido.id}`}>
                  <strong>Pedido {pedido.id.slice(0, 8)}</strong>
                  <span>{STATUS_PEDIDO[pedido.status]}</span>
                  <span>{pedido.quantidade} unidade(s) · {formatarMoeda(pedido.valor_total)}</span>
                  <span>Ver pedido →</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        {erro && (
          <button type="button" className="secondary-button" onClick={() => {
            setErro(''); setCarregando(true); setRevisao((atual) => atual + 1)
          }}>Tentar novamente</button>
        )}
        <Link className="secondary-button" to="/home">Voltar aos anúncios</Link>
      </section>
    </main>
  )
}

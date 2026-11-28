import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { mensagemApiErro, resolverUrlDaApi } from '../../lib/api'
import { formatarMoeda } from '../../lib/formatarTempo'
import { listarPedidos } from './pagamentoApi'
import { STATUS_PEDIDO, tomDoStatus } from './pedidoApresentacao'
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
    <main className="payment-page payment-page--larga">
      <section className="payment-card">
        <h1>Meus pedidos</h1>
        <p>Abra um pedido para acompanhar pagamento, entrega, reembolso ou contestação.</p>
        {carregando && <p role="status">Carregando pedidos...</p>}
        {erro && <p className="form-alert" role="alert">{erro}</p>}
        {!carregando && !erro && pedidos.length === 0 && <p>Você ainda não tem pedidos.</p>}
        {!carregando && !erro && (
          <ul className="payment-order-list">
            {pedidos.map((pedido) => {
              const codigo = pedido.id.slice(0, 8)
              const titulo = pedido.anuncio?.titulo ?? 'Anúncio indisponível'
              const capa = pedido.anuncio?.imagem_capa_url
              return (
              <li key={pedido.id}>
                <Link
                  to={`/pedidos/${pedido.id}`}
                  aria-label={`Pedido ${codigo}: ${titulo}, ${STATUS_PEDIDO[pedido.status]}, ${formatarMoeda(pedido.valor_total)}. Ver pedido`}
                >
                  <span className="payment-order-foto" aria-hidden="true">
                    {capa && <img src={resolverUrlDaApi(capa)} alt="" />}
                  </span>
                  <span className="payment-order-id">
                    <strong>{titulo}</strong>
                    <span>
                      Pedido {codigo} · {pedido.quantidade}{' '}
                      {pedido.quantidade === 1 ? 'unidade' : 'unidades'}
                    </span>
                  </span>
                  <span className={`status-chip status-chip--${tomDoStatus(pedido.status)}`}>
                    {STATUS_PEDIDO[pedido.status]}
                  </span>
                  <strong className="payment-order-valor">{formatarMoeda(pedido.valor_total)}</strong>
                </Link>
              </li>
              )
            })}
          </ul>
        )}
        {erro && (
          <button type="button" className="secondary-button" onClick={() => {
            setErro(''); setCarregando(true); setRevisao((atual) => atual + 1)
          }}>Tentar novamente</button>
        )}
        <Link className="secondary-button" to="/home">Voltar aos anúncios</Link>
        {import.meta.env.DEV && (
          <div className="payment-navigation">
            <Link className="secondary-button" to="/testes/contestacao">Testar contestação</Link>
          </div>
        )}
      </section>
    </main>
  )
}

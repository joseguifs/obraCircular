import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { mensagemApiErro } from '../../lib/api'
import { formatarMoeda } from '../../lib/formatarTempo'
import { useAuth } from '../autenticacao/useAuth'
import { ContestacaoPedido } from './ContestacaoPage'
import { listarPedidos } from './pagamentoApi'
import { STATUS_PEDIDO } from './pedidoApresentacao'
import type { Pedido } from './types'

export function ContestacaoTestePage() {
  const { sessao } = useAuth()
  const [parametros, setParametros] = useSearchParams()
  const [pedidos, setPedidos] = useState<Pedido[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [revisao, setRevisao] = useState(0)
  const pedidoId = parametros.get('pedido')
    ?? pedidos.find((pedido) => pedido.status === 'ENTREGUE')?.id
    ?? pedidos[0]?.id
    ?? ''
  const pertenceAoComprador = pedidos.some((pedido) => pedido.id === pedidoId)

  useEffect(() => {
    let ativo = true
    listarPedidos()
      .then((resposta) => { if (ativo) setPedidos(resposta.items) })
      .catch((falha) => {
        if (ativo) setErro(mensagemApiErro(falha, 'Não foi possível carregar seus pedidos.'))
      })
      .finally(() => { if (ativo) setCarregando(false) })
    return () => { ativo = false }
  }, [revisao])

  return (
    <main className="payment-page dispute-page">
      <Link className="back-button" to="/pedidos">← Meus pedidos</Link>
      <section className="payment-card">
        <span className="step-label">Ambiente de teste</span>
        <h1>Testar contestação</h1>
        <p>Selecione um pedido entregue, descreva o problema e acompanhe a contestação.</p>
        <p className="dispute-session">Conectado como <strong>{sessao?.usuario.email}</strong></p>
        <p className="dispute-note">
          Esta página abre uma contestação de verdade no backend conectado. No fluxo de repasse
          posterior, uma contestação ativa impede a liberação ao vendedor.
        </p>
        {carregando && <p role="status">Carregando seus pedidos...</p>}
        {erro && <p className="form-alert" role="alert">{erro}</p>}
        {erro && (
          <button className="secondary-button" type="button" onClick={() => {
            setErro(''); setCarregando(true); setRevisao((atual) => atual + 1)
          }}>Tentar novamente</button>
        )}
        {!carregando && !erro && pedidos.length === 0 && <p>Você ainda não tem pedidos para testar.</p>}
        {!carregando && !erro && pedidos.length > 0 && (
          <>
            <label className="dispute-field" htmlFor="pedido-teste">Pedido</label>
            <select id="pedido-teste" className="dispute-select"
              value={pertenceAoComprador ? pedidoId : ''}
              onChange={(evento) => setParametros({ pedido: evento.target.value })}>
              <option value="" disabled>Selecione um dos seus pedidos</option>
              {pedidos.map((pedido) => (
                <option key={pedido.id} value={pedido.id}>
                  {pedido.id.slice(0, 8)} · {STATUS_PEDIDO[pedido.status]} · {formatarMoeda(pedido.valor_total)}
                </option>
              ))}
            </select>
            {pertenceAoComprador
              ? <ContestacaoPedido key={pedidoId} pedidoId={pedidoId} />
              : <p role="alert">O pedido informado não está entre os seus pedidos. Selecione outro ou entre com o comprador correto.</p>}
          </>
        )}
      </section>
    </main>
  )
}

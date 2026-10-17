import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { mensagemApiErro } from '../../lib/api'
import { consultarPedido } from './pagamentoApi'
import type { Pedido } from './types'

export function PagamentoRetornoPage() {
  const [parametros] = useSearchParams()
  const pedidoId =
    parametros.get('external_reference') ??
    sessionStorage.getItem('obraCircular:lastOrderId')
  const [pedido, setPedido] = useState<Pedido | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    if (!pedidoId) {
      setErro('Não foi possível identificar o pedido retornado pelo Mercado Pago.')
      return
    }
    let ativo = true
    let tentativas = 0
    async function atualizar() {
      try {
        const recebido = await consultarPedido(pedidoId!)
        if (!ativo) return
        setPedido(recebido)
        tentativas += 1
        if (
          recebido.status === 'AGUARDANDO_PAGAMENTO' &&
          tentativas < 10
        ) {
          window.setTimeout(atualizar, 2000)
        }
      } catch (falha) {
        if (ativo) setErro(mensagemApiErro(falha, 'Não foi possível consultar o pedido.'))
      }
    }
    void atualizar()
    return () => {
      ativo = false
    }
  }, [pedidoId])

  const confirmado = pedido?.status === 'PAGAMENTO_APROVADO'
  return (
    <main className="payment-page">
      <section className="payment-card">
        <span className="step-label">Pagamento</span>
        <h1>{confirmado ? 'Pagamento confirmado' : 'Estamos confirmando seu pagamento'}</h1>
        <p>
          {confirmado
            ? 'O vendedor já pode preparar seu pedido.'
            : 'A página de retorno não confirma a cobrança. Aguarde a validação segura do Mercado Pago.'}
        </p>
        {erro && <p className="form-alert" role="alert">{erro}</p>}
        {pedido && <p className="payment-status">Pedido: <strong>{pedido.status}</strong></p>}
        <Link className="secondary-button" to="/home">Voltar aos anúncios</Link>
      </section>
    </main>
  )
}

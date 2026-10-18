import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { mensagemApiErro } from '../../lib/api'
import { cancelarCheckout, consultarPedido, solicitarReembolso } from './pagamentoApi'
import { deveAtualizarPedido, reembolsoPendente, STATUS_PEDIDO } from './pedidoApresentacao'
import type { Pedido } from './types'

type AcaoPedido = 'cancelar' | 'reembolsar'

function conteudoDoPedido(pedido: Pedido | null) {
  if (!pedido) return { titulo: 'Consultar pedido', descricao: 'Carregando os dados do pedido.' }
  if (pedido.status === 'REEMBOLSADO') {
    return {
      titulo: 'Reembolso concluído',
      descricao: 'O Mercado Pago confirmou a devolução do valor deste pedido.',
    }
  }
  if (pedido.reembolso?.status === 'FALHOU' || pedido.reembolso?.status === 'RECUSADO') {
    return {
      titulo: 'Reembolso não concluído',
      descricao: 'A devolução não foi confirmada. Tente novamente ou entre em contato com o atendimento.',
    }
  }
  if (reembolsoPendente(pedido)) {
    return {
      titulo: 'Reembolso em andamento',
      descricao: 'A solicitação está sendo processada. Aguarde a confirmação do Mercado Pago.',
    }
  }
  if (pedido.status === 'CANCELADO') {
    return pedido.pagamento?.status === 'APROVADO'
      ? {
          titulo: 'Pagamento recebido após o cancelamento',
          descricao: 'O pedido permanece cancelado e a devolução será acompanhada nesta página.',
        }
      : {
          titulo: 'Checkout cancelado',
          descricao: 'A reserva foi encerrada e a quantidade voltou a ficar disponível.',
        }
  }
  if (pedido.status === 'AGUARDANDO_PAGAMENTO') {
    return {
      titulo: 'Estamos confirmando seu pagamento',
      descricao: 'Aguarde a confirmação segura do Mercado Pago. Você pode atualizar o pedido a qualquer momento.',
    }
  }
  if (pedido.status === 'EM_CONTESTACAO') {
    return {
      titulo: 'Pedido em contestação',
      descricao: 'Acompanhe a análise da contestação antes de realizar uma nova ação.',
    }
  }
  return {
    titulo: pedido.status === 'PAGAMENTO_APROVADO' ? 'Pagamento confirmado' : STATUS_PEDIDO[pedido.status],
    descricao: 'Acompanhe o pagamento e a entrega do seu pedido nesta página.',
  }
}

export function PagamentoRetornoPage() {
  const [parametros] = useSearchParams()
  const { pedidoId: idDaRota } = useParams()
  const pedidoId =
    idDaRota ??
    parametros.get('external_reference') ??
    sessionStorage.getItem('obraCircular:lastOrderId')
  return pedidoId ? <PedidoDetalhe key={pedidoId} pedidoId={pedidoId} /> : (
    <main className="payment-page">
      <section className="payment-card">
        <h1>Consultar pedido</h1>
        <p role="alert">Não foi possível identificar o pedido retornado pelo Mercado Pago.</p>
        <Link className="secondary-button" to="/pedidos">Ver meus pedidos</Link>
      </section>
    </main>
  )
}

function PedidoDetalhe({ pedidoId }: { pedidoId: string }) {
  const [pedido, setPedido] = useState<Pedido | null>(null)
  const [erroConsulta, setErroConsulta] = useState('')
  const [erroAcao, setErroAcao] = useState('')
  const [aviso, setAviso] = useState('')
  const [acaoEmAndamento, setAcaoEmAndamento] = useState<AcaoPedido | null>(null)
  const [mensagemAcao, setMensagemAcao] = useState('')
  const controle = useRef({ ativo: true, versao: 0, acao: false, tentativas: 0 })
  const timer = useRef<number | undefined>(undefined)
  const atualizarRef = useRef<() => Promise<void>>(async () => {})

  useEffect(() => {
    const estado = controle.current
    estado.ativo = true
    async function atualizar() {
      if (!estado.ativo || estado.acao) return
      window.clearTimeout(timer.current)
      const versao = ++estado.versao
      let continuar = true
      try {
        const recebido = await consultarPedido(pedidoId)
        if (!estado.ativo || versao !== estado.versao || estado.acao) return
        setPedido(recebido)
        setErroConsulta('')
        continuar = deveAtualizarPedido(recebido)
      } catch (falha) {
        if (!estado.ativo || versao !== estado.versao || estado.acao) return
        setErroConsulta(mensagemApiErro(falha, 'Não foi possível consultar o pedido.'))
      }
      if (!estado.ativo || versao !== estado.versao || estado.acao) return
      estado.tentativas += 1
      if (continuar && estado.tentativas < 60) {
        timer.current = window.setTimeout(() => void atualizar(), 2000)
      } else if (continuar) {
        setAviso('A confirmação está demorando. Use Atualizar pedido para consultar novamente.')
      } else {
        setAviso('')
      }
    }
    atualizarRef.current = atualizar
    void atualizar()
    return () => {
      estado.ativo = false
      estado.versao += 1
      window.clearTimeout(timer.current)
    }
  }, [pedidoId])

  async function executarAcao(acao: AcaoPedido) {
    const estado = controle.current
    if (!pedido || estado.acao || acaoEmAndamento) return
    estado.acao = true
    estado.versao += 1
    window.clearTimeout(timer.current)
    setAcaoEmAndamento(acao)
    setErroAcao('')
    setMensagemAcao('')
    try {
      if (acao === 'cancelar') {
        await cancelarCheckout(pedido.id)
        if (!estado.ativo) return
        setPedido({
          ...pedido,
          status: 'CANCELADO',
          pagamento: pedido.pagamento ? { ...pedido.pagamento, status: 'CANCELADO' } : null,
        })
        setMensagemAcao('Checkout cancelado. A quantidade reservada foi liberada.')
      } else {
        const reembolso = await solicitarReembolso(pedido.id)
        if (!estado.ativo) return
        setPedido({
          ...pedido,
          reembolso,
          status: reembolso.status === 'CONCLUIDO' ? 'REEMBOLSADO' : 'CANCELADO',
          pagamento: reembolso.status === 'CONCLUIDO' && pedido.pagamento
            ? { ...pedido.pagamento, status: 'REEMBOLSADO' }
            : pedido.pagamento,
        })
        if (reembolso.status === 'CONCLUIDO') {
          setMensagemAcao('Reembolso concluído com sucesso.')
        } else if (reembolso.status === 'SOLICITADO' || reembolso.status === 'PROCESSANDO') {
          setMensagemAcao('Reembolso solicitado. Aguarde a confirmação do Mercado Pago.')
        } else {
          setErroAcao('O reembolso não foi concluído. Tente novamente ou procure o atendimento.')
        }
      }
    } catch (falha) {
      if (estado.ativo) setErroAcao(mensagemApiErro(
        falha,
        acao === 'cancelar'
          ? 'Não foi possível cancelar o checkout.'
          : 'Não foi possível solicitar o reembolso.',
      ))
    } finally {
      estado.acao = false
      estado.tentativas = 0
      if (estado.ativo) {
        // Reconciliar também após erros: a operação pode ter sido persistida.
        await atualizarRef.current()
        if (estado.ativo) setAcaoEmAndamento(null)
      }
    }
  }

  const conteudo = conteudoDoPedido(pedido)
  const podeCancelar = pedido?.status === 'AGUARDANDO_PAGAMENTO'
  const podeReembolsar = Boolean(pedido && !reembolsoPendente(pedido) && (
    pedido.status === 'PAGAMENTO_APROVADO' ||
    pedido.status === 'PREPARANDO_ENTREGA' ||
    (pedido.status === 'CANCELADO' && pedido.pagamento?.status === 'APROVADO')
  ))
  const bloqueado = acaoEmAndamento !== null || Boolean(erroConsulta)
  return (
    <main className="payment-page">
      <section className="payment-card">
        <span className="step-label">Pedido</span>
        <h1>{conteudo.titulo}</h1>
        <p>{conteudo.descricao}</p>
        {erroAcao && <p className="form-alert" role="alert">{erroAcao}</p>}
        {erroConsulta && <p className="form-alert" role="alert">{erroConsulta}</p>}
        {mensagemAcao && <p className="payment-success" role="status">{mensagemAcao}</p>}
        {aviso && <p role="status">{aviso}</p>}
        {pedido && (
          <p className="payment-status">Pedido: <strong>{STATUS_PEDIDO[pedido.status]}</strong></p>
        )}
        <div className="payment-actions">
          {podeCancelar && (
            <button type="button" className="payment-danger-button" disabled={bloqueado}
              onClick={() => void executarAcao('cancelar')}>
              {acaoEmAndamento === 'cancelar' ? 'Cancelando...' : 'Cancelar checkout'}
            </button>
          )}
          {podeReembolsar && (
            <button type="button" className="payment-danger-button" disabled={bloqueado}
              onClick={() => void executarAcao('reembolsar')}>
              {acaoEmAndamento === 'reembolsar' ? 'Solicitando...' : 'Solicitar reembolso'}
            </button>
          )}
          <button type="button" className="secondary-button" disabled={acaoEmAndamento !== null}
            onClick={() => { controle.current.tentativas = 0; void atualizarRef.current() }}>
            Atualizar pedido
          </button>
        </div>
        <div className="payment-navigation">
          <Link className="secondary-button" to="/pedidos">Meus pedidos</Link>
          <Link className="secondary-button" to="/home">Voltar aos anúncios</Link>
        </div>
      </section>
    </main>
  )
}

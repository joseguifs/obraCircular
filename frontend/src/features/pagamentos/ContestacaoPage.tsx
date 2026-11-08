import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { mensagemApiErro } from '../../lib/api'
import { formatarDataHora, formatarMoeda } from '../../lib/formatarTempo'
import { abrirContestacao, consultarPedido, listarContestacoes } from './pagamentoApi'
import { contestacaoAtiva, MOTIVOS_CONTESTACAO, STATUS_CONTESTACAO } from './contestacaoApresentacao'
import { impedimentoContestacao, STATUS_PEDIDO } from './pedidoApresentacao'
import { useHorarioAtual } from './useHorarioAtual'
import type { Contestacao, ContestacaoMotivo, Pedido } from './types'
import './ContestacaoPage.css'

export function ContestacaoPage() {
  const { pedidoId } = useParams()

  return (
    <main className="payment-page dispute-page">
      <Link className="back-button" to={pedidoId ? `/pedidos/${pedidoId}` : '/pedidos'}>
        ← Voltar ao pedido
      </Link>
      <section className="payment-card">
        <span className="step-label">Minhas compras</span>
        <h1>Contestação do pedido</h1>
        <p>Teve um problema com os materiais? Informe o motivo, descreva o que aconteceu e acompanhe sua solicitação.</p>
        <p className="dispute-note">
          Você pode abrir uma contestação em até sete dias corridos após a confirmação da entrega,
          antes da liberação do repasse ao vendedor. O prazo e a situação do pedido são verificados ao enviar.
        </p>
        {pedidoId && <ContestacaoPedido key={pedidoId} pedidoId={pedidoId} />}
      </section>
    </main>
  )
}

export function ContestacaoPedido({ pedidoId }: { pedidoId: string }) {
  const [pedido, setPedido] = useState<Pedido | null>(null)
  const [historico, setHistorico] = useState<Contestacao[]>([])
  const [motivo, setMotivo] = useState<ContestacaoMotivo>('PRODUTO_DANIFICADO')
  const [descricao, setDescricao] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [enviando, setEnviando] = useState(false)
  const [erroConsulta, setErroConsulta] = useState('')
  const [erroAcao, setErroAcao] = useState('')
  const [sucesso, setSucesso] = useState('')
  const controle = useRef({ ativo: true, versao: 0, enviando: false })
  const agora = useHorarioAtual()

  const atualizar = useCallback(async () => {
    const estado = controle.current
    const versao = ++estado.versao
    try {
      const [atual, lista] = await Promise.all([consultarPedido(pedidoId), listarContestacoes(pedidoId)])
      if (!estado.ativo || versao !== estado.versao) return
      setPedido(atual)
      setHistorico(lista.items)
      setErroConsulta('')
    } catch (falha) {
      if (estado.ativo && versao === estado.versao) {
        setErroConsulta(mensagemApiErro(falha, 'Não foi possível atualizar o pedido e o histórico.'))
      }
    } finally {
      if (estado.ativo && versao === estado.versao) setCarregando(false)
    }
  }, [pedidoId])

  useEffect(() => {
    const estado = controle.current
    estado.ativo = true
    void Promise.resolve().then(atualizar)
    return () => { estado.ativo = false; estado.versao += 1 }
  }, [atualizar])

  const ativa = historico.some((item) => contestacaoAtiva(item.status))
  const impedimento = pedido ? impedimentoContestacao(pedido, agora) : ''
  const podeAbrir = pedido && !impedimento && !ativa
    && !carregando && !enviando && !erroConsulta

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    const estado = controle.current
    if (!podeAbrir || !descricao.trim() || estado.enviando) return
    estado.enviando = true
    estado.versao += 1
    setEnviando(true)
    setErroAcao('')
    setSucesso('')
    try {
      const criada = await abrirContestacao(pedidoId, { motivo, descricao: descricao.trim() })
      if (!estado.ativo) return
      setPedido((atual) => atual ? { ...atual, status: 'EM_CONTESTACAO' } : null)
      setHistorico((atual) => [criada, ...atual.filter((item) => item.id !== criada.id)])
      setSucesso('Contestação aberta com sucesso. Acompanhe o andamento pelo histórico abaixo.')
      setDescricao('')
    } catch (falha) {
      if (estado.ativo) setErroAcao(mensagemApiErro(falha, 'Não foi possível abrir a contestação.'))
    } finally {
      // Reconcilia também após erro: a operação pode ter sido concluída no servidor.
      if (estado.ativo) {
        setCarregando(true)
        await atualizar()
        if (estado.ativo) setEnviando(false)
      }
      estado.enviando = false
    }
  }

  return (
    <div className="dispute-content">
      {carregando && <p role="status">Atualizando pedido e contestações...</p>}
      {erroConsulta && <p className="form-alert" role="alert">{erroConsulta}</p>}
      {pedido && (
        <div className="dispute-summary">
          <p className="dispute-id">Pedido {pedido.id}</p>
          <dl>
            <div><dt>Situação</dt><dd>{STATUS_PEDIDO[pedido.status]}</dd></div>
            <div><dt>Total</dt><dd>{formatarMoeda(pedido.valor_total)}</dd></div>
          </dl>
          {pedido.entrega?.prazo_contestacao_em && <p>
            Prazo de contestação: {formatarDataHora(pedido.entrega.prazo_contestacao_em)}.
          </p>}
          <Link to={`/pedidos/${pedidoId}`}>Ver detalhes do pedido →</Link>
        </div>
      )}
      {sucesso && <p className="payment-success" role="status">{sucesso}</p>}
      {erroAcao && <p className="form-alert" role="alert">{erroAcao}</p>}
      {!carregando && (ativa || pedido?.status === 'EM_CONTESTACAO') && (
        <p>Este pedido já está em contestação. Acompanhe o histórico abaixo.</p>
      )}
      {!carregando && pedido && pedido.status !== 'EM_CONTESTACAO' && impedimento && (
        <p>{impedimento}</p>
      )}
      <form className="dispute-form" onSubmit={(evento) => void enviar(evento)}>
        <fieldset disabled={!podeAbrir}>
          <legend>Comunicar um problema</legend>
          <label htmlFor="motivo-contestacao">Motivo</label>
          <select id="motivo-contestacao" value={motivo}
            onChange={(evento) => setMotivo(evento.target.value as ContestacaoMotivo)}>
            {Object.entries(MOTIVOS_CONTESTACAO).map(([valor, rotulo]) => <option key={valor} value={valor}>{rotulo}</option>)}
          </select>
          <label htmlFor="descricao-contestacao">Descreva o problema</label>
          <textarea id="descricao-contestacao" value={descricao} rows={5} required maxLength={5000}
            aria-describedby="descricao-contestacao-ajuda"
            placeholder="Conte o que aconteceu com o material recebido."
            onChange={(evento) => setDescricao(evento.target.value)} />
          <span id="descricao-contestacao-ajuda" className="dispute-counter">{descricao.length}/5000 caracteres</span>
        </fieldset>
        <div className="payment-actions">
          <button className="publish-button" type="submit" disabled={!podeAbrir || !descricao.trim()}>
            {enviando ? 'Abrindo contestação...' : 'Abrir contestação'}
          </button>
          <button className="secondary-button" type="button" disabled={carregando || enviando}
            onClick={() => { setCarregando(true); void atualizar() }}>Atualizar pedido e histórico</button>
        </div>
      </form>
      <section className="dispute-history" aria-label="Histórico de contestações">
        <h2>Histórico de contestações</h2>
        {!carregando && !erroConsulta && historico.length === 0 && <p>Nenhuma contestação neste pedido.</p>}
        <ul>
          {historico.map((item) => (
            <li key={item.id}>
              <div className="dispute-history-title">
                <h3>{MOTIVOS_CONTESTACAO[item.motivo]}</h3>
                <span className="dispute-badge">{STATUS_CONTESTACAO[item.status]}</span>
              </div>
              <p className="dispute-description">{item.descricao}</p>
              <p>Aberta em <time dateTime={item.criado_em}>{new Date(item.criado_em).toLocaleString('pt-BR')}</time></p>
              {item.resolucao && <p>Resolução: {item.resolucao}</p>}
              <small className="dispute-id">Protocolo: {item.id}</small>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

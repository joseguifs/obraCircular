import { useEffect, useRef, useState, type FormEvent } from 'react'
import { mensagemApiErro } from '../../lib/api'
import { formatarData } from '../../lib/formatarTempo'
import { contestacaoPendente, MOTIVOS_CONTESTACAO, STATUS_CONTESTACAO } from '../pagamentos/contestacaoApresentacao'
import { decidirContestacaoAdmin, listarContestacoesAdmin } from './adminApi'
import { Paginacao } from './Paginacao'
import type { ContestacaoAdmin, ContestacaoStatus, DecisaoContestacao, ListaContestacoesAdmin } from './types'

const POR_PAGINA = 10

export function AdminContestacoesPage() {
  const [status, setStatus] = useState<'' | ContestacaoStatus>('')
  const [offset, setOffset] = useState(0)
  const [versao, setVersao] = useState(0)
  const [lista, setLista] = useState<ListaContestacoesAdmin | null>(null)
  const [concluida, setConcluida] = useState({ chave: '', erro: '' })
  const [confirmando, setConfirmando] = useState<{ item: ContestacaoAdmin; decisao: DecisaoContestacao } | null>(null)
  const [resolucao, setResolucao] = useState('')
  const [executando, setExecutando] = useState(false)
  const emExecucao = useRef(false)
  const [aviso, setAviso] = useState({ erro: false, texto: '' })
  const chave = `${status}:${offset}:${versao}`
  const carregando = concluida.chave !== chave

  useEffect(() => {
    let ativo = true
    listarContestacoesAdmin(status, offset, POR_PAGINA)
      .then((resposta) => {
        if (!ativo) return
        setLista(resposta)
        setConcluida({ chave, erro: '' })
      })
      .catch((erro) => {
        if (ativo) setConcluida({ chave, erro: mensagemApiErro(erro, 'Não foi possível carregar as contestações.') })
      })
    return () => { ativo = false }
  }, [chave, status, offset])

  function solicitar(item: ContestacaoAdmin, decisao: DecisaoContestacao) {
    setConfirmando({ item, decisao })
    setResolucao(item.resolucao ?? '')
    setAviso({ erro: false, texto: '' })
  }

  async function executar(evento: FormEvent) {
    evento.preventDefault()
    if (!confirmando || emExecucao.current) return
    if (resolucao.trim().length < 3) {
      setAviso({ erro: true, texto: 'Informe uma justificativa com pelo menos 3 caracteres.' })
      return
    }
    emExecucao.current = true
    setExecutando(true)
    try {
      const resposta = await decidirContestacaoAdmin(confirmando.item.id, confirmando.decisao, resolucao.trim())
      setAviso({ erro: resposta.reembolso_status === 'FALHOU', texto: resposta.reembolso_status === 'FALHOU'
        ? 'Contestação aprovada, mas o reembolso falhou. Verifique a conta do vendedor antes de tentar novamente.'
        : resposta.status === 'RECUSADA' ? 'Contestação recusada.'
        : resposta.status === 'RESOLVIDA' ? 'Contestação aprovada e reembolso confirmado.'
          : 'Contestação aprovada. O reembolso aguarda confirmação do provedor.' })
      setConfirmando(null)
    } catch (erro) {
      setAviso({ erro: true, texto: mensagemApiErro(erro, 'Não foi possível concluir a análise.') })
      setConfirmando(null)
    } finally {
      setVersao((atual) => atual + 1)
      setExecutando(false)
      emExecucao.current = false
    }
  }

  return (
    <main className="publish-page">
      <header className="publish-heading">
        <span className="step-label">Administração</span>
        <h1>Contestações</h1>
        <p>Analise os problemas relatados pelos compradores nos pedidos.</p>
      </header>
      {aviso.texto && <div className={aviso.erro ? 'publish-alert' : 'cat-success'} role={aviso.erro ? 'alert' : 'status'}>{aviso.texto}</div>}
      <div className="admin-filtros">
        <label className="publish-field">
          <span>Status</span>
          <select value={status} disabled={executando} onChange={(e) => {
            setStatus(e.target.value as '' | ContestacaoStatus)
            setOffset(0)
            setConfirmando(null)
          }}>
            <option value="">Todas</option>
            {Object.entries(STATUS_CONTESTACAO).map(([valor, rotulo]) => <option key={valor} value={valor}>{rotulo}</option>)}
          </select>
        </label>
        <button type="button" className="secondary-button" disabled={carregando || executando} onClick={() => setVersao((atual) => atual + 1)}>Atualizar</button>
      </div>
      {!carregando && concluida.erro && <div className="publish-alert" role="alert">{concluida.erro}</div>}
      <section className="publish-card" aria-label="Lista de contestações" aria-busy={carregando}>
        {carregando ? <p className="publish-loading">Carregando contestações…</p> : concluida.erro ? null : !lista?.items.length ? (
          <p className="publish-loading">Nenhuma contestação encontrada.</p>
        ) : (
          <ul className="cat-list">
            {lista.items.map((item) => (
              <li className="cat-item admin-contestacao" key={item.id}>
                <div className="cat-item-main">
                  <div className="cat-item-title"><h2>{item.anuncio_titulo}</h2><span className="cat-badge">{STATUS_CONTESTACAO[item.status]}</span></div>
                  <p>Pedido: {item.pedido_id}</p>
                  <p>Comprador: {item.comprador_nome} · Vendedor: {item.vendedor_nome}</p>
                  <p><strong>{MOTIVOS_CONTESTACAO[item.motivo] ?? item.motivo}</strong> · {formatarData(item.criado_em)}</p>
                  <p className="admin-contestacao-texto">{item.descricao}</p>
                  {item.resolucao && <p className="admin-contestacao-texto">Decisão: {item.resolucao}</p>}
                  {item.resolvida_em && <small>Analisada em {formatarData(item.resolvida_em)}</small>}
                  {item.reembolso_status && <p>Reembolso: {item.reembolso_status}</p>}
                </div>
                {confirmando?.item.id === item.id ? (
                  <form className="admin-decisao" onSubmit={executar}>
                    <p>{confirmando.decisao === 'ACEITA' ? 'Aprovar solicita o reembolso integral do pagamento. A conclusão depende do provedor.' : 'Recusar encerra a contestação e mantém a entrega do pedido.'}</p>
                    <label className="publish-field"><span>Justificativa</span>
                      <textarea value={resolucao} onChange={(e) => setResolucao(e.target.value)} required minLength={3} maxLength={2000} disabled={executando} />
                    </label>
                    <div className="admin-actions">
                      <button type="submit" className="publish-button" disabled={executando}>{executando ? 'Processando…' : confirmando.decisao === 'ACEITA' ? 'Confirmar aprovação' : 'Confirmar recusa'}</button>
                      <button type="button" className="secondary-button" disabled={executando} onClick={() => setConfirmando(null)}>Cancelar</button>
                    </div>
                  </form>
                ) : (
                  <div className="admin-actions">
                    {contestacaoPendente(item.status) && <>
                      <button type="button" className="publish-button" disabled={executando} onClick={() => solicitar(item, 'ACEITA')}>Aprovar</button>
                      <button type="button" className="secondary-button admin-button--perigo-texto" disabled={executando} onClick={() => solicitar(item, 'RECUSADA')}>Recusar</button>
                    </>}
                    {item.status === 'ACEITA' && (
                      item.reembolso_status === 'FALHOU' || item.reembolso_status === 'SOLICITADO'
                      || (item.reembolso_status === 'PROCESSANDO' && !item.reembolso_externo_id)
                    ) && (
                      <button type="button" className="secondary-button" disabled={executando} onClick={() => solicitar(item, 'ACEITA')}>Tentar reembolso novamente</button>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
        <Paginacao offset={offset} porPagina={POR_PAGINA} total={lista?.total ?? 0}
          desabilitada={carregando || executando || Boolean(concluida.erro)} aoMudar={(valor) => { setOffset(valor); setConfirmando(null) }} />
      </section>
    </main>
  )
}

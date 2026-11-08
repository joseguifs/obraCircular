import { useEffect, useRef, useState, type FormEvent } from 'react'
import { apiRequest, mensagemApiErro } from '../../lib/api'
import { formatarMoeda } from '../../lib/formatarTempo'
import { Paginacao } from './Paginacao'
import { formatarData } from './rotulos'

interface Repasse {
  id: string
  pedido_id: string
  vendedor_id: string
  vendedor_nome: string
  modelo_financeiro: string
  valor_bruto: string
  percentual_marketplace: string
  taxa_marketplace: string
  taxa_provedor: string
  valor_liquido: string
  taxas_por_conta_marketplace: boolean
  status: string
  liberacao_prevista_em: string | null
  pago_em: string | null
  destino_cadastrado: boolean
  pode_liberar: boolean
  pode_consultar: boolean
  destino_tipo?: string | null
  motivo_bloqueio: string | null
}

interface Evento { id: string; acao: string; status: string; criado_em: string }
interface Lista { items: Repasse[]; total: number; offset: number; limit: number }

const ROTULOS: Record<string, string> = {
  AGUARDANDO_ENTREGA: 'Aguardando entrega', EM_PERIODO_CONTESTACAO: 'Em período de contestação',
  BLOQUEADO: 'Bloqueado', PRONTO_PARA_LIBERACAO: 'Pronto para liberação',
  PROCESSANDO: 'Processando', PAGO: 'Pago', FALHOU: 'Falhou', CANCELADO: 'Cancelado',
  REEMBOLSADO: 'Reembolsado',
}

export function AdminRepassesPage() {
  const [lista, setLista] = useState<Lista | null>(null)
  const [status, setStatus] = useState('')
  const [offset, setOffset] = useState(0)
  const [revisao, setRevisao] = useState(0)
  const [concluida, setConcluida] = useState({ chave: '', erro: '' })
  const [salvando, setSalvando] = useState(false)
  const [aviso, setAviso] = useState({ erro: false, texto: '' })
  const [confirmacao, setConfirmacao] = useState('')
  const [destino, setDestino] = useState<Repasse | null>(null)
  const [eventos, setEventos] = useState<{ pedido: string; items: Evento[] } | null>(null)
  const emAcao = useRef(false)
  const ativo = useRef(true)
  const chave = `${status}:${offset}:${revisao}`
  const carregando = concluida.chave !== chave
  const erroLista = carregando ? '' : concluida.erro

  useEffect(() => {
    ativo.current = true
    return () => { ativo.current = false }
  }, [])

  useEffect(() => {
    let atual = true
    const query = new URLSearchParams({ offset: String(offset), limit: '10' })
    if (status) query.set('status', status)
    apiRequest<Lista>(`/admin/payouts?${query}`)
      .then((resposta) => {
        if (atual) { setLista(resposta); setConcluida({ chave, erro: '' }) }
      })
      .catch((falha) => {
        if (atual) setConcluida({ chave, erro: mensagemApiErro(falha, 'Não foi possível carregar os repasses.') })
      })
    return () => { atual = false }
  }, [chave, offset, status])

  async function executar(acao: () => Promise<unknown>, mensagem: string) {
    if (emAcao.current) return
    emAcao.current = true
    setSalvando(true)
    setAviso({ erro: false, texto: '' })
    try {
      await acao()
      if (ativo.current) setAviso({ erro: false, texto: mensagem })
    } catch (falha) {
      if (ativo.current) setAviso({ erro: true, texto: mensagemApiErro(falha, 'Não foi possível concluir a operação.') })
    } finally {
      emAcao.current = false
      if (ativo.current) {
        setSalvando(false)
        setConfirmacao('')
        setRevisao((atual) => atual + 1)
      }
    }
  }

  return (
    <main className="publish-page">
      <header className="publish-heading">
        <span className="step-label">Administração financeira</span>
        <h1>Repasses aos vendedores</h1>
        <p>Confira os valores de cada venda e libere os repasses após o período de contestação.</p>
      </header>
      {aviso.texto && <p className={aviso.erro ? 'publish-alert' : 'cat-success'}
        role={aviso.erro ? 'alert' : 'status'}>{aviso.texto}</p>}
      <div className="admin-filtros">
        <label className="publish-field"><span>Situação do repasse</span>
          <select value={status} disabled={salvando} onChange={(e) => {
            setStatus(e.target.value); setOffset(0); setConfirmacao('')
          }}>
            <option value="">Todas</option>
            {Object.entries(ROTULOS).map(([valor, rotulo]) => <option key={valor} value={valor}>{rotulo}</option>)}
          </select>
        </label>
        <button className="secondary-button" disabled={salvando || carregando}
          onClick={() => setRevisao((atual) => atual + 1)}>Atualizar repasses</button>
      </div>
      {carregando && <p role="status">Carregando repasses...</p>}
      {erroLista && <p className="publish-alert" role="alert">{erroLista}</p>}
      {erroLista && <button className="secondary-button" onClick={() => setRevisao((v) => v + 1)}>Tentar novamente</button>}
      {!carregando && !erroLista && lista?.items.length === 0 && <p>Nenhum repasse encontrado.</p>}
      {!carregando && !erroLista && <div className="admin-payout-list">
        {lista?.items.map((item) => (
          <article className="payment-card" key={item.id}>
            <h2>{item.vendedor_nome}</h2>
            <p>Pedido {item.pedido_id.slice(0, 8)} · <strong>{ROTULOS[item.status] ?? item.status}</strong></p>
            <dl className="admin-payout-values">
              <div><dt>Venda</dt><dd>{formatarMoeda(item.valor_bruto)}</dd></div>
              <div><dt>Comissão da venda ({Number(item.percentual_marketplace)}%)</dt><dd>{formatarMoeda(item.taxa_marketplace)}</dd></div>
              <div><dt>Tarifas do provedor</dt><dd>{formatarMoeda(item.taxa_provedor)}</dd></div>
              <div><dt>Valor do vendedor</dt><dd><strong>{formatarMoeda(item.valor_liquido)}</strong></dd></div>
            </dl>
            <p>{item.modelo_financeiro === 'SPLIT_LEGADO'
              ? 'Venda anterior com split automático. Não gera uma nova transferência.'
              : 'As tarifas do provedor são absorvidas pela comissão da Obra Circular.'}</p>
            {item.liberacao_prevista_em && <p>Fim da contestação: {formatarData(item.liberacao_prevista_em)}</p>}
            {item.motivo_bloqueio && <p>{item.motivo_bloqueio}</p>}
            {item.destino_tipo === 'CONTA_MP_TESTE' && (
              <p>Destino de teste: conta Mercado Pago por e-mail, sem Pix.</p>
            )}
            {item.status === 'PROCESSANDO' && !item.pode_consultar && (
              <p>O envio ainda não tem identificador confirmado no Mercado Pago.
                Retomar envio preserva o destino e os valores da tentativa original para evitar duplicações.</p>
            )}
            <div className="payment-actions">
              {item.modelo_financeiro === 'REPASSE_POSTERIOR' && (
                <button className="secondary-button" disabled={salvando}
                  onClick={() => { setDestino(item); setConfirmacao('') }}>
                  {item.destino_cadastrado ? 'Atualizar destino' : 'Cadastrar destino'}
                </button>
              )}
              <button className="publish-button" disabled={!item.pode_liberar || salvando}
                onClick={() => setConfirmacao(item.id)}>
                {item.status === 'PROCESSANDO' && !item.pode_consultar ? 'Retomar envio' : 'Liberar repasse'}
              </button>
              {item.modelo_financeiro === 'REPASSE_POSTERIOR'
                && item.pode_consultar
                && <button className="secondary-button" disabled={salvando}
                onClick={() => void executar(
                  () => apiRequest(`/admin/payouts/${item.id}/reconcile`, { method: 'POST' }),
                  'Estado consultado no provedor. Confira a situação atualizada do repasse.',
                )}>Consultar transferência</button>}
              <button className="secondary-button" disabled={salvando}
                onClick={() => void executar(async () => {
                  const items = await apiRequest<Evento[]>(`/admin/payouts/${item.id}/events`)
                  if (ativo.current) setEventos({ pedido: item.pedido_id, items })
                }, 'Histórico consultado.')}>Ver histórico</button>
            </div>
            {confirmacao === item.id && <div className="payment-status" role="group" aria-label="Confirmar liberação">
              <p>Enviar <strong>{formatarMoeda(item.valor_liquido)}</strong> a {item.vendedor_nome}?
                A transferência utilizará o destino conferido e os valores registrados na venda.</p>
              <div className="payment-actions">
                <button className="publish-button" disabled={salvando}
                  onClick={() => void executar(
                    () => apiRequest(`/admin/payouts/${item.id}/release`, { method: 'POST' }),
                    'Solicitação enviada. O repasse só será marcado como pago após confirmação do provedor.',
                  )}>{salvando ? 'Enviando...' : 'Confirmar transferência'}</button>
                <button className="secondary-button" disabled={salvando} onClick={() => setConfirmacao('')}>Voltar</button>
              </div>
            </div>}
          </article>
        ))}
      </div>}
      {destino && <DestinoForm key={destino.vendedor_id} repasse={destino} salvando={salvando}
        cancelar={() => setDestino(null)}
        salvar={(dados) => void executar(async () => {
          await apiRequest(`/admin/users/${destino.vendedor_id}/payout-destination`, {
            method: 'PUT', body: JSON.stringify(dados),
          })
          if (ativo.current) setDestino(null)
        }, 'Destino conferido e cadastrado. Instruções já iniciadas preservam o destino original.')} />}
      {eventos && <section className="payment-card" aria-label="Histórico do repasse">
        <h2>Histórico · pedido {eventos.pedido.slice(0, 8)}</h2>
        {eventos.items.length === 0 && <p>Nenhuma operação registrada.</p>}
        <ul>{eventos.items.map((evento) => <li key={evento.id}>
          {formatarData(evento.criado_em)} · {evento.acao} · {ROTULOS[evento.status] ?? evento.status}
        </li>)}</ul>
        <button className="secondary-button" onClick={() => setEventos(null)}>Fechar histórico</button>
      </section>}
      {lista && !carregando && !erroLista && <Paginacao offset={offset} porPagina={10} total={lista.total}
        desabilitada={salvando} aoMudar={setOffset} />}
    </main>
  )
}

interface DadosDestino { tipo_chave: string; chave: string; titularidade_conferida: true }

function DestinoForm({ repasse, salvando, cancelar, salvar }: {
  repasse: Repasse; salvando: boolean; cancelar: () => void; salvar: (dados: DadosDestino) => void
}) {
  const [tipo, setTipo] = useState('CPF')
  const [chave, setChave] = useState('')
  const [conferida, setConferida] = useState(false)
  function enviar(e: FormEvent) {
    e.preventDefault()
    if (conferida && chave.trim()) salvar({ tipo_chave: tipo, chave: chave.trim(), titularidade_conferida: true })
  }
  return <section className="payment-card">
    <h2>Destino de {repasse.vendedor_nome}</h2>
    <p>Confira a titularidade do destino com o vendedor antes de cadastrar.</p>
    <form onSubmit={enviar}>
      <label className="publish-field"><span>Tipo de destino</span>
        <select value={tipo} disabled={salvando} onChange={(e) => setTipo(e.target.value)}>
          {['CPF', 'CNPJ', 'EMAIL', 'PHONE', 'PIX_CODE'].map((valor) => <option key={valor}>{valor}</option>)}
        </select>
      </label>
      <label className="publish-field"><span>Chave Pix</span><input required maxLength={255}
        value={chave} disabled={salvando} autoComplete="off" onChange={(e) => setChave(e.target.value)} /></label>
      <label className="admin-checkbox"><input type="checkbox" required checked={conferida}
        disabled={salvando} onChange={(e) => setConferida(e.target.checked)} />Conferi a titularidade do vendedor</label>
      <div className="payment-actions">
        <button className="publish-button" disabled={salvando || !conferida || !chave.trim()}>Salvar destino conferido</button>
        <button className="secondary-button" type="button" disabled={salvando} onClick={cancelar}>Cancelar</button>
      </div>
    </form>
  </section>
}

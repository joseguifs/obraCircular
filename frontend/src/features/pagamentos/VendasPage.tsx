import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { mensagemApiErro } from '../../lib/api'
import { formatarDataHora, formatarMoeda } from '../../lib/formatarTempo'
import { confirmarEntrega, listarVendas } from './pagamentoApi'
import { aguardaEntrega, STATUS_PEDIDO } from './pedidoApresentacao'
import type { Pedido } from './types'

export function VendasPage() {
  const [pedidos, setPedidos] = useState<Pedido[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erroConsulta, setErroConsulta] = useState('')
  const [erroAcao, setErroAcao] = useState('')
  const [sucesso, setSucesso] = useState('')
  const [selecionado, setSelecionado] = useState('')
  const [pin, setPin] = useState('')
  const [enviando, setEnviando] = useState(false)
  const controle = useRef({ ativo: true, versao: 0, enviando: false })

  const atualizar = useCallback(async () => {
    const estado = controle.current
    const versao = ++estado.versao
    setCarregando(true)
    try {
      const lista = await listarVendas()
      if (!estado.ativo || estado.versao !== versao) return
      setPedidos(lista.items)
      setErroConsulta('')
    } catch (falha) {
      if (estado.ativo && estado.versao === versao) {
        setErroConsulta(mensagemApiErro(falha, 'Não foi possível carregar suas vendas.'))
      }
    } finally {
      if (estado.ativo && estado.versao === versao) setCarregando(false)
    }
  }, [])

  useEffect(() => {
    const estado = controle.current
    estado.ativo = true
    void Promise.resolve().then(() => { if (estado.ativo) void atualizar() })
    return () => { estado.ativo = false; estado.versao += 1 }
  }, [atualizar])

  async function enviar(evento: FormEvent, pedido: Pedido) {
    evento.preventDefault()
    const estado = controle.current
    if (estado.enviando || carregando || erroConsulta || !aguardaEntrega(pedido) || !/^[0-9]{5}$/.test(pin)) return
    estado.enviando = true
    estado.versao += 1
    setEnviando(true)
    setErroAcao('')
    setSucesso('')
    try {
      const entrega = await confirmarEntrega(pedido.id, pin)
      if (!estado.ativo) return
      setPedidos((atuais) => atuais.map((item) => item.id === pedido.id
        ? { ...item, status: 'ENTREGUE', entrega } : item))
      setSucesso(`Entrega do pedido ${pedido.id.slice(0, 8)} confirmada. O prazo de contestação do comprador começou.`)
      setSelecionado('')
      setPin('')
    } catch (falha) {
      if (estado.ativo) setErroAcao(mensagemApiErro(falha, 'Não foi possível confirmar a entrega.'))
    } finally {
      // Uma falha na resposta pode ocorrer depois da confirmação no servidor.
      if (estado.ativo) {
        await atualizar()
        if (estado.ativo) setEnviando(false)
      }
      estado.enviando = false
    }
  }

  const bloqueado = enviando || carregando || Boolean(erroConsulta)
  return (
    <main className="payment-page">
      <section className="payment-card">
        <span className="step-label">Área do vendedor</span>
        <h1>Minhas vendas</h1>
        <p>Após o comprador conferir o material, peça o PIN para confirmar a entrega ou retirada.</p>
        {carregando && <p role="status">Atualizando vendas...</p>}
        {erroConsulta && <p className="form-alert" role="alert">{erroConsulta}</p>}
        {erroAcao && <p className="form-alert" role="alert">{erroAcao}</p>}
        {sucesso && <p className="payment-success" role="status">{sucesso}</p>}
        <button type="button" className="secondary-button" disabled={carregando || enviando}
          onClick={() => void atualizar()}>Atualizar vendas</button>
        {!carregando && !erroConsulta && pedidos.length === 0 && <p>Você ainda não tem vendas.</p>}
        <ul className="delivery-sales-list">
          {pedidos.map((pedido) => <li className="delivery-panel" key={pedido.id}>
            <h2>Pedido {pedido.id.slice(0, 8)}</h2>
            <p><strong>{STATUS_PEDIDO[pedido.status]}</strong> · {pedido.quantidade} unidade(s) · {formatarMoeda(pedido.valor_total)}</p>
            <Link to={`/anuncios/${pedido.anuncio_id}`}>Ver anúncio</Link>
            {pedido.entrega?.confirmado_em && <p>Entrega confirmada em {formatarDataHora(pedido.entrega.confirmado_em)}.</p>}
            {pedido.entrega?.prazo_contestacao_em && <p>Prazo de contestação: {formatarDataHora(pedido.entrega.prazo_contestacao_em)}.</p>}
            {pedido.status === 'EM_CONTESTACAO' && <p>O pedido está em contestação e o repasse permanece bloqueado durante a análise.</p>}
            {aguardaEntrega(pedido) && (selecionado === pedido.id ? (
              <form className="checkout-form" onSubmit={(evento) => void enviar(evento, pedido)}>
                <label htmlFor="pin-entrega">PIN informado pelo comprador
                  <input id="pin-entrega" type="text" inputMode="numeric" autoComplete="off"
                    pattern="[0-9]{5}" minLength={5} maxLength={5} required value={pin}
                    disabled={bloqueado} aria-describedby="pin-entrega-ajuda"
                    onChange={(evento) => setPin(evento.target.value.replace(/[^0-9]/g, '').slice(0, 5))} />
                </label>
                <p id="pin-entrega-ajuda">Informe os cinco dígitos. Após cinco erros, o comprador precisará gerar outro PIN.
                  A confirmação registra o recebimento e inicia o prazo de sete dias para contestação.</p>
                <div className="payment-actions">
                  <button type="submit" className="publish-button" disabled={bloqueado || !/^[0-9]{5}$/.test(pin)}>
                    {enviando ? 'Validando PIN...' : 'Validar PIN e confirmar entrega'}
                  </button>
                  <button type="button" className="secondary-button" disabled={enviando}
                    onClick={() => { setSelecionado(''); setPin('') }}>Cancelar</button>
                </div>
              </form>
            ) : <div className="payment-actions">
              <button type="button" className="publish-button" disabled={bloqueado}
                onClick={() => { setSelecionado(pedido.id); setPin(''); setErroAcao(''); setSucesso('') }}>
                Confirmar {pedido.modalidade_entrega === 'RETIRADA' ? 'retirada' : 'entrega'}
              </button>
            </div>)}
          </li>)}
        </ul>
        <Link className="secondary-button" to="/pedidos">Meus pedidos</Link>
      </section>
    </main>
  )
}

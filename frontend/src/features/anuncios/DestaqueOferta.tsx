import { useEffect, useState } from 'react'
import { mensagemApiErro } from '../../lib/api'
import { formatarDataHora, formatarMoeda } from '../../lib/formatarTempo'
import { consultarPrecoDestaque, iniciarCheckoutDestaque } from './destaqueApi'
import type { DestaquePreco } from './types'

interface DestaqueOfertaProps {
  anuncioId: string
  destaqueAte?: string | null
  emDestaque?: boolean
  aoFechar: () => void
}

/** Painel de compra do destaque: mostra o preço e leva o vendedor ao Mercado Pago. */
export function DestaqueOferta({ anuncioId, destaqueAte, emDestaque, aoFechar }: DestaqueOfertaProps) {
  const [preco, setPreco] = useState<DestaquePreco | null>(null)
  const [erro, setErro] = useState('')
  const [pagando, setPagando] = useState(false)

  useEffect(() => {
    let ativo = true
    consultarPrecoDestaque()
      .then((recebido) => {
        if (ativo) setPreco(recebido)
      })
      .catch((falha) => {
        if (ativo) setErro(mensagemApiErro(falha, 'Não foi possível consultar o preço do destaque.'))
      })
    return () => {
      ativo = false
    }
  }, [])

  async function pagar() {
    setPagando(true)
    setErro('')
    try {
      const checkout = await iniciarCheckoutDestaque(anuncioId)
      window.location.assign(checkout.init_point)
    } catch (falha) {
      setErro(mensagemApiErro(falha, 'Não foi possível abrir o pagamento. Tente novamente.'))
      setPagando(false)
    }
  }

  return (
    <section className="destaque-oferta" aria-label="Destacar anúncio" aria-busy={!preco && !erro}>
      <div className="destaque-fita" aria-hidden="true" />
      <div className="destaque-oferta-corpo">
        <div className="destaque-oferta-preco">
          <strong>{preco ? formatarMoeda(preco.valor) : '—'}</strong>
          <span>{preco ? `${preco.duracao_dias} dias no topo das buscas` : 'Consultando o preço…'}</span>
        </div>
        <ul className="destaque-oferta-itens">
          <li>Seu anúncio aparece antes dos outros na página inicial e nas buscas.</li>
          <li>Ganha o selo Em destaque nos resultados.</li>
          {emDestaque && destaqueAte ? (
            <li>Os dias são somados ao destaque atual, que vai até {formatarDataHora(destaqueAte)}.</li>
          ) : (
            <li>Começa assim que o Mercado Pago confirmar o pagamento.</li>
          )}
        </ul>
        {erro && <p className="destaque-oferta-erro" role="alert">{erro}</p>}
        <div className="destaque-oferta-acoes">
          <button
            type="button"
            className="destaque-botao"
            disabled={!preco || pagando}
            onClick={() => void pagar()}
          >
            {pagando ? 'Abrindo Mercado Pago…' : 'Pagar com Mercado Pago'}
          </button>
          <button type="button" className="destaque-botao-secundario" disabled={pagando} onClick={aoFechar}>
            Agora não
          </button>
        </div>
      </div>
    </section>
  )
}

/** Selo com a fita de sinalização usado nos anúncios em destaque. */
export function SeloDestaque({ className = '' }: { className?: string }) {
  return <span className={`destaque-selo ${className}`.trim()}>Em destaque</span>
}

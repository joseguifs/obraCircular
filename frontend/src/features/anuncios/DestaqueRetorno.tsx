import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { mensagemApiErro } from '../../lib/api'
import { formatarDataHora, formatarMoeda } from '../../lib/formatarTempo'
import { consultarDestaque } from './destaqueApi'
import type { DestaqueCompra } from './types'

const MAX_TENTATIVAS = 60

function aguardandoConfirmacao(destaque: DestaqueCompra): boolean {
  return destaque.status === 'AGUARDANDO_PAGAMENTO' && destaque.status_pagamento !== 'RECUSADO'
}

function conteudo(destaque: DestaqueCompra | null) {
  if (!destaque) return { titulo: 'Destaque do anúncio', descricao: 'Carregando os dados do pagamento.' }
  if (destaque.status === 'ATIVO') {
    return {
      titulo: 'Destaque ativado',
      descricao: destaque.expira_em
        ? `Seu anúncio aparece em destaque até ${formatarDataHora(destaque.expira_em)}.`
        : 'Seu anúncio já aparece em destaque.',
    }
  }
  if (destaque.status === 'REEMBOLSADO') {
    return { titulo: 'Destaque estornado', descricao: 'O pagamento foi devolvido e o destaque removido.' }
  }
  if (destaque.status === 'CANCELADO') {
    return {
      titulo: 'Pagamento do destaque cancelado',
      descricao: 'Nenhuma cobrança foi confirmada. Você pode tentar novamente em Meus anúncios.',
    }
  }
  if (destaque.status_pagamento === 'RECUSADO') {
    return {
      titulo: 'Pagamento recusado',
      descricao: 'O Mercado Pago recusou o pagamento. Tente novamente com outro meio de pagamento.',
    }
  }
  return {
    titulo: 'Estamos confirmando seu pagamento',
    descricao: 'Aguarde a confirmação segura do Mercado Pago. O destaque é ativado logo em seguida.',
  }
}

export function DestaqueRetorno({ destaqueId }: { destaqueId: string }) {
  const [destaque, setDestaque] = useState<DestaqueCompra | null>(null)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')
  const timer = useRef<number | undefined>(undefined)
  const atualizarRef = useRef<() => Promise<void>>(async () => {})

  useEffect(() => {
    let ativo = true
    let tentativas = 0
    async function atualizar() {
      window.clearTimeout(timer.current)
      let continuar = true
      try {
        const recebido = await consultarDestaque(destaqueId)
        if (!ativo) return
        setDestaque(recebido)
        setErro('')
        continuar = aguardandoConfirmacao(recebido)
      } catch (falha) {
        if (!ativo) return
        setErro(mensagemApiErro(falha, 'Não foi possível consultar o pagamento do destaque.'))
      }
      tentativas += 1
      if (continuar && tentativas < MAX_TENTATIVAS) {
        timer.current = window.setTimeout(() => void atualizar(), 2000)
      } else if (continuar) {
        setAviso('O acompanhamento automático foi pausado. Use Atualizar para consultar novamente.')
      } else {
        setAviso('')
      }
    }
    atualizarRef.current = async () => {
      tentativas = 0
      await atualizar()
    }
    void atualizar()
    return () => {
      ativo = false
      window.clearTimeout(timer.current)
    }
  }, [destaqueId])

  const texto = conteudo(destaque)
  return (
    <main className="payment-page">
      <section className="payment-card">
        <span className="step-label">Destaque do anúncio</span>
        <h1>{texto.titulo}</h1>
        <p>{texto.descricao}</p>
        {erro && <p className="form-alert" role="alert">{erro}</p>}
        {aviso && <p role="status">{aviso}</p>}
        {destaque && (
          <p className="payment-status">
            Valor: <strong>{formatarMoeda(destaque.valor)}</strong> · {destaque.duracao_dias} dias de destaque
          </p>
        )}
        <div className="payment-actions">
          <button type="button" className="secondary-button" onClick={() => void atualizarRef.current()}>
            Atualizar
          </button>
        </div>
        <div className="payment-navigation">
          <Link className="secondary-button" to="/anuncios/meus">Meus anúncios</Link>
          {destaque && (
            <Link className="secondary-button" to={`/anuncios/${destaque.anuncio_id}`}>Ver anúncio</Link>
          )}
        </div>
      </section>
    </main>
  )
}

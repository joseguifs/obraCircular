import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { mensagemApiErro } from '../../lib/api'
import { formatarMoeda } from '../../lib/formatarTempo'
import { listarMeusAnuncios } from './anuncioApi'
import { DestaqueOferta, SeloDestaque } from './DestaqueOferta'
import type { Anuncio } from './types'

interface DestaqueDialogProps {
  /** Anúncio já escolhido (botão do card). Sem ele, o vendedor escolhe na lista. */
  anuncio?: Anuncio | null
  aoFechar: () => void
}

/** Janela para destacar um anúncio do próprio vendedor sem sair da página. */
export function DestaqueDialog({ anuncio = null, aoFechar }: DestaqueDialogProps) {
  const [escolhido, setEscolhido] = useState<Anuncio | null>(anuncio)
  const [opcoes, setOpcoes] = useState<Anuncio[] | null>(anuncio ? [anuncio] : null)
  const [erro, setErro] = useState('')
  const painel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (anuncio) return
    let ativo = true
    listarMeusAnuncios({ status: 'ATIVO', limit: 50 })
      .then((resposta) => {
        if (ativo) setOpcoes(resposta.items)
      })
      .catch((falha) => {
        if (ativo) setErro(mensagemApiErro(falha, 'Não foi possível carregar seus anúncios.'))
      })
    return () => {
      ativo = false
    }
  }, [anuncio])

  // Foco entra na janela ao abrir e volta para quem a abriu ao fechar.
  useEffect(() => {
    const anterior = document.activeElement as HTMLElement | null
    painel.current?.focus()
    function aoTeclar(evento: KeyboardEvent) {
      if (evento.key === 'Escape') aoFechar()
    }
    document.addEventListener('keydown', aoTeclar)
    return () => {
      document.removeEventListener('keydown', aoTeclar)
      anterior?.focus()
    }
  }, [aoFechar])

  return (
    <div className="destaque-dialog-fundo" onMouseDown={(evento) => {
      if (evento.target === evento.currentTarget) aoFechar()
    }}>
      <div
        ref={painel}
        className="destaque-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="destaque-dialog-titulo"
        tabIndex={-1}
      >
        <div className="destaque-dialog-cabecalho">
          <h2 id="destaque-dialog-titulo">
            {escolhido ? `Destacar “${escolhido.titulo}”` : 'Qual anúncio você quer destacar?'}
          </h2>
          <button type="button" className="destaque-dialog-fechar" onClick={aoFechar} aria-label="Fechar">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </button>
        </div>

        {escolhido ? (
          <>
            <DestaqueOferta
              anuncioId={escolhido.id}
              emDestaque={escolhido.em_destaque}
              destaqueAte={escolhido.destaque_ate}
              aoFechar={anuncio ? aoFechar : () => setEscolhido(null)}
            />
            {!anuncio && (
              <button type="button" className="destaque-dialog-trocar" onClick={() => setEscolhido(null)}>
                Escolher outro anúncio
              </button>
            )}
          </>
        ) : (
          <>
            {erro && <p className="destaque-oferta-erro" role="alert">{erro}</p>}
            {!erro && opcoes === null && <p role="status">Carregando seus anúncios…</p>}
            {opcoes?.length === 0 && (
              <div className="destaque-dialog-vazio">
                <p>Você não tem anúncios disponíveis para destacar.</p>
                <Link className="publish-button" to="/anuncios/novo" onClick={aoFechar}>
                  Publicar um anúncio
                </Link>
              </div>
            )}
            {opcoes && opcoes.length > 0 && (
              <ul className="destaque-dialog-lista">
                {opcoes.map((opcao) => (
                  <li key={opcao.id}>
                    <button type="button" onClick={() => setEscolhido(opcao)}>
                      <span className="destaque-dialog-item-titulo">{opcao.titulo}</span>
                      <span className="destaque-dialog-item-meta">
                        {formatarMoeda(opcao.preco)} por unidade, {opcao.quantidade}{' '}
                        {opcao.quantidade === 1 ? 'disponível' : 'disponíveis'}
                      </span>
                      {opcao.em_destaque && <SeloDestaque />}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  )
}

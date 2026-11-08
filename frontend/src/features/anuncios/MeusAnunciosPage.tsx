import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { Paginacao } from '../admin/Paginacao'
import { mensagemApiErro, resolverUrlDaApi } from '../../lib/api'
import { formatarMoeda, formatarTempoRelativo } from '../../lib/formatarTempo'
import { listarMeusAnuncios } from './anuncioApi'
import type { Anuncio } from './types'

const POR_PAGINA = 10

type FiltroStatus = '' | Anuncio['status']

const FILTROS: Array<{ valor: FiltroStatus; rotulo: string }> = [
  { valor: '', rotulo: 'Todos' },
  { valor: 'ATIVO', rotulo: 'Disponíveis' },
  { valor: 'ESGOTADO', rotulo: 'Esgotados' },
  { valor: 'ENCERRADO', rotulo: 'Encerrados' },
]

const ROTULO_STATUS: Record<Anuncio['status'], string> = {
  ATIVO: 'Disponível',
  ESGOTADO: 'Esgotado',
  ENCERRADO: 'Encerrado',
}

export function MeusAnunciosPage() {
  const [status, setStatus] = useState<FiltroStatus>('')
  const [offset, setOffset] = useState(0)
  const [anuncios, setAnuncios] = useState<Anuncio[]>([])
  const [total, setTotal] = useState(0)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    setErro('')
    listarMeusAnuncios({
      status: status || undefined,
      offset,
      limit: POR_PAGINA,
    })
      .then((resposta) => {
        if (!ativo) return
        setAnuncios(resposta.items)
        setTotal(resposta.total)
      })
      .catch((erroRecebido) => {
        if (!ativo) return
        setErro(mensagemApiErro(erroRecebido, 'Não foi possível carregar seus anúncios.'))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [status, offset])

  function escolherStatus(novoStatus: FiltroStatus) {
    setStatus(novoStatus)
    setOffset(0)
  }

  return (
    <main className="meus-anuncios-main">
      <div className="meus-anuncios-cabecalho">
        <div>
          <span className="step-label">Sua vitrine</span>
          <h1>Meus anúncios</h1>
          <p>
            {carregando
              ? 'Carregando seus anúncios…'
              : `${total} ${total === 1 ? 'anúncio' : 'anúncios'} ${status ? 'nesta situação' : 'publicados por você'}.`}
          </p>
        </div>
        <Link to="/anuncios/novo" className="meus-anuncios-novo">
          Novo anúncio
        </Link>
      </div>

      <div className="meus-anuncios-filtros" role="group" aria-label="Filtrar por situação">
        {FILTROS.map((filtro) => (
          <button
            key={filtro.rotulo}
            type="button"
            className={
              status === filtro.valor ? 'home-filtro home-filtro--ativo' : 'home-filtro'
            }
            onClick={() => escolherStatus(filtro.valor)}
          >
            {filtro.rotulo}
          </button>
        ))}
      </div>

      {erro && (
        <div className="home-alert" role="alert">
          {erro}
        </div>
      )}

      {!erro && !carregando && anuncios.length === 0 && (
        <div className="home-vazio">
          <p className="home-vazio-titulo">Nenhum anúncio por aqui</p>
          <p>
            {status
              ? 'Não há anúncios nesta situação. Escolha outro filtro.'
              : 'Publique seu primeiro anúncio para vê-lo listado aqui.'}
          </p>
        </div>
      )}

      {anuncios.length > 0 && (
        <ul className="meus-anuncios-lista">
          {anuncios.map((anuncio) => {
            const capa = anuncio.imagem_capa_url ?? anuncio.imagem_url
            return (
              <li key={anuncio.id} className="meus-anuncios-item">
                <Link
                  to={`/anuncios/${anuncio.id}`}
                  className="meus-anuncios-link"
                  aria-label={`Ver anúncio ${anuncio.titulo}`}
                >
                  <div className="meus-anuncios-foto">
                    {capa ? (
                      <img src={resolverUrlDaApi(capa)} alt={`Foto de ${anuncio.titulo}`} />
                    ) : (
                      <span>Sem foto</span>
                    )}
                  </div>
                  <div className="meus-anuncios-corpo">
                    <h2>{anuncio.titulo}</h2>
                    <p className="meus-anuncios-tempo">
                      Publicado {formatarTempoRelativo(anuncio.postado_em)}
                    </p>
                    <div className="meus-anuncios-rodape">
                      <strong>{formatarMoeda(anuncio.preco)}</strong>
                      <span>{anuncio.quantidade} unidades</span>
                      <span
                        className={`meus-anuncios-status meus-anuncios-status--${anuncio.status.toLowerCase()}`}
                      >
                        {ROTULO_STATUS[anuncio.status]}
                      </span>
                    </div>
                  </div>
                </Link>
              </li>
            )
          })}
        </ul>
      )}

      <Paginacao
        offset={offset}
        porPagina={POR_PAGINA}
        total={total}
        desabilitada={carregando}
        aoMudar={setOffset}
      />
    </main>
  )
}

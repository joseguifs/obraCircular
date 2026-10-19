import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { mensagemApiErro, resolverUrlDaApi } from '../../lib/api'
import { formatarMoeda } from '../../lib/formatarTempo'
import { encerrarAnuncioAdmin, excluirAnuncioAdmin, listarAnunciosAdmin } from './adminApi'
import { Paginacao } from './Paginacao'
import { formatarData, ROTULOS_STATUS_ANUNCIO } from './rotulos'
import type { AnuncioAdmin, AnuncioStatus, ListaAnunciosAdmin } from './types'

const POR_PAGINA = 10

type Acao = { tipo: 'encerrar' | 'excluir'; anuncioId: string } | null

export function AdminAnunciosPage() {
  const [status, setStatus] = useState<'' | AnuncioStatus>('')
  const [busca, setBusca] = useState('')
  const [buscaDigitada, setBuscaDigitada] = useState('')
  const [incluirExcluidos, setIncluirExcluidos] = useState(false)
  const [offset, setOffset] = useState(0)
  const [versao, setVersao] = useState(0)
  const [lista, setLista] = useState<ListaAnunciosAdmin | null>(null)
  const [concluida, setConcluida] = useState({ chave: '', erro: '' })
  const [confirmando, setConfirmando] = useState<Acao>(null)
  const [executando, setExecutando] = useState(false)
  const [aviso, setAviso] = useState({ tipo: '', texto: '' })

  // Identifica a consulta atual; enquanto a última concluída for outra, está carregando.
  const chave = `${status}:${busca}:${incluirExcluidos}:${offset}:${versao}`
  const carregando = concluida.chave !== chave
  const erroLista = carregando ? '' : concluida.erro

  useEffect(() => {
    let ativo = true
    listarAnunciosAdmin({ status, busca, incluirExcluidos, offset, limit: POR_PAGINA })
      .then((resposta) => {
        if (!ativo) return
        setLista(resposta)
        setConcluida({ chave, erro: '' })
      })
      .catch((erro) => {
        if (!ativo) return
        setConcluida({ chave, erro: mensagemApiErro(erro, 'Não foi possível carregar os anúncios.') })
      })
    return () => {
      ativo = false
    }
  }, [chave, status, busca, incluirExcluidos, offset])

  function buscar(evento: FormEvent) {
    evento.preventDefault()
    setBusca(buscaDigitada.trim())
    setOffset(0)
  }

  async function executar(acao: NonNullable<Acao>) {
    setExecutando(true)
    try {
      if (acao.tipo === 'encerrar') {
        await encerrarAnuncioAdmin(acao.anuncioId)
        setAviso({ tipo: 'sucesso', texto: 'Anúncio encerrado.' })
      } else {
        await excluirAnuncioAdmin(acao.anuncioId)
        setAviso({ tipo: 'sucesso', texto: 'Anúncio excluído.' })
      }
      setConfirmando(null)
      setVersao((atual) => atual + 1)
    } catch (erro) {
      setAviso({ tipo: 'erro', texto: mensagemApiErro(erro, 'Não foi possível concluir a ação.') })
    } finally {
      setExecutando(false)
    }
  }

  const itens = lista?.items ?? []

  return (
    <main className="publish-page">
      <header className="publish-heading">
        <span className="step-label">Administração</span>
        <h1>Anúncios</h1>
        <p>Modere os anúncios publicados por todos os vendedores do marketplace.</p>
      </header>

      {aviso.texto && (
        <div
          className={aviso.tipo === 'erro' ? 'publish-alert' : 'cat-success'}
          role={aviso.tipo === 'erro' ? 'alert' : 'status'}
        >
          {aviso.texto}
        </div>
      )}

      <form className="admin-filtros" role="search" onSubmit={buscar}>
        <label className="publish-field">
          <span>Buscar</span>
          <input
            type="search"
            value={buscaDigitada}
            onChange={(e) => setBuscaDigitada(e.target.value)}
            placeholder="Título, vendedor ou e-mail"
          />
        </label>
        <label className="publish-field">
          <span>Status</span>
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as '' | AnuncioStatus)
              setOffset(0)
            }}
          >
            <option value="">Todos</option>
            {Object.entries(ROTULOS_STATUS_ANUNCIO).map(([valor, rotulo]) => (
              <option key={valor} value={valor}>
                {rotulo}
              </option>
            ))}
          </select>
        </label>
        <label className="admin-checkbox">
          <input
            type="checkbox"
            checked={incluirExcluidos}
            onChange={(e) => {
              setIncluirExcluidos(e.target.checked)
              setOffset(0)
            }}
          />
          Incluir excluídos
        </label>
        <button type="submit" className="publish-button">
          Buscar
        </button>
      </form>

      {erroLista && (
        <div className="publish-alert" role="alert">
          {erroLista}
        </div>
      )}

      <section className="publish-card" aria-label="Lista de anúncios" aria-busy={carregando}>
        {carregando && !lista ? (
          <p className="publish-loading">Carregando anúncios…</p>
        ) : itens.length === 0 ? (
          <p className="publish-loading">Nenhum anúncio encontrado.</p>
        ) : (
          <ul className="cat-list">
            {itens.map((anuncio) => (
              <LinhaAnuncio
                key={anuncio.id}
                anuncio={anuncio}
                confirmando={confirmando?.anuncioId === anuncio.id ? confirmando.tipo : null}
                executando={executando}
                aoSolicitar={(tipo) => {
                  setAviso({ tipo: '', texto: '' })
                  setConfirmando({ tipo, anuncioId: anuncio.id })
                }}
                aoConfirmar={() => confirmando && executar(confirmando)}
                aoCancelar={() => setConfirmando(null)}
              />
            ))}
          </ul>
        )}

        <Paginacao
          offset={offset}
          porPagina={POR_PAGINA}
          total={lista?.total ?? 0}
          desabilitada={carregando}
          aoMudar={setOffset}
        />
      </section>
    </main>
  )
}

interface LinhaAnuncioProps {
  anuncio: AnuncioAdmin
  confirmando: 'encerrar' | 'excluir' | null
  executando: boolean
  aoSolicitar: (tipo: 'encerrar' | 'excluir') => void
  aoConfirmar: () => void
  aoCancelar: () => void
}

function LinhaAnuncio({
  anuncio,
  confirmando,
  executando,
  aoSolicitar,
  aoConfirmar,
  aoCancelar,
}: LinhaAnuncioProps) {
  const excluido = anuncio.deletado_em !== null

  return (
    <li className="cat-item admin-item">
      <div className="admin-thumb" aria-hidden="true">
        {anuncio.imagem_capa_url && <img src={resolverUrlDaApi(anuncio.imagem_capa_url)} alt="" />}
      </div>
      <div className="cat-item-main">
        <div className="cat-item-title">
          <h2>
            {excluido ? anuncio.titulo : <Link to={`/anuncios/${anuncio.id}`}>{anuncio.titulo}</Link>}
          </h2>
          <span className={`cat-badge admin-badge--${anuncio.status.toLowerCase()}`}>
            {ROTULOS_STATUS_ANUNCIO[anuncio.status]}
          </span>
          {excluido && <span className="cat-badge admin-badge--excluido">Excluído</span>}
        </div>
        <p>
          {formatarMoeda(anuncio.preco)} · {anuncio.quantidade} un. · {anuncio.categoria_nome}
        </p>
        <small>
          {anuncio.vendedor_nome} ({anuncio.vendedor_email}) · publicado em{' '}
          {formatarData(anuncio.postado_em)}
        </small>
      </div>

      {!excluido && (
        <div className="admin-actions">
          {confirmando ? (
            <>
              <button
                type="button"
                className="publish-button admin-button--perigo"
                disabled={executando}
                onClick={aoConfirmar}
              >
                {confirmando === 'encerrar' ? 'Confirmar encerramento' : 'Confirmar exclusão'}
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={executando}
                onClick={aoCancelar}
              >
                Cancelar
              </button>
            </>
          ) : (
            <>
              {anuncio.status !== 'ENCERRADO' && (
                <button
                  type="button"
                  className="secondary-button"
                  aria-label={`Encerrar ${anuncio.titulo}`}
                  onClick={() => aoSolicitar('encerrar')}
                >
                  Encerrar
                </button>
              )}
              <button
                type="button"
                className="secondary-button admin-button--perigo-texto"
                aria-label={`Excluir ${anuncio.titulo}`}
                onClick={() => aoSolicitar('excluir')}
              >
                Excluir
              </button>
            </>
          )}
        </div>
      )}
    </li>
  )
}

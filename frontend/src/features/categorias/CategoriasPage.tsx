import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, mensagemApiErro } from '../../lib/api'
import { atualizarCategoria, criarCategoria, listarCategorias } from './categoriaApi'
import type {
  Categoria,
  CategoriaStatus,
  ErrosCategoria,
  FiltroStatus,
  ListaCategorias,
} from './types'
import {
  camposAlterados,
  DESCRICAO_MAXIMA,
  NOME_MAXIMO,
  normalizarNome,
  validarCategoria,
} from './validacaoCategoria'

const POR_PAGINA = 10

type Painel = { modo: 'novo' } | { modo: 'editar'; categoria: Categoria } | null

// TODO(autenticação): esta tela é pública por enquanto. Quando o perfil administrativo
// existir, mover a rota para dentro do ProtectedRoute e voltar a exigir login na API.
export function CategoriasPage() {
  const [filtro, setFiltro] = useState<FiltroStatus>('')
  const [offset, setOffset] = useState(0)
  const [versao, setVersao] = useState(0)
  const [lista, setLista] = useState<ListaCategorias | null>(null)
  const [concluida, setConcluida] = useState({ chave: '', erro: '' })
  const [painel, setPainel] = useState<Painel>(null)
  const [aviso, setAviso] = useState('')

  // Identifica a consulta atual; enquanto a última concluída for outra, está carregando.
  const chave = `${filtro}:${offset}:${versao}`
  const carregando = concluida.chave !== chave
  const erroLista = carregando ? '' : concluida.erro

  useEffect(() => {
    let ativo = true
    listarCategorias({ status: filtro, offset, limit: POR_PAGINA })
      .then((resposta) => {
        if (!ativo) return
        setLista(resposta)
        setConcluida({ chave, erro: '' })
      })
      .catch((erro) => {
        if (!ativo) return
        setConcluida({
          chave,
          erro: mensagemApiErro(erro, 'Não foi possível carregar as categorias.'),
        })
      })
    return () => {
      ativo = false
    }
  }, [chave, filtro, offset])

  function alterarFiltro(novoFiltro: FiltroStatus) {
    setFiltro(novoFiltro)
    setOffset(0)
  }

  function concluirFormulario(mensagem: string) {
    setPainel(null)
    setAviso(mensagem)
    setVersao((atual) => atual + 1)
  }

  const itens = lista?.items ?? []
  const total = lista?.total ?? 0
  const primeiro = total === 0 ? 0 : offset + 1
  const ultimo = Math.min(offset + POR_PAGINA, total)

  return (
    <main className="publish-page">
      <header className="publish-heading">
        <span className="step-label">Administração</span>
        <h1>Categorias</h1>
        <p>Cadastre, consulte e edite as categorias usadas nos anúncios de materiais.</p>
      </header>

      {aviso && (
        <div className="cat-success" role="status">
          {aviso}
        </div>
      )}

      {painel ? (
        <section className="publish-card cat-panel" aria-label="Formulário de categoria">
          <CategoriaForm
            key={painel.modo === 'editar' ? painel.categoria.id : 'novo'}
            categoria={painel.modo === 'editar' ? painel.categoria : undefined}
            aoConcluir={concluirFormulario}
            aoCancelar={() => setPainel(null)}
          />
        </section>
      ) : (
        <div className="cat-toolbar">
          <label className="publish-field cat-filter">
            <span>Status</span>
            <select
              value={filtro}
              onChange={(e) => alterarFiltro(e.target.value as FiltroStatus)}
            >
              <option value="">Todas</option>
              <option value="ATIVA">Ativas</option>
              <option value="INATIVA">Inativas</option>
            </select>
          </label>
          <button
            type="button"
            className="publish-button"
            onClick={() => {
              setAviso('')
              setPainel({ modo: 'novo' })
            }}
          >
            + Nova categoria
          </button>
        </div>
      )}

      {erroLista && (
        <div className="publish-alert" role="alert">
          {erroLista}
        </div>
      )}

      <section className="publish-card" aria-label="Lista de categorias" aria-busy={carregando}>
        {carregando && !lista ? (
          <p className="publish-loading">Carregando categorias…</p>
        ) : itens.length === 0 ? (
          <p className="publish-loading">Nenhuma categoria encontrada.</p>
        ) : (
          <ul className="cat-list">
            {itens.map((categoria) => (
              <li key={categoria.id} className="cat-item">
                <div className="cat-item-main">
                  <div className="cat-item-title">
                    <h2>{categoria.nome}</h2>
                    <span
                      className={
                        categoria.status === 'ATIVA'
                          ? 'cat-badge cat-badge--ativa'
                          : 'cat-badge cat-badge--inativa'
                      }
                    >
                      {categoria.status === 'ATIVA' ? 'Ativa' : 'Inativa'}
                    </span>
                  </div>
                  <p>{categoria.descricao ?? 'Sem descrição.'}</p>
                  <small>Atualizada em {formatarData(categoria.atualizado_em)}</small>
                </div>
                <button
                  type="button"
                  className="secondary-button"
                  aria-label={`Editar ${categoria.nome}`}
                  onClick={() => {
                    setAviso('')
                    setPainel({ modo: 'editar', categoria })
                  }}
                >
                  Editar
                </button>
              </li>
            ))}
          </ul>
        )}

        {total > 0 && (
          <nav className="cat-pagination" aria-label="Paginação">
            <span>
              {primeiro}–{ultimo} de {total}
            </span>
            <div>
              <button
                type="button"
                className="secondary-button"
                disabled={offset === 0 || carregando}
                onClick={() => setOffset(Math.max(0, offset - POR_PAGINA))}
              >
                Anterior
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={offset + POR_PAGINA >= total || carregando}
                onClick={() => setOffset(offset + POR_PAGINA)}
              >
                Próxima
              </button>
            </div>
          </nav>
        )}
      </section>
    </main>
  )
}

interface CategoriaFormProps {
  categoria?: Categoria
  aoConcluir: (mensagem: string) => void
  aoCancelar: () => void
}

function CategoriaForm({ categoria, aoConcluir, aoCancelar }: CategoriaFormProps) {
  const [nome, setNome] = useState(categoria?.nome ?? '')
  const [descricao, setDescricao] = useState(categoria?.descricao ?? '')
  const [status, setStatus] = useState<CategoriaStatus>(categoria?.status ?? 'ATIVA')
  const [erros, setErros] = useState<ErrosCategoria>({})
  const [enviando, setEnviando] = useState(false)

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (enviando) return

    const errosValidacao = validarCategoria(nome, descricao)
    if (Object.keys(errosValidacao).length > 0) {
      setErros(errosValidacao)
      return
    }

    const alteracoes = categoria ? camposAlterados(categoria, nome, descricao, status) : undefined
    if (categoria && alteracoes && Object.keys(alteracoes).length === 0) {
      setErros({ geral: 'Altere ao menos um campo antes de salvar.' })
      return
    }

    setErros({})
    setEnviando(true)
    try {
      if (categoria && alteracoes) {
        await atualizarCategoria(categoria.id, alteracoes)
        aoConcluir('Categoria atualizada com sucesso.')
      } else {
        const descricaoLimpa = descricao.trim()
        await criarCategoria({
          nome: normalizarNome(nome),
          ...(descricaoLimpa ? { descricao: descricaoLimpa } : {}),
        })
        aoConcluir('Categoria cadastrada com sucesso.')
      }
    } catch (erro) {
      if (erro instanceof ApiError && erro.status === 409) {
        setErros({ nome: erro.message })
      } else {
        setErros({ geral: mensagemApiErro(erro, 'Não foi possível salvar a categoria.') })
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={enviar} noValidate aria-busy={enviando}>
      <h2 className="cat-form-title">{categoria ? 'Editar categoria' : 'Nova categoria'}</h2>

      {erros.geral && (
        <div className="publish-alert" role="alert">
          {erros.geral}
        </div>
      )}

      <div className="cat-field">
        <label className="publish-field">
          <span>Nome</span>
          <input
            value={nome}
            maxLength={NOME_MAXIMO}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Ex.: Tijolos e blocos"
            aria-invalid={Boolean(erros.nome)}
            aria-describedby={erros.nome ? 'cat-erro-nome' : undefined}
          />
        </label>
        {erros.nome && (
          <small id="cat-erro-nome" className="publish-field-error">
            {erros.nome}
          </small>
        )}
      </div>

      <div className="cat-field">
        <label className="publish-field">
          <span>Descrição (opcional)</span>
          <textarea
            value={descricao}
            maxLength={DESCRICAO_MAXIMA}
            rows={3}
            onChange={(e) => setDescricao(e.target.value)}
            placeholder="Explique quais materiais pertencem a esta categoria."
            aria-invalid={Boolean(erros.descricao)}
            aria-describedby={erros.descricao ? 'cat-erro-descricao' : undefined}
          />
        </label>
        {erros.descricao && (
          <small id="cat-erro-descricao" className="publish-field-error">
            {erros.descricao}
          </small>
        )}
      </div>

      {categoria && (
        <label className="publish-field">
          <span>Status</span>
          <select value={status} onChange={(e) => setStatus(e.target.value as CategoriaStatus)}>
            <option value="ATIVA">Ativa</option>
            <option value="INATIVA">Inativa</option>
          </select>
        </label>
      )}
      {categoria && (
        <p className="section-hint cat-hint">
          Categorias inativas não podem ser usadas em novos anúncios, mas os anúncios existentes não
          são afetados.
        </p>
      )}

      <div className="publish-actions">
        <button type="button" className="secondary-button" onClick={aoCancelar} disabled={enviando}>
          Cancelar
        </button>
        <button type="submit" className="publish-button" disabled={enviando}>
          {enviando ? (
            <>
              <span className="spinner" /> Salvando…
            </>
          ) : categoria ? (
            'Salvar alterações'
          ) : (
            'Cadastrar categoria'
          )}
        </button>
      </div>
    </form>
  )
}

function formatarData(iso: string): string {
  const data = new Date(iso)
  return Number.isNaN(data.getTime()) ? '—' : data.toLocaleDateString('pt-BR')
}

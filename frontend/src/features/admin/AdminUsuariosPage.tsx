import { useEffect, useState, type FormEvent } from 'react'
import { mensagemApiErro } from '../../lib/api'
import { useAuth } from '../autenticacao/useAuth'
import { alterarStatusUsuario, definirAdministrador, listarUsuariosAdmin } from './adminApi'
import { Paginacao } from './Paginacao'
import { formatarData, ROTULOS_STATUS_USUARIO } from './rotulos'
import type { ListaUsuariosAdmin, UsuarioAdmin, UsuarioStatus } from './types'

const POR_PAGINA = 10

export function AdminUsuariosPage() {
  const { sessao } = useAuth()
  const [status, setStatus] = useState<'' | UsuarioStatus>('')
  const [busca, setBusca] = useState('')
  const [buscaDigitada, setBuscaDigitada] = useState('')
  const [incluirExcluidos, setIncluirExcluidos] = useState(false)
  const [offset, setOffset] = useState(0)
  const [versao, setVersao] = useState(0)
  const [lista, setLista] = useState<ListaUsuariosAdmin | null>(null)
  const [concluida, setConcluida] = useState({ chave: '', erro: '' })
  const [salvandoId, setSalvandoId] = useState('')
  const [aviso, setAviso] = useState({ tipo: '', texto: '' })

  // Identifica a consulta atual; enquanto a última concluída for outra, está carregando.
  const chave = `${status}:${busca}:${incluirExcluidos}:${offset}:${versao}`
  const carregando = concluida.chave !== chave
  const erroLista = carregando ? '' : concluida.erro

  useEffect(() => {
    let ativo = true
    listarUsuariosAdmin({ status, busca, incluirExcluidos, offset, limit: POR_PAGINA })
      .then((resposta) => {
        if (!ativo) return
        setLista(resposta)
        setConcluida({ chave, erro: '' })
      })
      .catch((erro) => {
        if (!ativo) return
        setConcluida({ chave, erro: mensagemApiErro(erro, 'Não foi possível carregar os usuários.') })
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

  async function salvar(usuario: UsuarioAdmin, acao: () => Promise<UsuarioAdmin>, mensagem: string) {
    setSalvandoId(usuario.id)
    setAviso({ tipo: '', texto: '' })
    try {
      await acao()
      setAviso({ tipo: 'sucesso', texto: mensagem })
      setVersao((atual) => atual + 1)
    } catch (erro) {
      setAviso({ tipo: 'erro', texto: mensagemApiErro(erro, 'Não foi possível atualizar o usuário.') })
    } finally {
      setSalvandoId('')
    }
  }

  const itens = lista?.items ?? []

  return (
    <main className="publish-page">
      <header className="publish-heading">
        <span className="step-label">Administração</span>
        <h1>Usuários</h1>
        <p>Consulte contas, altere o status de acesso e gerencie os administradores.</p>
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
            placeholder="Nome ou e-mail"
          />
        </label>
        <label className="publish-field">
          <span>Status</span>
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as '' | UsuarioStatus)
              setOffset(0)
            }}
          >
            <option value="">Todos</option>
            {Object.entries(ROTULOS_STATUS_USUARIO).map(([valor, rotulo]) => (
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

      <section className="publish-card" aria-label="Lista de usuários" aria-busy={carregando}>
        {carregando && !lista ? (
          <p className="publish-loading">Carregando usuários…</p>
        ) : itens.length === 0 ? (
          <p className="publish-loading">Nenhum usuário encontrado.</p>
        ) : (
          <ul className="cat-list">
            {itens.map((usuario) => {
              const proprio = usuario.id === sessao?.usuario.id
              const excluido = usuario.deletado_em !== null
              const bloqueado = proprio || excluido || salvandoId === usuario.id
              return (
                <li key={usuario.id} className="cat-item admin-item">
                  <div className="cat-item-main">
                    <div className="cat-item-title">
                      <h2>{usuario.nome}</h2>
                      <span className={`cat-badge admin-badge--${usuario.status.toLowerCase()}`}>
                        {ROTULOS_STATUS_USUARIO[usuario.status]}
                      </span>
                      {usuario.administrador && (
                        <span className="cat-badge admin-badge--admin">Administrador</span>
                      )}
                      {excluido && <span className="cat-badge admin-badge--excluido">Excluído</span>}
                      {proprio && <span className="cat-badge cat-badge--inativa">Você</span>}
                    </div>
                    <p>
                      {usuario.email}
                      {usuario.telefone ? ` · ${usuario.telefone}` : ''}
                    </p>
                    <small>Cadastrado em {formatarData(usuario.criado_em)}</small>
                  </div>

                  <div className="admin-actions">
                    <label className="publish-field admin-status-select">
                      <span>Status</span>
                      <select
                        aria-label={`Status de ${usuario.nome}`}
                        value={usuario.status}
                        disabled={bloqueado}
                        onChange={(e) => {
                          const novo = e.target.value as UsuarioStatus
                          salvar(
                            usuario,
                            () => alterarStatusUsuario(usuario.id, novo),
                            `Status de ${usuario.nome} alterado para ${ROTULOS_STATUS_USUARIO[novo].toLowerCase()}.`,
                          )
                        }}
                      >
                        {Object.entries(ROTULOS_STATUS_USUARIO).map(([valor, rotulo]) => (
                          <option key={valor} value={valor}>
                            {rotulo}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={bloqueado || (!usuario.administrador && usuario.status !== 'ATIVO')}
                      onClick={() =>
                        salvar(
                          usuario,
                          () => definirAdministrador(usuario.id, !usuario.administrador),
                          usuario.administrador
                            ? `${usuario.nome} não é mais administrador.`
                            : `${usuario.nome} agora é administrador.`,
                        )
                      }
                    >
                      {usuario.administrador ? 'Remover admin' : 'Tornar admin'}
                    </button>
                  </div>
                </li>
              )
            })}
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

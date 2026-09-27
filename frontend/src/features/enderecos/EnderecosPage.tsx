import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { CampoConta } from '../../components/CampoConta'
import { ApiError } from '../../lib/api'
import { atualizarEndereco, listarMeusEnderecos } from './enderecoApi'
import type { Endereco, EnderecoForm, ErrosEndereco } from './types'
import { UFS, validarEndereco } from './validacaoEndereco'

export function EnderecosPage() {
  const [enderecos, setEnderecos] = useState<Endereco[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')
  const [editando, setEditando] = useState<Endereco | null>(null)
  const [tentativa, setTentativa] = useState(0)

  useEffect(() => {
    let ativo = true
    listarMeusEnderecos(offset)
      .then((resposta) => {
        if (!ativo) return
        setEnderecos(resposta.items)
        setTotal(resposta.total)
      })
      .catch((falha: unknown) => {
        if (ativo)
          setErro(
            falha instanceof ApiError
              ? falha.message
              : 'Não foi possível carregar os endereços.',
          )
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [offset, tentativa])

  return (
    <main className="profile-page">
      <Link to="/home" className="back-button">
        ← Voltar para a home
      </Link>
      <nav className="account-nav" aria-label="Minha conta">
        <Link to="/perfil">Meu perfil</Link>
        <Link to="/perfil/enderecos" aria-current="page">
          Meus endereços
        </Link>
      </nav>
      <header className="account-heading">
        <span className="step-label">Minha conta</span>
        <h1>Meus endereços</h1>
        <p>Visualize e edite os endereços cadastrados na sua conta.</p>
      </header>
      {sucesso && (
        <p className="account-success" role="status">
          {sucesso}
        </p>
      )}
      {editando ? (
        <EditarEndereco
          key={editando.id}
          endereco={editando}
          aoCancelar={() => setEditando(null)}
          aoSalvar={(atualizado) => {
            setEnderecos((atuais) =>
              atuais.map((endereco) =>
                endereco.id === atualizado.id ? atualizado : endereco,
              ),
            )
            setEditando(null)
            setSucesso('Endereço atualizado com sucesso.')
          }}
        />
      ) : carregando ? (
        <p role="status">Carregando endereços...</p>
      ) : erro ? (
        <div className="publish-card">
          <p role="alert">{erro}</p>
          <button
            className="secondary-button"
            type="button"
            onClick={() => {
              setCarregando(true)
              setErro('')
              setTentativa((atual) => atual + 1)
            }}
          >
            Tentar novamente
          </button>
        </div>
      ) : (
        <>
          {enderecos.length === 0 ? (
            <section className="publish-card">
              <h2>Nenhum endereço cadastrado</h2>
              <p>
                Os endereços que você cadastrar ao publicar um anúncio aparecerão aqui
                para consulta e edição.
              </p>
              <Link className="secondary-button" to="/anuncios/novo">
                Publicar anúncio
              </Link>
            </section>
          ) : (
            <div className="account-addresses">
              {enderecos.map((endereco) => (
                <article className="publish-card" key={endereco.id}>
                  <span className="step-label">
                    {endereco.cidade} · {endereco.estado}
                  </span>
                  <h2>
                    {endereco.logradouro}, {endereco.numero}
                  </h2>
                  <p>{endereco.bairro}</p>
                  {endereco.complemento && <p>{endereco.complemento}</p>}
                  <p>CEP {endereco.cep.replace(/(\d{5})(\d{3})/, '$1-$2')}</p>
                  <button
                    className="secondary-button"
                    type="button"
                    aria-label={`Editar endereço: ${endereco.logradouro}, ${endereco.numero}`}
                    onClick={() => {
                      setEditando(endereco)
                      setSucesso('')
                    }}
                  >
                    Editar endereço
                  </button>
                </article>
              ))}
            </div>
          )}
          {total > 10 && (
            <nav className="account-actions" aria-label="Paginação de endereços">
              <button
                type="button"
                className="secondary-button"
                disabled={offset === 0}
                onClick={() => {
                  setCarregando(true)
                  setOffset((atual) => Math.max(0, atual - 10))
                  setSucesso('')
                }}
              >
                Anterior
              </button>
              <span>
                Página {Math.floor(offset / 10) + 1} de {Math.ceil(total / 10)}
              </span>
              <button
                type="button"
                className="secondary-button"
                disabled={offset + 10 >= total}
                onClick={() => {
                  setCarregando(true)
                  setOffset((atual) => atual + 10)
                  setSucesso('')
                }}
              >
                Próxima
              </button>
            </nav>
          )}
        </>
      )}
    </main>
  )
}

function EditarEndereco({
  endereco,
  aoCancelar,
  aoSalvar,
}: {
  endereco: Endereco
  aoCancelar: () => void
  aoSalvar: (endereco: Endereco) => void
}) {
  const [formulario, setFormulario] = useState<EnderecoForm>({
    cep: endereco.cep,
    logradouro: endereco.logradouro,
    numero: endereco.numero,
    complemento: endereco.complemento ?? '',
    bairro: endereco.bairro,
    cidade: endereco.cidade,
    estado: endereco.estado,
  })
  const [erros, setErros] = useState<ErrosEndereco>({})
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  function atualizar(campo: keyof EnderecoForm, valor: string) {
    setFormulario((atual) => ({ ...atual, [campo]: valor }))
    setErros((atual) => ({ ...atual, [campo]: undefined }))
    setErro('')
  }

  async function salvar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (enviando) return
    const novosErros = validarEndereco(formulario)
    setErros(novosErros)
    setErro('')
    if (Object.keys(novosErros).length) return
    setEnviando(true)
    try {
      const atualizado = await atualizarEndereco(endereco.id, {
        cep: formulario.cep.replace(/\D/g, ''),
        estado: formulario.estado.trim().toUpperCase(),
        logradouro: formulario.logradouro.trim(),
        numero: formulario.numero.trim(),
        bairro: formulario.bairro.trim(),
        cidade: formulario.cidade.trim(),
        complemento: formulario.complemento.trim() || null,
      })
      aoSalvar(atualizado)
    } catch (falha) {
      setErro(
        falha instanceof ApiError
          ? falha.message
          : 'Não foi possível salvar o endereço. Tente novamente.',
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section className="publish-card account-address-form">
      <h2>Editar endereço</h2>
      <p>
        Alterações valem para os próximos pedidos. O endereço registrado em pedidos
        anteriores permanece preservado.
      </p>
      <form onSubmit={salvar} noValidate aria-busy={enviando}>
        <fieldset className="account-fields" disabled={enviando}>
          <legend className="account-legend">Dados do endereço</legend>
          <div className="account-form-grid">
            {(
              [
                ['cep', 'CEP', 9, 'postal-code'],
                ['logradouro', 'Logradouro', 150, 'address-line1'],
                ['numero', 'Número', 20, 'off'],
                ['complemento', 'Complemento (opcional)', 100, 'address-line2'],
                ['bairro', 'Bairro', 100, 'off'],
                ['cidade', 'Cidade', 100, 'address-level2'],
              ] as const
            ).map(([campo, label, maxLength, autoComplete]) => (
              <CampoConta
                key={campo}
                id={campo}
                name={campo}
                label={label}
                maxLength={maxLength}
                autoComplete={autoComplete}
                inputMode={campo === 'cep' ? 'numeric' : 'text'}
                required={campo !== 'complemento'}
                value={formulario[campo]}
                erro={erros[campo]}
                onChange={(evento) => atualizar(campo, evento.target.value)}
              />
            ))}
            <div className="field-group">
              <label htmlFor="estado">Estado</label>
              <select
                id="estado"
                name="estado"
                value={formulario.estado}
                required
                autoComplete="address-level1"
                aria-invalid={Boolean(erros.estado)}
                aria-describedby={erros.estado ? 'estado-erro' : undefined}
                onChange={(evento) => atualizar('estado', evento.target.value)}
              >
                <option value="">Selecione</option>
                {UFS.map((uf) => (
                  <option key={uf} value={uf}>
                    {uf}
                  </option>
                ))}
              </select>
              {erros.estado && (
                <p className="field-error" id="estado-erro">
                  {erros.estado}
                </p>
              )}
            </div>
          </div>
          {erro && (
            <p role="alert" className="form-alert">
              {erro}
            </p>
          )}
          <div className="account-actions">
            <button type="submit" className="submit-button">
              {enviando ? 'Salvando...' : 'Salvar endereço'}
            </button>
            <button type="button" className="secondary-button" onClick={aoCancelar}>
              Cancelar
            </button>
          </div>
        </fieldset>
      </form>
    </section>
  )
}

import { useState, type ChangeEvent, type FormEvent } from 'react'
import { ApiError } from '../../lib/api'
import type { CadastroUsuarioForm, CampoCadastro, ErrosCadastro, Usuario } from './types'
import { cadastrarUsuario } from './usuarioApi'
import { validarCadastro } from './validacaoCadastro'

const formularioInicial: CadastroUsuarioForm = {
  nome: '',
  email: '',
  telefone: '',
  senha: '',
  confirmarSenha: '',
}

export function CadastroUsuarioPage() {
  const [formulario, setFormulario] = useState(formularioInicial)
  const [erros, setErros] = useState<ErrosCadastro>({})
  const [erroGeral, setErroGeral] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [usuarioCriado, setUsuarioCriado] = useState<Usuario | null>(null)

  function atualizarCampo(evento: ChangeEvent<HTMLInputElement>) {
    const campo = evento.target.name as CampoCadastro
    const valor = evento.target.value
    setFormulario((atual) => ({ ...atual, [campo]: valor }))
    setErros((atuais) => ({ ...atuais, [campo]: undefined }))
    setErroGeral('')
  }

  async function enviarFormulario(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const novosErros = validarCadastro(formulario)
    setErros(novosErros)
    setErroGeral('')

    if (Object.keys(novosErros).length > 0) {
      return
    }

    setEnviando(true)
    try {
      const telefone = formulario.telefone.trim()
      const usuario = await cadastrarUsuario({
        nome: formulario.nome.trim(),
        email: formulario.email.trim().toLowerCase(),
        senha: formulario.senha,
        ...(telefone ? { telefone } : {}),
      })
      setUsuarioCriado(usuario)
      setFormulario(formularioInicial)
    } catch (erro) {
      setErroGeral(
        erro instanceof ApiError
          ? erro.message
          : 'Ocorreu um erro inesperado. Tente novamente.',
      )
    } finally {
      setEnviando(false)
    }
  }

  function iniciarNovoCadastro() {
    setUsuarioCriado(null)
    setErros({})
    setErroGeral('')
  }

  return (
    <main className="signup-shell">
      <section className="brand-panel" aria-label="Sobre a Obra Circular">
        <Logo />

        <div className="brand-copy">
          <span className="eyebrow">Construir também é reaproveitar</span>
          <h1>Materiais com história. Obras com futuro.</h1>
          <p>
            Compre e venda excedentes de obra com segurança, reduzindo custos e evitando
            desperdícios.
          </p>
        </div>

        <ul className="benefit-list" aria-label="Benefícios da plataforma">
          <li>
            <LeafIcon />
            <span>
              <strong>Economia circular</strong>
              Cada material reaproveitado deixa de virar descarte.
            </span>
          </li>
          <li>
            <ShieldIcon />
            <span>
              <strong>Negociações mais seguras</strong>
              Uma comunidade feita para quem compra, vende e constrói.
            </span>
          </li>
        </ul>

        <p className="brand-footnote">Obra Circular · Menos descarte, mais possibilidades.</p>
      </section>

      <section className="form-panel">
        <div className="mobile-logo">
          <Logo />
        </div>

        <div className="form-card">
          {usuarioCriado ? (
            <CadastroConcluido usuario={usuarioCriado} aoReiniciar={iniciarNovoCadastro} />
          ) : (
            <>
              <header className="form-heading">
                <span className="step-label">Comece por aqui</span>
                <h2>Crie sua conta</h2>
                <p>Leva menos de dois minutos. Você poderá comprar e anunciar materiais.</p>
              </header>

              <form
                className="signup-form"
                onSubmit={enviarFormulario}
                aria-busy={enviando}
                noValidate
              >
                <CampoTexto
                  id="nome"
                  label="Nome completo"
                  name="nome"
                  autoComplete="name"
                  placeholder="Como devemos chamar você?"
                  value={formulario.nome}
                  error={erros.nome}
                  onChange={atualizarCampo}
                  maxLength={150}
                />

                <CampoTexto
                  id="email"
                  label="E-mail"
                  name="email"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  placeholder="voce@exemplo.com"
                  value={formulario.email}
                  error={erros.email}
                  onChange={atualizarCampo}
                />

                <CampoTexto
                  id="telefone"
                  label="Telefone"
                  optional
                  name="telefone"
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  placeholder="(11) 98765-4321"
                  value={formulario.telefone}
                  error={erros.telefone}
                  onChange={atualizarCampo}
                  maxLength={20}
                />

                <div className="password-grid">
                  <CampoTexto
                    id="senha"
                    label="Senha"
                    name="senha"
                    type={mostrarSenha ? 'text' : 'password'}
                    autoComplete="new-password"
                    placeholder="Mínimo de 8 caracteres"
                    value={formulario.senha}
                    error={erros.senha}
                    onChange={atualizarCampo}
                    maxLength={72}
                  />

                  <CampoTexto
                    id="confirmarSenha"
                    label="Confirmar senha"
                    name="confirmarSenha"
                    type={mostrarSenha ? 'text' : 'password'}
                    autoComplete="new-password"
                    placeholder="Digite novamente"
                    value={formulario.confirmarSenha}
                    error={erros.confirmarSenha}
                    onChange={atualizarCampo}
                    maxLength={72}
                  />
                </div>

                <label className="show-password">
                  <input
                    type="checkbox"
                    checked={mostrarSenha}
                    onChange={(evento) => setMostrarSenha(evento.target.checked)}
                  />
                  Mostrar senhas
                </label>

                {erroGeral && (
                  <div className="form-alert" role="alert">
                    <AlertIcon />
                    <span>{erroGeral}</span>
                  </div>
                )}

                <button className="submit-button" type="submit" disabled={enviando}>
                  {enviando ? (
                    <>
                      <span className="spinner" aria-hidden="true" />
                      Criando sua conta...
                    </>
                  ) : (
                    <>
                      Criar minha conta
                      <ArrowIcon />
                    </>
                  )}
                </button>

                <p className="privacy-note">
                  Ao continuar, você concorda em usar a plataforma de forma responsável e
                  manter seus dados atualizados.
                </p>
              </form>
            </>
          )}
        </div>
      </section>
    </main>
  )
}

interface CampoTextoProps {
  id: string
  label: string
  name: CampoCadastro
  value: string
  error?: string
  optional?: boolean
  type?: string
  inputMode?: 'email' | 'tel' | 'text'
  autoComplete?: string
  placeholder?: string
  maxLength?: number
  onChange: (evento: ChangeEvent<HTMLInputElement>) => void
}

function CampoTexto({ label, error, optional, ...inputProps }: CampoTextoProps) {
  const errorId = `${inputProps.id}-error`
  return (
    <div className="field-group">
      <label htmlFor={inputProps.id}>
        {label}
        {optional && <span>Opcional</span>}
      </label>
      <input
        {...inputProps}
        required={!optional}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : undefined}
      />
      {error && (
        <p className="field-error" id={errorId}>
          {error}
        </p>
      )}
    </div>
  )
}

function CadastroConcluido({
  usuario,
  aoReiniciar,
}: {
  usuario: Usuario
  aoReiniciar: () => void
}) {
  return (
    <div className="success-state" role="status">
      <div className="success-icon" aria-hidden="true">
        <CheckIcon />
      </div>
      <span className="step-label">Cadastro concluído</span>
      <h2>Boas-vindas, {usuario.nome.split(' ')[0]}!</h2>
      <p>
        Sua conta foi criada com o e-mail <strong>{usuario.email}</strong>. Agora você já faz
        parte da comunidade Obra Circular.
      </p>
      <button className="submit-button" type="button" onClick={aoReiniciar}>
        Cadastrar outra pessoa
        <ArrowIcon />
      </button>
    </div>
  )
}

function Logo() {
  return (
    <div className="brand-logo" aria-label="Obra Circular">
      <span className="logo-mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span className="logo-type">
        Obra <strong>Circular</strong>
      </span>
    </div>
  )
}

function LeafIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 4.5C12.5 4.5 6 8.1 6 14.1c0 2.9 2.1 5.4 5.4 5.4 5.8 0 8.6-6.4 8.6-15Z" />
      <path d="M4 20c2.5-4.4 6.2-7.5 11.2-9.4" />
    </svg>
  )
}

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 4.8 6v5.2c0 4.7 2.9 8.2 7.2 9.8 4.3-1.6 7.2-5.1 7.2-9.8V6L12 3Z" />
      <path d="m8.8 12.1 2.1 2.1 4.5-4.7" />
    </svg>
  )
}

function AlertIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.8v5.3M12 16.4v.1" />
    </svg>
  )
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h14m-5-5 5 5-5 5" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6.8 12.3 3.3 3.4 7.3-7.5" />
    </svg>
  )
}

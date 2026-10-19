import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { ApiError, mensagemApiErro } from '../../lib/api'
import { forcaDaSenha } from '../usuarios/validacaoCadastro'
import { AuthLayout } from './AuthLayout'
import { redefinirSenha, validarTokenRecuperacao } from './autenticacaoApi'
import { AlertIcon, ArrowIcon, CheckIcon, LockIcon } from './icones'

const TEXTO_FORCA = ['', 'Fraca', 'Média', 'Forte'] as const
const LINK_INVALIDO = 'Este link de redefinição é inválido ou expirou. Solicite um novo link.'

type Etapa = 'validando' | 'invalido' | 'formulario' | 'concluido'

interface ErrosRedefinicao {
  senha?: string
  confirmarSenha?: string
}

interface RedefinirSenhaPageProps {
  token: string | null
  aoIrParaLogin: () => void
  aoSolicitarNovoLink: () => void
}

export function RedefinirSenhaPage({
  token,
  aoIrParaLogin,
  aoSolicitarNovoLink,
}: RedefinirSenhaPageProps) {
  const [etapa, setEtapa] = useState<Etapa>(token ? 'validando' : 'invalido')
  const [motivoInvalido, setMotivoInvalido] = useState(LINK_INVALIDO)
  const [senha, setSenha] = useState('')
  const [confirmarSenha, setConfirmarSenha] = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [erros, setErros] = useState<ErrosRedefinicao>({})
  const [erroGeral, setErroGeral] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    if (!token) return
    let ativo = true
    validarTokenRecuperacao(token)
      .then(() => {
        if (ativo) setEtapa('formulario')
      })
      .catch((erro: unknown) => {
        if (!ativo) return
        setMotivoInvalido(mensagemApiErro(erro, LINK_INVALIDO))
        setEtapa('invalido')
      })
    return () => {
      ativo = false
    }
  }, [token])

  function atualizarSenha(evento: ChangeEvent<HTMLInputElement>) {
    setSenha(evento.target.value)
    setErros((atuais) => ({ ...atuais, senha: undefined }))
    setErroGeral('')
  }

  function atualizarConfirmacao(evento: ChangeEvent<HTMLInputElement>) {
    setConfirmarSenha(evento.target.value)
    setErros((atuais) => ({ ...atuais, confirmarSenha: undefined }))
    setErroGeral('')
  }

  async function enviarFormulario(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const novosErros = validarNovaSenha(senha, confirmarSenha)
    setErros(novosErros)
    setErroGeral('')
    if (Object.keys(novosErros).length > 0 || !token) return

    setEnviando(true)
    try {
      await redefinirSenha(token, senha)
      setEtapa('concluido')
    } catch (erro) {
      // 400 = o link expirou ou já foi usado enquanto a tela estava aberta.
      if (erro instanceof ApiError && erro.status === 400) {
        setMotivoInvalido(erro.message)
        setEtapa('invalido')
      } else {
        setErroGeral(mensagemApiErro(erro, 'Ocorreu um erro inesperado. Tente novamente.'))
      }
    } finally {
      setEnviando(false)
    }
  }

  const forca = forcaDaSenha(senha)

  return (
    <AuthLayout>
      <div className="form-card recuperacao-card">
        {etapa === 'validando' && (
          <div className="success-state recuperacao-status" role="status">
            <span className="spinner recuperacao-spinner" aria-hidden="true" />
            <p>Verificando seu link de redefinição...</p>
          </div>
        )}

        {etapa === 'invalido' && (
          <div className="success-state recuperacao-status" role="alert">
            <div className="success-icon recuperacao-icone-erro" aria-hidden="true">
              <AlertIcon />
            </div>
            <span className="step-label">Link indisponível</span>
            <h2>Não foi possível usar este link</h2>
            <p>{motivoInvalido}</p>
            <button className="submit-button" type="button" onClick={aoSolicitarNovoLink}>
              Solicitar novo link
              <ArrowIcon />
            </button>
            <p className="login-hint recuperacao-reenvio">
              Lembrou a senha?{' '}
              <button type="button" onClick={aoIrParaLogin}>
                Entrar
              </button>
            </p>
          </div>
        )}

        {etapa === 'concluido' && (
          <div className="success-state recuperacao-status" role="status">
            <div className="success-icon" aria-hidden="true">
              <CheckIcon />
            </div>
            <span className="step-label">Tudo certo</span>
            <h2>Senha redefinida</h2>
            <p>Sua nova senha já está valendo. Entre na plataforma usando a nova senha.</p>
            <button className="submit-button" type="button" onClick={aoIrParaLogin}>
              Ir para o login
              <ArrowIcon />
            </button>
          </div>
        )}

        {etapa === 'formulario' && (
          <>
            <header className="form-heading">
              <span className="step-label">Recuperar acesso</span>
              <h2>Crie uma nova senha</h2>
              <p>Escolha uma senha forte, que você não use em outros sites.</p>
            </header>

            <form
              className="recuperacao-form"
              onSubmit={enviarFormulario}
              aria-busy={enviando}
              noValidate
            >
              <CampoSenha
                id="nova-senha"
                label="Nova senha"
                placeholder="Mínimo de 8 caracteres"
                value={senha}
                erro={erros.senha}
                visivel={mostrarSenha}
                onChange={atualizarSenha}
              />

              {senha && (
                <div className="password-strength">
                  <div className="password-strength-bars">
                    {[1, 2, 3].map((nivel) => (
                      <div
                        key={nivel}
                        className={`password-strength-bar ${
                          forca >= nivel ? `password-strength-bar--${forca}` : ''
                        }`}
                      />
                    ))}
                  </div>
                  <span>{TEXTO_FORCA[forca]}</span>
                </div>
              )}

              <CampoSenha
                id="confirmar-nova-senha"
                label="Confirmar nova senha"
                placeholder="Digite novamente"
                value={confirmarSenha}
                erro={erros.confirmarSenha}
                visivel={mostrarSenha}
                onChange={atualizarConfirmacao}
              />

              <div className="check-option">
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={mostrarSenha}
                  aria-label="Mostrar senhas"
                  className={`check-toggle ${mostrarSenha ? 'check-toggle--marcado' : ''}`}
                  onClick={() => setMostrarSenha((atual) => !atual)}
                >
                  <CheckIcon />
                </button>
                <span>Mostrar senhas</span>
              </div>

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
                    Salvando...
                  </>
                ) : (
                  <>
                    Salvar nova senha
                    <ArrowIcon />
                  </>
                )}
              </button>
            </form>
          </>
        )}
      </div>
    </AuthLayout>
  )
}

interface CampoSenhaProps {
  id: string
  label: string
  placeholder: string
  value: string
  erro?: string
  visivel: boolean
  onChange: (evento: ChangeEvent<HTMLInputElement>) => void
}

function CampoSenha({ id, label, placeholder, value, erro, visivel, onChange }: CampoSenhaProps) {
  const erroId = `${id}-error`
  return (
    <div className="field-group">
      <label htmlFor={id}>{label}</label>
      <div className={`field-box ${erro ? 'field-box--erro' : ''}`}>
        <span className="field-icon">
          <LockIcon />
        </span>
        <input
          id={id}
          name={id}
          type={visivel ? 'text' : 'password'}
          autoComplete="new-password"
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          maxLength={72}
          aria-invalid={Boolean(erro)}
          aria-describedby={erro ? erroId : undefined}
          required
        />
      </div>
      {erro && (
        <p className="field-error" id={erroId}>
          {erro}
        </p>
      )}
    </div>
  )
}

function validarNovaSenha(senha: string, confirmarSenha: string): ErrosRedefinicao {
  const erros: ErrosRedefinicao = {}
  if (senha.length < 8) erros.senha = 'A senha deve ter pelo menos 8 caracteres.'
  else if (senha.length > 72) erros.senha = 'A senha deve ter no máximo 72 caracteres.'

  if (!confirmarSenha) erros.confirmarSenha = 'Confirme sua nova senha.'
  else if (confirmarSenha !== senha) erros.confirmarSenha = 'As senhas não coincidem.'
  return erros
}

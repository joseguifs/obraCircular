import { apiRequest } from '../../lib/api'
import type { Usuario } from '../usuarios/types'
import type { LoginPayload, Sessao, TokenResponse } from './types'

const CHAVE_SESSAO = 'obra-circular:sessao'

export async function autenticar(dados: LoginPayload): Promise<Sessao> {
  const tokens = await apiRequest<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
  const usuario = await apiRequest<Usuario>('/auth/me', {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  })
  const sessao: Sessao = {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    expiraEm: Date.now() + tokens.expires_in * 1000,
    usuario,
  }
  salvarSessao(sessao)
  return sessao
}

export function obterSessao(): Sessao | null {
  try {
    const valor = sessionStorage.getItem(CHAVE_SESSAO)
    if (!valor) return null

    const sessao = JSON.parse(valor) as Partial<Sessao>
    if (
      !sessao.accessToken ||
      !sessao.refreshToken ||
      !sessao.expiraEm ||
      sessao.expiraEm <= Date.now() ||
      !sessao.usuario?.id
    ) {
      sessionStorage.removeItem(CHAVE_SESSAO)
      return null
    }
    return sessao as Sessao
  } catch {
    return null
  }
}

export function encerrarSessao() {
  try {
    sessionStorage.removeItem(CHAVE_SESSAO)
  } catch {
    // O encerramento local continua válido mesmo se o armazenamento estiver indisponível.
  }
}

function salvarSessao(sessao: Sessao) {
  try {
    sessionStorage.setItem(CHAVE_SESSAO, JSON.stringify(sessao))
  } catch {
    // A aplicação ainda pode manter a sessão em memória durante esta navegação.
  }
}

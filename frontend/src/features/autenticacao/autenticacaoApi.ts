import { apiRequest } from '../../lib/api'
import type { Usuario } from '../usuarios/types'
import {
  obterSessaoArmazenada,
  removerSessaoArmazenada,
  salvarSessaoArmazenada,
} from './sessaoStorage'
import type { LoginPayload, Sessao, TokenResponse } from './types'

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
  salvarSessaoArmazenada(sessao)
  return sessao
}

export function obterUsuarioAtual(): Promise<Usuario> {
  return apiRequest<Usuario>('/auth/me')
}

export function obterSessao(): Sessao | null {
  return obterSessaoArmazenada()
}

export function encerrarSessao() {
  removerSessaoArmazenada()
}

export async function solicitarRecuperacaoSenha(email: string): Promise<void> {
  await apiRequest<unknown>('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

export async function validarTokenRecuperacao(token: string): Promise<void> {
  await apiRequest<void>('/auth/reset-password/validate', {
    method: 'POST',
    body: JSON.stringify({ token }),
  })
}

export async function redefinirSenha(token: string, novaSenha: string): Promise<void> {
  await apiRequest<void>('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ token, nova_senha: novaSenha }),
  })
}

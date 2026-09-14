import type { Usuario } from '../usuarios/types'

export interface LoginPayload {
  email: string
  senha: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface Sessao {
  accessToken: string
  refreshToken: string
  expiraEm: number
  usuario: Usuario
}

import { createContext } from 'react'
import type { Sessao } from './types'

export interface AuthContextValue {
  sessao: Sessao | null
  iniciarSessao: (sessao: Sessao) => void
  encerrarSessao: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

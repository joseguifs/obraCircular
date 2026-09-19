import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { renovarSessaoAtual } from '../../lib/api'
import { AuthContext, type AuthContextValue } from './authContext'
import {
  obterSessaoArmazenada,
  observarSessao,
  removerSessaoArmazenada,
  salvarSessaoArmazenada,
} from './sessaoStorage'
import type { Sessao } from './types'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [sessao, setSessao] = useState<Sessao | null>(() => obterSessaoArmazenada())

  useEffect(() => observarSessao(setSessao), [])

  useEffect(() => {
    if (!sessao) return

    const tempoRestante = Math.max(0, sessao.expiraEm - Date.now() - 30_000)
    const temporizador = window.setTimeout(async () => {
      try {
        await renovarSessaoAtual()
      } catch {
        removerSessaoArmazenada()
      }
    }, tempoRestante)
    return () => window.clearTimeout(temporizador)
  }, [sessao])

  const valor = useMemo<AuthContextValue>(
    () => ({
      sessao,
      iniciarSessao: salvarSessaoArmazenada,
      encerrarSessao: removerSessaoArmazenada,
    }),
    [sessao],
  )

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}

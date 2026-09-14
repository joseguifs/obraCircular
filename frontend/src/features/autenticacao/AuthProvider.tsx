import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { encerrarSessao as removerSessao, obterSessao } from './autenticacaoApi'
import { AuthContext, type AuthContextValue } from './authContext'
import type { Sessao } from './types'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [sessao, setSessao] = useState<Sessao | null>(() => obterSessao())

  useEffect(() => {
    if (!sessao) return

    const tempoRestante = Math.max(0, sessao.expiraEm - Date.now())
    const temporizador = window.setTimeout(() => {
      removerSessao()
      setSessao(null)
    }, tempoRestante)
    return () => window.clearTimeout(temporizador)
  }, [sessao])

  const valor = useMemo<AuthContextValue>(
    () => ({
      sessao,
      iniciarSessao: setSessao,
      encerrarSessao: () => {
        removerSessao()
        setSessao(null)
      },
    }),
    [sessao],
  )

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}

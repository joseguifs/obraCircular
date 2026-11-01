import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '../features/autenticacao/useAuth'

export function PublicOnlyRoute() {
  const { sessao } = useAuth()
  const localizacao = useLocation()
  const estado = localizacao.state as { origem?: string } | null
  return sessao ? <Navigate to={estado?.origem ?? '/home'} replace /> : <Outlet />
}

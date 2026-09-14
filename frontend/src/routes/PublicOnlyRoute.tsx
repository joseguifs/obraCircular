import { Navigate, Outlet } from 'react-router'
import { useAuth } from '../features/autenticacao/useAuth'

export function PublicOnlyRoute() {
  const { sessao } = useAuth()
  return sessao ? <Navigate to="/home" replace /> : <Outlet />
}

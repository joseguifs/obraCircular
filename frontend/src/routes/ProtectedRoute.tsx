import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '../features/autenticacao/useAuth'

export function ProtectedRoute() {
  const { sessao } = useAuth()
  const localizacao = useLocation()

  if (!sessao) {
    return <Navigate to="/login" replace state={{ origem: localizacao.pathname }} />
  }

  return <Outlet />
}

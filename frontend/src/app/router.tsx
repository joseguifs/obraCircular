import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router'
import { AdminAnunciosPage } from '../features/admin/AdminAnunciosPage'
import { AdminLayout } from '../features/admin/AdminLayout'
import { AdminResumoPage } from '../features/admin/AdminResumoPage'
import { AdminUsuariosPage } from '../features/admin/AdminUsuariosPage'
import { LoginPage } from '../features/autenticacao/LoginPage'
import { AnuncioDetalhePage } from '../features/anuncios/AnuncioDetalhePage'
import { AnuncioPublicadoPage } from '../features/anuncios/AnuncioPublicadoPage'
import { PublicarAnuncioPage } from '../features/anuncios/PublicarAnuncioPage'
import { CategoriasPage } from '../features/categorias/CategoriasPage'
import type { Sessao } from '../features/autenticacao/types'
import { useAuth } from '../features/autenticacao/useAuth'
import { EnderecosPage } from '../features/enderecos/EnderecosPage'
import { HomePage } from '../features/home/HomePage'
import { NotFoundPage } from '../features/not-found/NotFoundPage'
import { CadastroUsuarioPage } from '../features/usuarios/CadastroUsuarioPage'
import { PerfilPage } from '../features/usuarios/PerfilPage'
import { MarketplaceLayout } from '../layouts/MarketplaceLayout'
import { AdminRoute } from '../routes/AdminRoute'
import { ProtectedRoute } from '../routes/ProtectedRoute'
import { PublicOnlyRoute } from '../routes/PublicOnlyRoute'

export function AppRouter() {
  return (
    <>
      <AtualizarTitulo />
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/cadastro" element={<CadastroRoute />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route element={<MarketplaceLayout />}>
            <Route index element={<Navigate to="/home" replace />} />
            <Route path="/home" element={<HomePage />} />
            <Route path="/perfil" element={<PerfilPage />} />
            <Route path="/perfil/enderecos" element={<EnderecosPage />} />
            <Route path="/anuncios/novo" element={<PublicarAnuncioPage />} />
            <Route path="/anuncios/:anuncioId/publicado" element={<AnuncioPublicadoPage />} />
            <Route path="/anuncios/:anuncioId" element={<AnuncioDetalhePage />} />
            <Route path="/categorias" element={<Navigate to="/admin/categorias" replace />} />

            <Route element={<AdminRoute />}>
              <Route path="/admin" element={<AdminLayout />}>
                <Route index element={<AdminResumoPage />} />
                <Route path="anuncios" element={<AdminAnunciosPage />} />
                <Route path="usuarios" element={<AdminUsuariosPage />} />
                <Route path="categorias" element={<CategoriasPage />} />
              </Route>
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </>
  )
}

function LoginRoute() {
  const { iniciarSessao } = useAuth()
  const navegar = useNavigate()
  const localizacao = useLocation()
  const estado = localizacao.state as { origem?: string } | null

  function concluirLogin(sessao: Sessao) {
    iniciarSessao(sessao)
    navegar(estado?.origem ?? '/home', { replace: true })
  }

  return (
    <LoginPage
      aoAutenticar={concluirLogin}
      aoCadastrar={() => navegar('/cadastro')}
    />
  )
}

function CadastroRoute() {
  const navegar = useNavigate()
  return <CadastroUsuarioPage aoEntrar={() => navegar('/login')} />
}

function AtualizarTitulo() {
  const { pathname } = useLocation()

  useEffect(() => {
    if (pathname === '/login') document.title = 'Entrar | Obra Circular'
    else if (pathname === '/cadastro') document.title = 'Crie sua conta | Obra Circular'
    else if (pathname === '/home' || pathname === '/') document.title = 'Início | Obra Circular'
    else if (pathname === '/perfil') document.title = 'Meu perfil | Obra Circular'
    else if (pathname === '/perfil/enderecos') document.title = 'Meus endereços | Obra Circular'
    else if (pathname === '/admin') document.title = 'Administração | Obra Circular'
    else if (pathname === '/admin/anuncios') document.title = 'Anúncios · Administração | Obra Circular'
    else if (pathname === '/admin/usuarios') document.title = 'Usuários · Administração | Obra Circular'
    else if (pathname === '/admin/categorias' || pathname === '/categorias')
      document.title = 'Categorias · Administração | Obra Circular'
    else if (pathname === '/anuncios/novo') document.title = 'Publicar anúncio | Obra Circular'
    else if (/^\/anuncios\/[^/]+\/publicado$/.test(pathname)) document.title = 'Anúncio publicado | Obra Circular'
    else if (/^\/anuncios\/[^/]+$/.test(pathname)) document.title = 'Anúncio | Obra Circular'
    else document.title = 'Página não encontrada | Obra Circular'
  }, [pathname])

  return null
}

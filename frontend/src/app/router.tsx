import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate, useSearchParams } from 'react-router'
import { AdminAnunciosPage } from '../features/admin/AdminAnunciosPage'
import { AdminContestacoesPage } from '../features/admin/AdminContestacoesPage'
import { AdminLayout } from '../features/admin/AdminLayout'
import { AdminResumoPage } from '../features/admin/AdminResumoPage'
import { AdminUsuariosPage } from '../features/admin/AdminUsuariosPage'
import { AdminRepassesPage } from '../features/admin/AdminRepassesPage'
import { EsqueciSenhaPage } from '../features/autenticacao/EsqueciSenhaPage'
import { LoginPage } from '../features/autenticacao/LoginPage'
import { RedefinirSenhaPage } from '../features/autenticacao/RedefinirSenhaPage'
import { AnuncioDetalhePage } from '../features/anuncios/AnuncioDetalhePage'
import { AnuncioPublicadoPage } from '../features/anuncios/AnuncioPublicadoPage'
import { MeusAnunciosPage } from '../features/anuncios/MeusAnunciosPage'
import { PublicarAnuncioPage } from '../features/anuncios/PublicarAnuncioPage'
import { CategoriasPage } from '../features/categorias/CategoriasPage'
import type { Sessao } from '../features/autenticacao/types'
import { useAuth } from '../features/autenticacao/useAuth'
import { EnderecosPage } from '../features/enderecos/EnderecosPage'
import { HomePage } from '../features/home/HomePage'
import { ContaMercadoPagoPage } from '../features/pagamentos/ContaMercadoPagoPage'
import { ContestacaoPage } from '../features/pagamentos/ContestacaoPage'
import { ContestacaoTestePage } from '../features/pagamentos/ContestacaoTestePage'
import { PagamentoRetornoPage } from '../features/pagamentos/PagamentoRetornoPage'
import { PedidosPage } from '../features/pagamentos/PedidosPage'
import { VendasPage } from '../features/pagamentos/VendasPage'
import { NotFoundPage } from '../features/not-found/NotFoundPage'
import { MinhasPerguntasPage } from '../features/perguntas/MinhasPerguntasPage'
import { CadastroUsuarioPage } from '../features/usuarios/CadastroUsuarioPage'
import type { Usuario } from '../features/usuarios/types'
import { PerfilPage } from '../features/usuarios/PerfilPage'
import { MarketplaceLayout } from '../layouts/MarketplaceLayout'
import { AdminRoute } from '../routes/AdminRoute'
import { ProtectedRoute } from '../routes/ProtectedRoute'
import { PublicOnlyRoute } from '../routes/PublicOnlyRoute'

/** Estado de navegação aceito pela rota /login. */
interface EstadoLogin {
  origem?: string
  emailCadastrado?: string
}

export function AppRouter() {
  return (
    <>
      <AtualizarTitulo />
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/cadastro" element={<CadastroRoute />} />
          <Route path="/esqueci-senha" element={<EsqueciSenhaRoute />} />
        </Route>

        {/* Fora do PublicOnlyRoute: o link do e-mail deve abrir mesmo com uma sessão ativa. */}
        <Route path="/redefinir-senha" element={<RedefinirSenhaRoute />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<MarketplaceLayout />}>
            <Route index element={<Navigate to="/home" replace />} />
            <Route path="/home" element={<HomePage />} />
            <Route path="/perfil" element={<PerfilPage />} />
            <Route path="/perfil/enderecos" element={<EnderecosPage />} />
            <Route path="/perfil/mercado-pago" element={<ContaMercadoPagoPage />} />
            <Route path="/pagamento/retorno" element={<PagamentoRetornoPage />} />
            <Route path="/pedidos" element={<PedidosPage />} />
            <Route path="/vendas" element={<VendasPage />} />
            <Route path="/pedidos/:pedidoId" element={<PagamentoRetornoPage />} />
            <Route path="/pedidos/:pedidoId/contestacoes" element={<ContestacaoPage />} />
            {import.meta.env.DEV && <Route path="/testes/contestacao" element={<ContestacaoTestePage />} />}
            <Route path="/anuncios/novo" element={<PublicarAnuncioPage />} />
            <Route path="/anuncios/meus" element={<MeusAnunciosPage />} />
            <Route path="/anuncios/:anuncioId/publicado" element={<AnuncioPublicadoPage />} />
            <Route path="/anuncios/:anuncioId" element={<AnuncioDetalhePage />} />
            <Route path="/perguntas" element={<MinhasPerguntasPage />} />
            <Route path="/categorias" element={<Navigate to="/admin/categorias" replace />} />

            <Route element={<AdminRoute />}>
              <Route path="/admin" element={<AdminLayout />}>
                <Route index element={<AdminResumoPage />} />
                <Route path="anuncios" element={<AdminAnunciosPage />} />
                <Route path="contestacoes" element={<AdminContestacoesPage />} />
                <Route path="usuarios" element={<AdminUsuariosPage />} />
                <Route path="categorias" element={<CategoriasPage />} />
                <Route path="repasses" element={<AdminRepassesPage />} />
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
  const estado = localizacao.state as EstadoLogin | null

  function concluirLogin(sessao: Sessao) {
    iniciarSessao(sessao)
    navegar(estado?.origem ?? '/home', { replace: true })
  }

  return (
    <LoginPage
      emailInicial={estado?.emailCadastrado}
      aviso={
        estado?.emailCadastrado
          ? 'Conta criada com sucesso! Entre com seu e-mail e senha para continuar.'
          : undefined
      }
      aoAutenticar={concluirLogin}
      aoCadastrar={() => navegar('/cadastro')}
      aoRecuperarSenha={() => navegar('/esqueci-senha')}
    />
  )
}

function CadastroRoute() {
  const navegar = useNavigate()

  function concluirCadastro(usuario: Usuario) {
    const estado: EstadoLogin = { emailCadastrado: usuario.email }
    // replace: voltar no navegador não deve reabrir o formulário já enviado.
    navegar('/login', { replace: true, state: estado })
  }

  return (
    <CadastroUsuarioPage aoEntrar={() => navegar('/login')} aoCadastrar={concluirCadastro} />
  )
}

function EsqueciSenhaRoute() {
  const navegar = useNavigate()
  return <EsqueciSenhaPage aoVoltarParaLogin={() => navegar('/login')} />
}

function RedefinirSenhaRoute() {
  const navegar = useNavigate()
  const [parametros] = useSearchParams()
  return (
    <RedefinirSenhaPage
      token={parametros.get('token')}
      aoIrParaLogin={() => navegar('/login', { replace: true })}
      aoSolicitarNovoLink={() => navegar('/esqueci-senha', { replace: true })}
    />
  )
}

function AtualizarTitulo() {
  const { pathname } = useLocation()

  useEffect(() => {
    if (pathname === '/login') document.title = 'Entrar | Obra Circular'
    else if (pathname === '/cadastro') document.title = 'Crie sua conta | Obra Circular'
    else if (pathname === '/esqueci-senha') document.title = 'Recuperar senha | Obra Circular'
    else if (pathname === '/redefinir-senha') document.title = 'Redefinir senha | Obra Circular'
    else if (pathname === '/home' || pathname === '/') document.title = 'Início | Obra Circular'
    else if (pathname === '/perfil') document.title = 'Meu perfil | Obra Circular'
    else if (pathname === '/perfil/enderecos') document.title = 'Meus endereços | Obra Circular'
    else if (pathname === '/admin') document.title = 'Administração | Obra Circular'
    else if (pathname === '/admin/anuncios') document.title = 'Anúncios · Administração | Obra Circular'
    else if (pathname === '/admin/usuarios') document.title = 'Usuários · Administração | Obra Circular'
    else if (pathname === '/admin/contestacoes') document.title = 'Contestações · Administração | Obra Circular'
    else if (pathname === '/admin/repasses') document.title = 'Repasses · Administração | Obra Circular'
    else if (pathname === '/admin/categorias' || pathname === '/categorias')
      document.title = 'Categorias · Administração | Obra Circular'
    else if (pathname === '/perfil/mercado-pago') document.title = 'Mercado Pago | Obra Circular'
    else if (pathname === '/pagamento/retorno') document.title = 'Pagamento | Obra Circular'
    else if (pathname === '/pedidos') document.title = 'Meus pedidos | Obra Circular'
    else if (pathname === '/vendas') document.title = 'Minhas vendas | Obra Circular'
    else if (pathname === '/perguntas') document.title = 'Perguntas | Obra Circular'
    else if (pathname === '/testes/contestacao') document.title = 'Testar contestação | Obra Circular'
    else if (/^\/pedidos\/[^/]+\/contestacoes$/.test(pathname)) document.title = 'Contestação do pedido | Obra Circular'
    else if (pathname.startsWith('/pedidos/')) document.title = 'Pedido | Obra Circular'
    else if (pathname === '/anuncios/novo') document.title = 'Publicar anúncio | Obra Circular'
    else if (pathname === '/anuncios/meus') document.title = 'Meus anúncios | Obra Circular'
    else if (/^\/anuncios\/[^/]+\/publicado$/.test(pathname)) document.title = 'Anúncio publicado | Obra Circular'
    else if (/^\/anuncios\/[^/]+$/.test(pathname)) document.title = 'Anúncio | Obra Circular'
    else document.title = 'Página não encontrada | Obra Circular'
  }, [pathname])

  return null
}

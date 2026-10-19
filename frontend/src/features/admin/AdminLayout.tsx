import { NavLink, Outlet } from 'react-router'

const SECOES = [
  { para: '/admin', rotulo: 'Visão geral', exato: true },
  { para: '/admin/anuncios', rotulo: 'Anúncios', exato: false },
  { para: '/admin/usuarios', rotulo: 'Usuários', exato: false },
  { para: '/admin/categorias', rotulo: 'Categorias', exato: false },
]

export function AdminLayout() {
  return (
    <>
      <nav className="admin-tabs" aria-label="Seções da administração">
        {SECOES.map((secao) => (
          <NavLink
            key={secao.para}
            to={secao.para}
            end={secao.exato}
            className={({ isActive }) => (isActive ? 'admin-tab admin-tab--ativa' : 'admin-tab')}
          >
            {secao.rotulo}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </>
  )
}

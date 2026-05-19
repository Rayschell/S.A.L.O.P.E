import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navClass = ({ isActive }) =>
    `px-3 py-2 rounded text-sm font-medium transition-colors ${
      isActive
        ? 'bg-blue-700 text-white'
        : 'text-blue-100 hover:bg-blue-600 hover:text-white'
    }`

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      {/* Navbar */}
      <nav className="bg-blue-800 text-white shadow">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-14">
          <Link to="/" className="font-bold text-lg tracking-wide">
            🍺 S.A.L.O.P.E
          </Link>
          <div className="flex items-center gap-2">
            <NavLink to="/events" className={navClass}>
              Événements
            </NavLink>
            {user?.roles?.includes('bureau') && (
              <NavLink to="/members" className={navClass}>
                Membres
              </NavLink>
            )}
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-blue-200">
              {user?.prenom} {user?.nom}
            </span>
            <button
              onClick={handleLogout}
              className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm"
            >
              Déconnexion
            </button>
          </div>
        </div>
      </nav>

      {/* Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}

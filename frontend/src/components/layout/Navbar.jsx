import { useState, useRef, useEffect } from 'react'
import { IconMenu2, IconSun, IconMoon, IconLogout, IconUser } from '@tabler/icons-react'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { useTheme } from '../../contexts/ThemeContext.jsx'

export default function Navbar({ onToggleSidebar }) {
  const { user, logout } = useAuth()
  const { theme, toggle: toggleTheme } = useTheme()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const menuRef = useRef(null)

  const initials = user
    ? `${(user.prenom || user.nom || '?')[0]}${user.nom ? user.nom[0] : ''}`.toUpperCase()
    : '?'

  // Ferme le menu si clic extérieur
  useEffect(() => {
    if (!userMenuOpen) return
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setUserMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [userMenuOpen])

  return (
    <nav
      style={{
        height: 56,
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border)',
        padding: '0 16px 0 12px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gridColumn: '1 / -1',
      }}
    >
      {/* Logo + toggle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button
          onClick={onToggleSidebar}
          style={iconBtnStyle}
          title="Masquer / afficher la barre latérale"
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-high)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <IconMenu2 size={15} stroke={1.5} />
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <img src="/lateb_logo.svg" alt="Logo" style={{ width: 42, height: 42, flexShrink: 0 }} />
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
            S.A.L.O.P.E
          </span>
        </div>
      </div>

      {/* Droite : theme + avatar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <button
          onClick={toggleTheme}
          style={iconBtnStyle}
          title={theme === 'dark' ? 'Passer en mode clair' : 'Passer en mode sombre'}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-high)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          {theme === 'dark' ? <IconSun size={16} stroke={1.5} /> : <IconMoon size={16} stroke={1.5} />}
        </button>

        {/* Avatar cliquable */}
        <div ref={menuRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setUserMenuOpen((v) => !v)}
            title={user?.email || ''}
            style={{
              width: 30, height: 30, borderRadius: '50%',
              background: userMenuOpen ? 'var(--accent)' : 'var(--bg-high)',
              border: userMenuOpen ? '2px solid var(--accent)' : '2px solid transparent',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', transition: 'background 150ms ease, border-color 150ms ease',
              fontSize: 11, fontWeight: 600,
              color: userMenuOpen ? '#fff' : 'var(--text-secondary)',
              fontFamily: "'DM Mono', monospace",
            }}
            onMouseEnter={(e) => { if (!userMenuOpen) e.currentTarget.style.background = 'var(--border-mid)' }}
            onMouseLeave={(e) => { if (!userMenuOpen) e.currentTarget.style.background = 'var(--bg-high)' }}
          >
            {initials.length > 1 ? initials : <IconUser size={13} stroke={1.5} />}
          </button>

          {userMenuOpen && (
            <div
              style={{
                position: 'absolute', top: 'calc(100% + 8px)', right: 0,
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-mid)',
                borderRadius: 'var(--radius-md)',
                boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                minWidth: 200, zIndex: 1000,
                animation: 'scale-in 120ms ease',
                transformOrigin: 'top right',
                overflow: 'hidden',
              }}
            >
              {/* Info user */}
              <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
                <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                  {user?.prenom} {user?.nom}
                </p>
                {user?.email && (
                  <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, fontFamily: 'DM Mono, monospace' }}>
                    {user.email}
                  </p>
                )}
                {user?.roles?.includes('bureau') && (
                  <span style={{
                    display: 'inline-block', marginTop: 5,
                    fontSize: 10, fontFamily: 'DM Mono, monospace',
                    color: 'var(--violet)', background: 'var(--violet-soft)',
                    borderRadius: 4, padding: '2px 6px',
                    textTransform: 'uppercase', letterSpacing: '0.05em',
                  }}>
                    Bureau
                  </span>
                )}
              </div>
              {/* Logout */}
              <button
                onClick={() => { setUserMenuOpen(false); logout() }}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 8,
                  padding: '10px 14px', fontSize: 13,
                  color: 'var(--text-secondary)', background: 'transparent',
                  border: 'none', cursor: 'pointer', fontFamily: "'DM Sans', sans-serif",
                  transition: 'background 100ms ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-high)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <IconLogout size={14} stroke={1.5} />
                Déconnexion
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}

const iconBtnStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: 30, height: 30, borderRadius: 6,
  background: 'transparent', border: 'none',
  cursor: 'pointer', color: 'var(--text-muted)',
  transition: 'background 120ms ease',
}

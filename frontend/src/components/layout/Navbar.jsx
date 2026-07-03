import { IconUser, IconMenu2, IconSun, IconMoon } from '@tabler/icons-react'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { useTheme } from '../../contexts/ThemeContext.jsx'

export default function Navbar({ onToggleSidebar }) {
  const { user } = useAuth()
  const { theme, toggle: toggleTheme } = useTheme()

  return (
    <nav
      style={{
        height: 48,
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
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: 28, height: 28, borderRadius: 6,
            background: 'transparent', border: 'none',
            cursor: 'pointer', color: 'var(--text-muted)',
            transition: 'background 120ms ease',
          }}
          title="Masquer / afficher la barre latérale"
          onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-high)'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        >
          <IconMenu2 size={15} stroke={1.5} />
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <img
            src="/lateb_logo.svg"
            alt="Logo"
            style={{ width: 42, height: 42, flexShrink: 0 }}
          />
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
            S.A.L.O.P.E
          </span>
        </div>
      </div>

      {/* Avatar + theme toggle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <button
          onClick={toggleTheme}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: 30, height: 30, borderRadius: 6,
            background: 'transparent', border: 'none',
            cursor: 'pointer', color: 'var(--text-muted)',
            transition: 'background 120ms ease',
          }}
          title={theme === 'dark' ? 'Passer en mode clair' : 'Passer en mode sombre'}
          onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-high)'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        >
          {theme === 'dark' ? <IconSun size={16} stroke={1.5} /> : <IconMoon size={16} stroke={1.5} />}
        </button>
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: 'var(--bg-high)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'default',
          }}
          title={user?.email || ''}
        >
          <IconUser size={13} color="var(--text-secondary)" stroke={1.5} />
        </div>
      </div>
    </nav>
  )
}

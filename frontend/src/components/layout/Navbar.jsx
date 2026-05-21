import { Link, useLocation } from 'react-router-dom'
import { IconGlassFull, IconUser, IconMenu2 } from '@tabler/icons-react'
import { useAuth } from '../../contexts/AuthContext.jsx'

const NAV_LINKS = [
  { to: '/events', label: 'Événements' },
  { to: '/members', label: 'Membres' },
]

export default function Navbar({ onToggleSidebar }) {
  const location = useLocation()
  const { user } = useAuth()

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
          <div
            style={{
              width: 20,
              height: 20,
              background: 'var(--violet)',
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <IconGlassFull size={11} color="#fff" stroke={1.8} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
            S.A.L.O.P.E
          </span>
        </div>
      </div>

      {/* Navigation */}
      <div style={{ display: 'flex', gap: 4 }}>
        {NAV_LINKS.map(({ to, label }) => {
          const active = location.pathname.startsWith(to)
          return (
            <Link
              key={to}
              to={to}
              style={{
                fontSize: 12,
                padding: '5px 12px',
                borderRadius: 6,
                textDecoration: 'none',
                color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                background: active ? 'var(--bg-high)' : 'transparent',
                transition: 'background 120ms ease, color 120ms ease',
              }}
            >
              {label}
            </Link>
          )
        })}
      </div>

      {/* Avatar */}
      <div
        style={{
          width: 26,
          height: 26,
          borderRadius: '50%',
          background: 'var(--bg-high)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'default',
        }}
        title={user?.email || ''}
      >
        <IconUser size={12} color="var(--text-secondary)" stroke={1.5} />
      </div>
    </nav>
  )
}

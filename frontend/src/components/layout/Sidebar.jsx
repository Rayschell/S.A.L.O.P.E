import { Link, useLocation } from 'react-router-dom'
import { IconCalendarEvent, IconUsers, IconLogout } from '@tabler/icons-react'
import { useAuth } from '../../contexts/AuthContext.jsx'

const SECTIONS = [
  {
    label: 'Gestion',
    items: [
      { to: '/events', icon: IconCalendarEvent, label: 'Événements' },
      { to: '/members', icon: IconUsers, label: 'Membres' },
    ],
  },
]

export default function Sidebar() {
  const location = useLocation()
  const { logout } = useAuth()

  return (
    <aside
      style={{
        gridRow: 2,
        gridColumn: 1,
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
        padding: '8px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        overflowY: 'auto',
      }}
    >
      {SECTIONS.map((section) => (
        <div key={section.label}>
          <p
            style={{
              fontSize: 14,
              fontFamily: 'DM Mono, monospace',
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              padding: '4px 8px 4px',
              marginTop: 2,
            }}
          >
            {section.label}
          </p>
          {section.items.map(({ to, icon: Icon, label }) => {
            const active = location.pathname.startsWith(to)
            return (
              <Link
                key={to}
                to={to}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '8px 10px',
                  borderRadius: 6,
                  fontSize: 15,
                  textDecoration: 'none',
                  color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                  background: active ? 'var(--bg-high)' : 'transparent',
                  transition: 'background 120ms ease, color 120ms ease',
                }}
              >
                <Icon size={16} stroke={1.5} />
                {label}
              </Link>
            )
          })}
        </div>
      ))}

      <div style={{ flex: 1 }} />

      <button
        onClick={logout}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '8px 10px',
          borderRadius: 6,
          fontSize: 15,
          background: 'transparent',
          color: 'var(--text-muted)',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
          transition: 'color 120ms ease',
          width: '100%',
          fontFamily: "'DM Sans', sans-serif",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-secondary)' }}
        onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
      >
        <IconLogout size={16} stroke={1.5} />
        Déconnexion
      </button>
    </aside>
  )
}

import { useState, useEffect } from 'react'
import { IconSettings, IconPencil, IconTrash, IconRefresh, IconChevronDown } from '@tabler/icons-react'
import '../../styles/planning.css'

const AVAILABLE_ROLES = [
  { id: 'bureau', label: 'Bureau', color: '#a78bfa' },
  { id: 'staff',  label: 'Staff',  color: '#4ade80' },
]

export default function MemberTable({ members, isBureau, onEdit, onDelete, onResetCounters, onStats, onRoleChange }) {
  const [rolePickerId, setRolePickerId] = useState(null)
  const [rolePickerPos, setRolePickerPos] = useState({ top: 0, left: 0 })
  const [menuId, setMenuId] = useState(null)
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 })

  useEffect(() => {
    const close = () => { setRolePickerId(null); setMenuId(null) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const openRolePicker = (e, m) => {
    e.stopPropagation()
    if (!isBureau) return
    const rect = e.currentTarget.getBoundingClientRect()
    setMenuId(null)
    if (rolePickerId === m.id) { setRolePickerId(null); return }
    setRolePickerPos({ top: rect.bottom + 6, left: rect.left })
    setRolePickerId(m.id)
  }

  const openMenu = (e, m) => {
    e.stopPropagation()
    const rect = e.currentTarget.getBoundingClientRect()
    setRolePickerId(null)
    if (menuId === m.id) { setMenuId(null); return }
    setMenuPos({ top: rect.bottom + 6, left: rect.right - 160 })
    setMenuId(m.id)
  }

  const toggleRole = (member, roleId) => {
    if (roleId === 'staff') return
    const hasRole = member.roles?.includes(roleId)
    const newRoles = hasRole
      ? member.roles.filter((r) => r !== roleId)
      : [...(member.roles || []), roleId]
    onRoleChange(member.id, newRoles)
    setRolePickerId(null)
  }

  const roleMember = members.find((m) => m.id === rolePickerId)
  const menuMember = members.find((m) => m.id === menuId)

  return (
    <>
      <div className="planning-wrapper" style={{ maxWidth: 900 }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="planning-table">
            <thead>
              <tr>
                <th>Nom</th>
                <th style={{ textAlign: 'left' }}>Email</th>
                <th style={{ textAlign: 'left' }}>Rôles</th>
                <th>Stats</th>
                {isBureau && <th style={{ width: 32 }} />}
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id}>
                  <td style={{ textAlign: 'left', fontWeight: 500 }}>
                    {m.prenom} {m.nom}
                  </td>
                  <td style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
                    {m.email || '—'}
                  </td>
                  <td style={{ textAlign: 'left' }}>
                    <button
                      onMouseDown={(e) => openRolePicker(e, m)}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'none', border: 'none', padding: 0, cursor: isBureau ? 'pointer' : 'default' }}
                    >
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {(m.roles || []).map((r) => (
                          <span key={r} style={badgeStyle(r)}>{r === 'staff' ? 'Staff' : 'Bureau'}</span>
                        ))}
                      </div>
                      {isBureau && <IconChevronDown size={12} color="var(--text-muted)" />}
                    </button>
                  </td>
                  <td>
                    <button onClick={() => onStats(m)} style={actionBtn('var(--violet-soft)', 'var(--violet)')}>
                      Voir stats
                    </button>
                  </td>
                  {isBureau && (
                    <td style={{ textAlign: 'center', paddingRight: 8 }}>
                      <button
                        onMouseDown={(e) => openMenu(e, m)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', padding: '2px 4px', borderRadius: 4 }}
                      >
                        <IconSettings size={14} stroke={1.5} />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {roleMember && (
        <div
          onMouseDown={(e) => e.stopPropagation()}
          style={{ position: 'fixed', top: rolePickerPos.top, left: rolePickerPos.left, zIndex: 9999, ...popoverStyle }}
        >
          <div style={{ padding: '6px 12px 4px', fontSize: 11, color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Rôle
          </div>
          {AVAILABLE_ROLES.map((role) => {
            const active = roleMember.roles?.includes(role.id)
            const disabled = role.id === 'staff'
            return (
              <div
                key={role.id}
                onMouseDown={() => toggleRole(roleMember, role.id)}
                style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 12px', cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.45 : 1, borderRadius: 4 }}
                onMouseEnter={(e) => { if (!disabled) e.currentTarget.style.background = 'var(--bg-high)' }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
              >
                <span style={{ width: 12, height: 12, borderRadius: '50%', background: role.color, flexShrink: 0 }} />
                <span style={{ flex: 1, fontSize: 13, color: 'var(--text-primary)' }}>{role.label}</span>
                {active && <span style={{ fontSize: 13, color: role.color, fontWeight: 700 }}>✓</span>}
              </div>
            )
          })}
        </div>
      )}

      {menuMember && (
        <div
          onMouseDown={(e) => e.stopPropagation()}
          style={{ position: 'fixed', top: menuPos.top, left: menuPos.left, zIndex: 9999, ...popoverStyle, minWidth: 160 }}
        >
          <button
            onMouseDown={() => { setMenuId(null); onEdit(menuMember) }}
            style={menuItemStyle}
            onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-high)'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            <IconPencil size={13} stroke={1.5} /> Modifier
          </button>
          <button
            onMouseDown={() => { setMenuId(null); onResetCounters(menuMember.id) }}
            style={menuItemStyle}
            onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-high)'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            <IconRefresh size={13} stroke={1.5} /> Réinit. compteurs
          </button>
          <div style={{ height: 1, background: 'var(--border)', margin: '4px 6px' }} />
          <button
            onMouseDown={() => { setMenuId(null); onDelete(menuMember.id) }}
            style={{ ...menuItemStyle, color: 'var(--red)' }}
            onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-high)'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            <IconTrash size={13} stroke={1.5} /> Supprimer
          </button>
        </div>
      )}
    </>
  )
}

const badgeStyle = (role) => ({
  display: 'inline-flex',
  alignItems: 'center',
  padding: '2px 8px',
  borderRadius: 4,
  fontSize: 11,
  fontFamily: 'DM Mono, monospace',
  color: role === 'bureau' ? '#a78bfa' : '#4ade80',
  background: role === 'bureau' ? '#7c6af71a' : '#22c55e1a',
  border: `1px solid ${role === 'bureau' ? '#7c6af733' : '#22c55e33'}`,
})

const actionBtn = (bg, color) => ({
  padding: '3px 8px',
  fontSize: 11,
  background: bg,
  color,
  border: 'none',
  borderRadius: 4,
  cursor: 'pointer',
  fontFamily: "'DM Sans', sans-serif",
})

const popoverStyle = {
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border-mid)',
  borderRadius: 8,
  boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
  minWidth: 180,
  padding: '4px 0',
}

const menuItemStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  width: '100%',
  textAlign: 'left',
  padding: '7px 12px',
  fontSize: 13,
  color: 'var(--text-primary)',
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  fontFamily: "'DM Sans', sans-serif",
  borderRadius: 4,
}

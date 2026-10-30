import { useState, useEffect } from 'react'
import { IconSettings, IconPencil, IconTrash, IconRefresh, IconChevronDown } from '@tabler/icons-react'
import '../../styles/planning.css'

const AVAILABLE_ROLES = [
  { id: 'bureau', label: 'Bureau', color: '#a78bfa' },
  { id: 'staff',  label: 'Staff',  color: '#4ade80' },
]

const STAT_COLUMNS = [
  { key: 'heures_afterwork', label: 'Aft. (h)' },
  { key: 'heures_soiree', label: 'Soirée (h)' },
  { key: 'heures_total', label: 'Total (h)' },
  { key: 'shifts_respo_bar_cumules', label: 'Respo bar' },
]

export default function MemberTable({ members, isBureau, onEdit, onDelete, onResetCounters, onRoleChange, showStats, selectedId, onSelect }) {
  const [rolePickerId, setRolePickerId] = useState(null)
  const [rolePickerPos, setRolePickerPos] = useState({ top: 0, left: 0 })
  const [menuId, setMenuId] = useState(null)
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 })
  const [sortKey, setSortKey] = useState('nom')
  const [sortDir, setSortDir] = useState('asc')

  useEffect(() => {
    const close = () => { setRolePickerId(null); setMenuId(null) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  // Popovers en position:fixed — basculer au-dessus du bouton quand la place
  // manque sous le viewport (sinon coupés pour les dernières lignes de la table)
  const popoverTop = (rect, estimatedHeight) =>
    rect.bottom + 6 + estimatedHeight > window.innerHeight
      ? Math.max(8, rect.top - 6 - estimatedHeight)
      : rect.bottom + 6

  const openRolePicker = (e, m) => {
    e.stopPropagation()
    if (!isBureau) return
    const rect = e.currentTarget.getBoundingClientRect()
    setMenuId(null)
    if (rolePickerId === m.id) { setRolePickerId(null); return }
    setRolePickerPos({ top: popoverTop(rect, 100), left: rect.left })
    setRolePickerId(m.id)
  }

  const openMenu = (e, m) => {
    e.stopPropagation()
    const rect = e.currentTarget.getBoundingClientRect()
    setRolePickerId(null)
    if (menuId === m.id) { setMenuId(null); return }
    setMenuPos({ top: popoverTop(rect, 118), left: rect.right - 160 })
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

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir(key === 'nom' ? 'asc' : 'desc')
    }
  }

  const sorted = [...members].sort((a, b) => {
    const av = sortKey === 'nom' ? `${a.nom} ${a.prenom}` : (a[sortKey] ?? 0)
    const bv = sortKey === 'nom' ? `${b.nom} ${b.prenom}` : (b[sortKey] ?? 0)
    if (av < bv) return sortDir === 'asc' ? -1 : 1
    if (av > bv) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  const sortableTh = (key, label, align = 'right') => (
    <th
      key={key}
      onClick={() => handleSort(key)}
      style={{
        textAlign: align,
        cursor: 'pointer',
        userSelect: 'none',
        whiteSpace: 'nowrap',
        color: sortKey === key ? 'var(--accent)' : undefined,
      }}
    >
      {label}
      {sortKey === key && <span style={{ marginLeft: 4 }}>{sortDir === 'asc' ? '↑' : '↓'}</span>}
    </th>
  )

  const roleMember = members.find((m) => m.id === rolePickerId)
  const menuMember = members.find((m) => m.id === menuId)

  const maxTotal = Math.max(...members.map((m) => m.heures_total ?? 0), 0.1)

  const zeroDash = <span style={{ color: 'var(--text-muted)', opacity: 0.4 }}>—</span>

  return (
    <>
      <div className="planning-wrapper" style={{ maxWidth: showStats ? 'none' : 900 }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="planning-table member-table">
            <thead>
              <tr>
                {sortableTh('nom', 'Nom', 'left')}
                <th style={{ textAlign: 'left' }}>Rôles</th>
                {showStats && STAT_COLUMNS.map(({ key, label }) => sortableTh(key, label))}
                {isBureau && <th style={{ width: 32 }} />}
              </tr>
            </thead>
            <tbody>
              {sorted.map((m) => {
                const selected = m.id === selectedId
                return (
                  <tr
                    key={m.id}
                    onClick={() => showStats && onSelect?.(m)}
                    className={selected ? 'row-selected' : undefined}
                    style={{ cursor: showStats ? 'pointer' : 'default' }}
                  >
                    <td style={{ textAlign: 'left' }}>
                      <span style={{ fontWeight: 500 }}>
                        {m.prenom} {m.nom}
                      </span>
                      {m.bien_membre && (
                        <span title="Bien membré·e·s" style={{ marginLeft: 6, color: 'var(--green)', fontSize: 12 }}>
                          ✦
                        </span>
                      )}
                      {m.email && (
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                          {m.email}
                        </div>
                      )}
                    </td>
                    <td style={{ textAlign: 'left' }}>
                      <button
                        onMouseDown={(e) => openRolePicker(e, m)}
                        onClick={(e) => e.stopPropagation()}
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
                    {showStats && (
                      <>
                        <td style={numCellStyle}>
                          {(m.heures_afterwork ?? 0) > 0 ? (m.heures_afterwork).toFixed(1) : zeroDash}
                        </td>
                        <td style={numCellStyle}>
                          {(m.heures_soiree ?? 0) > 0 ? (m.heures_soiree).toFixed(1) : zeroDash}
                        </td>
                        <td style={{ ...numCellStyle, minWidth: 96 }}>
                          {(m.heures_total ?? 0) > 0 ? (
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                              <span style={{ color: 'var(--text-primary)' }}>{m.heures_total.toFixed(1)}</span>
                              <div style={{ width: '100%', maxWidth: 72, height: 3, borderRadius: 2, background: 'var(--bg-high)', overflow: 'hidden' }}>
                                <div style={{ width: `${(m.heures_total / maxTotal) * 100}%`, height: '100%', background: 'var(--accent)', borderRadius: 2 }} />
                              </div>
                            </div>
                          ) : zeroDash}
                        </td>
                        <td style={numCellStyle}>
                          {(m.shifts_respo_bar_cumules ?? 0) > 0 ? m.shifts_respo_bar_cumules : zeroDash}
                        </td>
                      </>
                    )}
                    {isBureau && (
                      <td style={{ textAlign: 'center', paddingRight: 8 }}>
                        <button
                          onMouseDown={(e) => openMenu(e, m)}
                          onClick={(e) => e.stopPropagation()}
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', padding: '2px 4px', borderRadius: 4 }}
                        >
                          <IconSettings size={14} stroke={1.5} />
                        </button>
                      </td>
                    )}
                  </tr>
                )
              })}
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
                className={disabled ? undefined : "hover-high"}
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
            className="hover-high"
          >
            <IconPencil size={13} stroke={1.5} /> Modifier
          </button>
          <button
            onMouseDown={() => { setMenuId(null); onResetCounters(menuMember.id) }}
            style={menuItemStyle}
            className="hover-high"
          >
            <IconRefresh size={13} stroke={1.5} /> Réinit. compteurs
          </button>
          <div style={{ height: 1, background: 'var(--border)', margin: '4px 6px' }} />
          <button
            onMouseDown={() => { setMenuId(null); onDelete(menuMember.id) }}
            style={{ ...menuItemStyle, color: 'var(--red)' }}
            className="hover-high"
          >
            <IconTrash size={13} stroke={1.5} /> Supprimer
          </button>
        </div>
      )}
    </>
  )
}

const numCellStyle = {
  textAlign: 'right',
  fontFamily: 'DM Mono, monospace',
  color: 'var(--text-muted)',
  whiteSpace: 'nowrap',
}

const badgeStyle = (role) => ({
  display: 'inline-flex',
  alignItems: 'center',
  padding: '2px 8px',
  borderRadius: 4,
  fontSize: 11,
  fontFamily: 'DM Mono, monospace',
  color: role === 'bureau' ? '#a78bfa' : '#4ade80',
  background: role === 'bureau' ? '#7c6af71a' : '#34c77b1a',
  border: `1px solid ${role === 'bureau' ? '#7c6af733' : '#34c77b33'}`,
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
}

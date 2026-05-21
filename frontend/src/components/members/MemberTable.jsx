import Badge from '../ui/Badge.jsx'
import '../../styles/planning.css'

export default function MemberTable({ members, isBureau, onEdit, onDelete, onResetCounters, onStats }) {
  return (
    <div className="planning-wrapper">
      <div style={{ overflowX: 'auto' }}>
        <table className="planning-table">
          <thead>
            <tr>
              <th>Nom</th>
              <th style={{ textAlign: 'left' }}>Email</th>
              <th style={{ textAlign: 'left' }}>Rôles</th>
              <th>Respo bar</th>
              <th>Stats</th>
              {isBureau && <th>Actions</th>}
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
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {(m.roles || []).map((r) => (
                      <Badge key={r} variant={r === 'bureau' ? 'violet' : 'default'}>
                        {r === 'staff' ? 'Staff' : 'Bureau'}
                      </Badge>
                    ))}
                  </div>
                </td>
                <td style={{ fontFamily: 'DM Mono, monospace', fontSize: 12 }}>
                  {m.shifts_respo_bar_cumules}
                </td>
                <td>
                  <button
                    onClick={() => onStats(m)}
                    style={actionBtn('var(--violet-soft)', 'var(--violet)')}
                  >
                    Voir stats
                  </button>
                </td>
                {isBureau && (
                  <td>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: 6 }}>
                      <button onClick={() => onEdit(m)} style={actionBtn('var(--accent-soft)', 'var(--accent)')}>
                        Modifier
                      </button>
                      <button onClick={() => onResetCounters(m.id)} style={actionBtn('var(--amber-soft)', 'var(--amber)')}>
                        Réinit.
                      </button>
                      <button onClick={() => onDelete(m.id)} style={actionBtn('var(--red-soft)', 'var(--red)')}>
                        Suppr.
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

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

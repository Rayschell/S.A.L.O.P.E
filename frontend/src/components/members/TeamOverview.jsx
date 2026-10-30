const AFTERWORK_COLOR = '#5b7fa6'
const SOIREE_COLOR = '#7c6af7'

// Panneau affiché quand aucun membre n'est sélectionné : l'activité de l'asso en un coup d'œil.
export default function TeamOverview({ members, onSelect }) {
  const totalAfterwork = members.reduce((s, m) => s + (m.heures_afterwork ?? 0), 0)
  const totalSoiree = members.reduce((s, m) => s + (m.heures_soiree ?? 0), 0)
  const total = totalAfterwork + totalSoiree
  const bienMembres = members.filter((m) => m.bien_membre).length

  const top = members
    .filter((m) => (m.heures_total ?? 0) > 0)
    .sort((a, b) => (b.heures_total ?? 0) - (a.heures_total ?? 0))
    .slice(0, 5)
  const maxTop = top[0]?.heures_total || 1

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>Vue d'ensemble</h2>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 3 }}>
          {members.length} membre{members.length > 1 ? 's' : ''} — cliquez sur une ligne pour le détail
        </p>
      </div>

      {/* Totaux */}
      <div style={{ display: 'flex', gap: 10 }}>
        <TotalPill label="Afterwork" value={totalAfterwork} color={AFTERWORK_COLOR} />
        <TotalPill label="Soirée" value={totalSoiree} color={SOIREE_COLOR} />
        <TotalPill label="Total" value={total} color="var(--text-primary)" bold />
      </div>

      {/* Répartition afterwork / soirée */}
      {total > 0 && (
        <div>
          <div style={{ display: 'flex', height: 6, borderRadius: 99, overflow: 'hidden', background: 'var(--bg-high)' }}>
            <div style={{ width: `${(totalAfterwork / total) * 100}%`, background: AFTERWORK_COLOR }} />
            <div style={{ width: `${(totalSoiree / total) * 100}%`, background: SOIREE_COLOR }} />
          </div>
          <div style={{ display: 'flex', gap: 14, marginTop: 8 }}>
            <LegendDot color={AFTERWORK_COLOR} label={`Afterwork ${Math.round((totalAfterwork / total) * 100)}%`} />
            <LegendDot color={SOIREE_COLOR} label={`Soirée ${Math.round((totalSoiree / total) * 100)}%`} />
          </div>
        </div>
      )}

      {/* Bien membré·e·s */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={sectionLabelStyle}>Bien membré·e·s</span>
          <span style={{ fontSize: 12, fontFamily: 'DM Mono, monospace', color: 'var(--text-secondary)' }}>
            {bienMembres} / {members.length}
          </span>
        </div>
        <div style={{ height: 5, background: 'var(--bg-high)', borderRadius: 99, overflow: 'hidden' }}>
          <div
            style={{
              height: '100%',
              width: `${members.length > 0 ? (bienMembres / members.length) * 100 : 0}%`,
              background: 'var(--green)',
              borderRadius: 99,
              transition: 'width 0.4s ease',
            }}
          />
        </div>
      </div>

      {/* Top 5 */}
      <div>
        <p style={{ ...sectionLabelStyle, marginBottom: 10 }}>Les plus actif·ve·s</p>
        {top.length === 0 ? (
          <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Les compteurs se rempliront à la publication des plannings
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {top.map((m) => (
              <button
                key={m.id}
                onClick={() => onSelect(m)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '6px 8px',
                  borderRadius: 6,
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  textAlign: 'left',
                  fontFamily: "'DM Sans', sans-serif",
                  transition: 'background 120ms ease',
                }}
                className="hover-elevated"
              >
                <span style={{ flexShrink: 0, fontSize: 13, color: 'var(--text-primary)', width: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {m.prenom} {m.nom}
                </span>
                <div style={{ flex: 1, height: 4, borderRadius: 2, background: 'var(--bg-high)', overflow: 'hidden' }}>
                  <div style={{ width: `${(m.heures_total / maxTop) * 100}%`, height: '100%', background: 'var(--accent)', borderRadius: 2 }} />
                </div>
                <span style={{ flexShrink: 0, fontSize: 12, fontFamily: 'DM Mono, monospace', color: 'var(--text-secondary)' }}>
                  {m.heures_total.toFixed(1)}h
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

const sectionLabelStyle = {
  fontSize: 12,
  fontWeight: 500,
  color: 'var(--text-secondary)',
}

function TotalPill({ label, value, color, bold }) {
  return (
    <div style={{ flex: 1, background: 'var(--bg-elevated)', borderRadius: 6, padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </span>
      <span style={{ fontSize: 16, fontWeight: bold ? 700 : 500, color, fontFamily: 'DM Mono, monospace', lineHeight: 1.2 }}>
        {value.toFixed(value % 1 === 0 ? 0 : 1)}h
      </span>
    </div>
  )
}

function LegendDot({ color, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
      <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: color, opacity: 0.85 }} />
      {label}
    </div>
  )
}

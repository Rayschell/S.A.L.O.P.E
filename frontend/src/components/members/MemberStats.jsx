export default function MemberStats({ stats, respoBar, maxRespoBar, isMemberBureau, timeline }) {
  if (!stats) return <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Chargement…</p>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {isMemberBureau && respoBar > 0 && (
        <RespoBarHistogram count={respoBar ?? 0} max={maxRespoBar ?? 1} />
      )}
      <Histogram title="Afterwork" entries={stats.afterwork} colorRaw="#2563c4" slotLabels={stats.afterwork_slot_labels ?? {}} />
      <Histogram title="Soirée" entries={stats.soiree} colorRaw="#7c6af7" slotLabels={stats.soiree_slot_labels ?? {}} />
      <Timeline events={timeline} />
    </div>
  )
}

function RespoBarHistogram({ count, max }) {
  const barH = max > 0 ? Math.max(Math.round((count / max) * 100), count > 0 ? 6 : 0) : 0
  const colorRaw = '#f59e0b'

  return (
    <div>
      <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 10 }}>Respo bar</p>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 80 }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 40 }}>
          <div style={{ position: 'relative', width: '100%', height: 64, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
            <div style={{ position: 'absolute', bottom: 0, width: '100%', height: '100%', background: colorRaw, opacity: 0.15, borderRadius: '3px 3px 0 0' }} />
            <div style={{ position: 'absolute', bottom: 0, width: '100%', height: `${barH}%`, background: colorRaw, opacity: 0.85, borderRadius: '3px 3px 0 0' }} />
          </div>
          <span style={{ fontSize: 10, fontFamily: 'DM Mono, monospace', color: 'var(--text-muted)', marginTop: 4 }}>{count}</span>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 14, marginTop: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
          <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: colorRaw, opacity: 0.85 }} />
          Shifts respo bar
        </div>
      </div>
    </div>
  )
}

function Histogram({ title, entries, colorRaw, slotLabels = {} }) {
  if (!entries || entries.length === 0) {
    return (
      <div>
        <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>{title}</p>
        <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>Aucune donnée</p>
      </div>
    )
  }

  const entryMap = Object.fromEntries(entries.map((e) => [e.heure_relative, e]))
  const knownHR = Object.keys(slotLabels).map(Number).sort((a, b) => a - b)
  const allEntries = knownHR.length > 0
    ? knownHR.map((hr) => entryMap[hr] ?? { heure_relative: hr, fois_disponible: 0, fois_staffe: 0 })
    : entries
  const displayEntries = allEntries.filter((e) => e.fois_disponible > 0 || e.fois_staffe > 0)

  const maxStaffe = Math.max(...displayEntries.map((e) => e.fois_staffe), 1)

  return (
    <div>
      <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 10 }}>{title}</p>
      <div style={{ display: 'flex', gap: 6 }}>
        {/* Y-axis */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', alignItems: 'flex-end', height: 64, paddingBottom: 0, flexShrink: 0 }}>
          <span style={{ fontSize: 9, fontFamily: 'DM Mono, monospace', color: 'var(--text-muted)', lineHeight: 1 }}>{maxStaffe}</span>
          <span style={{ fontSize: 9, fontFamily: 'DM Mono, monospace', color: 'var(--text-muted)', lineHeight: 1 }}>0</span>
        </div>
        {/* Bars */}
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, flex: 1 }}>
          {displayEntries.map((e) => {
            const fillH = Math.round((e.fois_staffe / maxStaffe) * 100)

            return (
              <div key={e.heure_relative} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1, minWidth: 0 }}>
                {/* Count label */}
                <span style={{ fontSize: 9, fontFamily: 'DM Mono, monospace', color: fillH > 0 ? colorRaw : 'var(--text-muted)', marginBottom: 2, opacity: fillH > 0 ? 0.9 : 0.5 }}>
                  {e.fois_staffe > 0 ? e.fois_staffe : ''}
                </span>
                <div style={{ position: 'relative', width: '100%', height: 64, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
                  {/* Staffé bar */}
                  {fillH > 0 && (
                    <div
                      style={{
                        position: 'absolute',
                        bottom: 0,
                        width: '100%',
                        height: `${fillH}%`,
                        background: colorRaw,
                        opacity: 0.85,
                        borderRadius: '3px 3px 0 0',
                      }}
                    />
                  )}
                </div>
                <span style={{ fontSize: 10, fontFamily: 'DM Mono, monospace', color: 'var(--text-muted)', marginTop: 4 }}>
                  {slotLabels[e.heure_relative] ?? `H${e.heure_relative}`}
                </span>
              </div>
            )
          })}
        </div>
      </div>

    </div>
  )
}

const fmtTime = (dt) =>
  new Date(dt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })

const fmtDate = (dt) =>
  new Date(dt).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })

function Timeline({ events }) {
  if (!events || events.length === 0) {
    return (
      <div>
        <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>Historique</p>
        <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>Aucun événement publié</p>
      </div>
    )
  }

  return (
    <div>
      <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 10 }}>Historique</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {events.map((ev) => (
          <div
            key={ev.event_id}
            style={{
              padding: '8px 10px',
              background: 'var(--bg-elevated)',
              borderRadius: 6,
              border: '1px solid var(--border)',
              display: 'flex',
              flexDirection: 'column',
              gap: 5,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace', flexShrink: 0 }}>
                  {fmtDate(ev.date)}
                </span>
                <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {ev.nom}
                </span>
                <span style={{
                  fontSize: 10,
                  padding: '1px 6px',
                  borderRadius: 4,
                  flexShrink: 0,
                  fontWeight: 500,
                  background: ev.type === 'afterwork' ? 'rgba(37,99,196,0.15)' : 'rgba(124,106,247,0.15)',
                  color: ev.type === 'afterwork' ? '#2563c4' : '#7c6af7',
                }}>
                  {ev.type}
                </span>
              </div>
              <span style={{ fontSize: 11, fontFamily: 'DM Mono, monospace', color: 'var(--text-secondary)', fontWeight: 600, flexShrink: 0 }}>
                {ev.total_heures}h
              </span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {ev.slots.map((s, i) => (
                <span
                  key={i}
                  style={{
                    fontSize: 10,
                    padding: '2px 7px',
                    borderRadius: 4,
                    background: 'var(--bg-high)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-secondary)',
                    fontFamily: 'DM Mono, monospace',
                  }}
                >
                  {fmtTime(s.heure_debut)}–{fmtTime(s.heure_fin)}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

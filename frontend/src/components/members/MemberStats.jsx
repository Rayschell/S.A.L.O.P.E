export default function MemberStats({ stats, respoBar, maxRespoBar, isMemberBureau, timeline }) {
  if (!stats) return <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Chargement…</p>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <HoursSummary stats={stats} />
      {isMemberBureau && respoBar > 0 && (
        <RespoBarHistogram count={respoBar ?? 0} max={maxRespoBar ?? 1} />
      )}
      <Histogram title="Afterwork" entries={stats.afterwork} colorRaw="#5b7fa6" slotLabels={stats.afterwork_slot_labels ?? {}} />
      <Histogram title="Soirée" entries={stats.soiree} colorRaw="#7c6af7" slotLabels={stats.soiree_slot_labels ?? {}} />
      <Timeline events={timeline} />
    </div>
  )
}

const SEUIL_HEURES = 10

function HoursSummary({ stats }) {
  const afterwork = stats.total_heures_afterwork ?? 0
  const soiree = stats.total_heures_soiree ?? 0
  const cumule = stats.total_heures_cumule ?? 0
  const bienMembre = stats.bien_membre ?? false
  const progress = Math.min(cumule / SEUIL_HEURES, 1)

  return (
    <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', margin: 0 }}>Heures staffé·e·s</p>
        {bienMembre && (
          <span style={{
            fontSize: 10,
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: 99,
            background: 'rgba(251,191,36,0.18)',
            color: '#f59e0b',
            border: '1px solid rgba(251,191,36,0.35)',
            fontFamily: 'DM Mono, monospace',
            letterSpacing: '0.04em',
          }}>
            ✦ Bien membré·e·s
          </span>
        )}
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        <StatPill label="Afterwork" value={afterwork} color="#5b7fa6" />
        <StatPill label="Soirée" value={soiree} color="#7c6af7" />
        <StatPill label="Total" value={cumule} color={bienMembre ? '#f59e0b' : 'var(--text-primary)'} bold />
      </div>

      {/* Progress bar toward Bien membré·e·s */}
      {!bienMembre && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace' }}>
              Vers Bien membré·e·s
            </span>
            <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace' }}>
              {cumule}h / {SEUIL_HEURES}h
            </span>
          </div>
          <div style={{ height: 5, background: 'var(--bg-high)', borderRadius: 99, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${progress * 100}%`, background: '#4ade80', borderRadius: 99, transition: 'width 0.4s ease' }} />
          </div>
        </div>
      )}
    </div>
  )
}

function StatPill({ label, value, color, bold }) {
  return (
    <div style={{ flex: 1, background: 'var(--bg-high)', borderRadius: 6, padding: '6px 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: bold ? 700 : 500, color, fontFamily: 'DM Mono, monospace', lineHeight: 1.2 }}>{value}h</span>
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
        <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>Aucun shift staffé pour l'instant</p>
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
  new Date(dt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', hour12: false })

const fmtDate = (dt) =>
  new Date(dt).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })

function Timeline({ events }) {
  if (!events || events.length === 0) {
    return (
      <div>
        <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>Historique</p>
        <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>Apparaîtra à la première publication d'un planning</p>
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
                  background: ev.type === 'afterwork' ? 'rgba(91, 127, 166,0.15)' : 'rgba(124, 106, 247,0.15)',
                  color: ev.type === 'afterwork' ? '#5b7fa6' : '#7c6af7',
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

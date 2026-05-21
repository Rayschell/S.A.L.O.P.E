export default function MemberStats({ stats }) {
  if (!stats) return <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Chargement…</p>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <Histogram title="Afterwork" entries={stats.afterwork} color="var(--accent)" colorRaw="#2563c4" />
      <Histogram title="Soirée" entries={stats.soiree} color="var(--violet)" colorRaw="#7c6af7" />
    </div>
  )
}

function Histogram({ title, entries, colorRaw }) {
  if (!entries || entries.length === 0) {
    return (
      <div>
        <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>{title}</p>
        <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>Aucune donnée</p>
      </div>
    )
  }

  const maxDispo = Math.max(...entries.map((e) => e.fois_disponible), 1)

  return (
    <div>
      <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 10 }}>{title}</p>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 80 }}>
        {entries.map((e) => {
          const barH = Math.round((e.fois_disponible / maxDispo) * 100)
          const fillH = e.fois_disponible > 0
            ? Math.round((e.fois_staffe / e.fois_disponible) * barH)
            : 0

          return (
            <div key={e.heure_relative} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1, minWidth: 0 }}>
              <div style={{ position: 'relative', width: '100%', height: 64, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
                {/* Dispo background */}
                <div
                  style={{
                    position: 'absolute',
                    bottom: 0,
                    width: '100%',
                    height: `${barH}%`,
                    background: colorRaw,
                    opacity: 0.15,
                    borderRadius: '3px 3px 0 0',
                  }}
                />
                {/* Staffé foreground */}
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
              </div>
              <span style={{ fontSize: 10, fontFamily: 'DM Mono, monospace', color: 'var(--text-muted)', marginTop: 4 }}>
                H{e.heure_relative}
              </span>
            </div>
          )
        })}
      </div>
      <div style={{ display: 'flex', gap: 14, marginTop: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
          <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: colorRaw, opacity: 0.15 }} />
          Disponible
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
          <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: colorRaw, opacity: 0.85 }} />
          Staffé
        </div>
      </div>
    </div>
  )
}

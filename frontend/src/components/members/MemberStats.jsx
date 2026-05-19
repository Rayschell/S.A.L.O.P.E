/**
 * MemberStats — shows two bar chart histograms (afterwork / soirée)
 * X axis: heure_relative (0-based slot index)
 * Each bar has two layers:
 *   - grey background bar = fois_disponible
 *   - coloured foreground bar = fois_staffe
 */
export default function MemberStats({ stats }) {
  if (!stats) return <p className="text-gray-400 text-sm">Chargement…</p>

  return (
    <div className="space-y-6">
      <Histogram title="Afterwork" entries={stats.afterwork} color="#3b82f6" />
      <Histogram title="Soirée" entries={stats.soiree} color="#8b5cf6" />
    </div>
  )
}

function Histogram({ title, entries, color }) {
  if (!entries || entries.length === 0) {
    return (
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-1">{title}</h3>
        <p className="text-xs text-gray-400">Aucune donnée</p>
      </div>
    )
  }

  const maxDispo = Math.max(...entries.map((e) => e.fois_disponible), 1)

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">{title}</h3>
      <div className="flex items-end gap-2 h-32">
        {entries.map((e) => {
          const barHeight = Math.round((e.fois_disponible / maxDispo) * 100)
          const fillHeight = e.fois_disponible > 0
            ? Math.round((e.fois_staffe / e.fois_disponible) * barHeight)
            : 0

          return (
            <div key={e.heure_relative} className="flex flex-col items-center flex-1 min-w-0">
              <div className="relative w-full flex flex-col justify-end" style={{ height: '100px' }}>
                {/* Background bar (fois_disponible) */}
                <div
                  className="absolute bottom-0 w-full rounded-t"
                  style={{
                    height: `${barHeight}%`,
                    backgroundColor: color,
                    opacity: 0.2,
                  }}
                />
                {/* Foreground bar (fois_staffe) */}
                <div
                  className="absolute bottom-0 w-full rounded-t"
                  style={{
                    height: `${fillHeight}%`,
                    backgroundColor: color,
                    opacity: 0.9,
                  }}
                />
              </div>
              <span className="text-xs text-gray-500 mt-1">H{e.heure_relative}</span>
            </div>
          )
        })}
      </div>
      <div className="flex gap-4 mt-2 text-xs text-gray-500">
        <span>
          <span className="inline-block w-3 h-3 rounded mr-1 align-middle" style={{ backgroundColor: color, opacity: 0.2 }} />
          Disponible
        </span>
        <span>
          <span className="inline-block w-3 h-3 rounded mr-1 align-middle" style={{ backgroundColor: color, opacity: 0.9 }} />
          Staffé
        </span>
      </div>
    </div>
  )
}

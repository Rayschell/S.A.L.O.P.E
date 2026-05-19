const WARNING_ICONS = {
  no_respo_bar: '🔴',
  slot_understaffed: '⚠️',
  no_bureau: '🔵',
  maybe_forced: '🟡',
  affinity_unsatisfied: '💜',
  over_quota: '📈',
  long_pause: 'ℹ️',
  no_slots: 'ℹ️',
}

const WARNING_LABELS = {
  no_respo_bar: 'Respo bar manquant',
  slot_understaffed: 'Créneau sous-effectif',
  no_bureau: 'Aucun membre bureau',
  maybe_forced: 'Disponibilité "maybe" forcée',
  affinity_unsatisfied: 'Affinité non satisfaite',
  over_quota: 'Quota dépassé (escalade)',
  long_pause: 'Pause 2h entre blocs (info)',
  no_slots: 'Info',
}

const WARNING_COLORS = {
  no_respo_bar: 'bg-red-50 border-red-200 text-red-800',
  slot_understaffed: 'bg-yellow-50 border-yellow-200 text-yellow-800',
  no_bureau: 'bg-blue-50 border-blue-200 text-blue-800',
  maybe_forced: 'bg-orange-50 border-orange-200 text-orange-800',
  affinity_unsatisfied: 'bg-purple-50 border-purple-200 text-purple-800',
  over_quota: 'bg-red-50 border-red-200 text-red-800',
  long_pause: 'bg-gray-50 border-gray-200 text-gray-600',
  no_slots: 'bg-gray-50 border-gray-200 text-gray-600',
}

export default function WarningsList({ warnings, slots, members }) {
  if (warnings.length === 0) return null

  const getSlotLabel = (slotId) => {
    const s = slots.find((s) => s.id === slotId)
    if (!s) return `Créneau #${slotId}`
    return new Date(s.heure_debut).toLocaleTimeString('fr-FR', {
      hour: '2-digit', minute: '2-digit',
    }) + ' – ' + new Date(s.heure_fin).toLocaleTimeString('fr-FR', {
      hour: '2-digit', minute: '2-digit',
    })
  }

  // Group by type
  const grouped = {}
  for (const w of warnings) {
    if (!grouped[w.type]) grouped[w.type] = []
    grouped[w.type].push(w)
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-700">
        ⚠ {warnings.length} avertissement(s) après génération
      </h3>
      {Object.entries(grouped).map(([type, items]) => (
        <div key={type} className={`border rounded-lg px-4 py-3 text-sm ${WARNING_COLORS[type] || 'bg-gray-50 border-gray-200'}`}>
          <p className="font-semibold mb-1">
            {WARNING_ICONS[type]} {WARNING_LABELS[type] || type} ({items.length})
          </p>
          <ul className="space-y-0.5 text-xs">
            {items.map((w, i) => (
              <li key={i}>• {w.message}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

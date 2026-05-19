import { useState } from 'react'
import { eventsApi } from '../../api/events.js'

export default function SlotConfig({ slots, eventId, onSaved, disabled }) {
  const [maxPersonnes, setMaxPersonnes] = useState(
    Object.fromEntries(slots.map((s) => [s.id, s.max_personnes]))
  )
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await Promise.all(
        slots.map((s) =>
          eventsApi.updateSlot(eventId, s.id, { max_personnes: maxPersonnes[s.id] })
        )
      )
      onSaved()
    } finally {
      setSaving(false)
    }
  }

  const fmt = (dt) => new Date(dt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  const fmtDate = (dt) => new Date(dt).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })

  if (slots.length === 0) {
    return (
      <div className="text-gray-400 py-8 text-center text-sm">
        Aucun créneau. Importez d'abord un CSV.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-700">Configuration des créneaux</h2>
      <p className="text-sm text-gray-500">
        Définissez le nombre maximum de personnes par créneau.
      </p>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-600 uppercase">
            <tr>
              <th className="px-4 py-3 text-left">Créneau</th>
              <th className="px-4 py-3 text-center w-40">Max personnes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {slots.map((s) => (
              <tr key={s.id}>
                <td className="px-4 py-3 text-gray-700">
                  {fmtDate(s.heure_debut)} · {fmt(s.heure_debut)} – {fmt(s.heure_fin)}
                </td>
                <td className="px-4 py-3 text-center">
                  <input
                    type="number"
                    min="1"
                    max="20"
                    value={maxPersonnes[s.id] ?? 3}
                    disabled={disabled}
                    onChange={(e) =>
                      setMaxPersonnes((prev) => ({
                        ...prev,
                        [s.id]: parseInt(e.target.value, 10),
                      }))
                    }
                    className="w-20 border rounded px-2 py-1 text-center focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!disabled && (
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm bg-blue-700 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      )}
    </div>
  )
}

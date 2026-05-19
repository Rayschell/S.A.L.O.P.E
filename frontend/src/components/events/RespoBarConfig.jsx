import { useState } from 'react'
import { eventsApi } from '../../api/events.js'

export default function RespoBarConfig({ eventId, members, resposBar, onSaved, disabled }) {
  const bureauMembers = members.filter((m) => m.roles?.includes('bureau'))
  const [ordered, setOrdered] = useState(resposBar.map((r) => r.membre_id))
  const [saving, setSaving] = useState(false)

  const addRespo = (memberId) => {
    if (!ordered.includes(memberId)) {
      setOrdered([...ordered, memberId])
    }
  }

  const removeRespo = (memberId) => {
    setOrdered(ordered.filter((id) => id !== memberId))
  }

  const moveUp = (idx) => {
    if (idx === 0) return
    const next = [...ordered]
    ;[next[idx - 1], next[idx]] = [next[idx], next[idx - 1]]
    setOrdered(next)
  }

  const moveDown = (idx) => {
    if (idx === ordered.length - 1) return
    const next = [...ordered]
    ;[next[idx], next[idx + 1]] = [next[idx + 1], next[idx]]
    setOrdered(next)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const result = await eventsApi.setResposBar(
        eventId,
        ordered.map((memberId, i) => ({ membre_id: memberId, ordre: i }))
      )
      onSaved(result)
    } finally {
      setSaving(false)
    }
  }

  const getMember = (id) => members.find((m) => m.id === id)

  const available = bureauMembers.filter((m) => !ordered.includes(m.id))

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-700">Désignation des respos bar</h2>
      <p className="text-sm text-gray-500">
        Optionnel. Désignez les respos bar dans l'ordre d'affectation. Si vide, la sélection est
        automatique (tri par nombre de shifts respo bar cumulés).
      </p>

      {/* Ordered list */}
      <div className="space-y-2">
        {ordered.length === 0 && (
          <p className="text-sm text-gray-400 italic">Aucun respo bar désigné (sélection automatique)</p>
        )}
        {ordered.map((memberId, idx) => {
          const m = getMember(memberId)
          if (!m) return null
          return (
            <div
              key={memberId}
              className="flex items-center gap-3 bg-white border border-gray-200 rounded-lg px-4 py-2.5"
            >
              <span className="text-sm font-medium text-gray-500 w-5 text-center">{idx + 1}</span>
              <span className="flex-1 text-sm font-medium text-gray-800">
                {m.prenom} {m.nom}
                <span className="ml-2 text-xs text-gray-400">({m.shifts_respo_bar_cumules} shifts)</span>
              </span>
              {!disabled && (
                <div className="flex gap-1">
                  <button
                    onClick={() => moveUp(idx)}
                    disabled={idx === 0}
                    className="px-1.5 py-0.5 text-xs rounded border disabled:opacity-30 hover:bg-gray-50"
                  >
                    ↑
                  </button>
                  <button
                    onClick={() => moveDown(idx)}
                    disabled={idx === ordered.length - 1}
                    className="px-1.5 py-0.5 text-xs rounded border disabled:opacity-30 hover:bg-gray-50"
                  >
                    ↓
                  </button>
                  <button
                    onClick={() => removeRespo(memberId)}
                    className="px-2 py-0.5 text-xs rounded bg-red-50 text-red-600 hover:bg-red-100"
                  >
                    ×
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Add member */}
      {!disabled && available.length > 0 && (
        <div>
          <select
            defaultValue=""
            onChange={(e) => { if (e.target.value) addRespo(parseInt(e.target.value, 10)); e.target.value = '' }}
            className="border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">+ Ajouter un respo bar…</option>
            {available.map((m) => (
              <option key={m.id} value={m.id}>
                {m.prenom} {m.nom} ({m.shifts_respo_bar_cumules} shifts)
              </option>
            ))}
          </select>
        </div>
      )}

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

import { useState } from 'react'
import { eventsApi } from '../../api/events.js'
import '../../styles/planning.css'

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

  const fmt = (dt) =>
    new Date(dt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  const fmtDate = (dt) =>
    new Date(dt).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })

  if (slots.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)', fontSize: 12 }}>
        Aucun créneau. Importez d'abord un CSV.
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <p style={{ fontSize: 15, color: 'var(--text-secondary)' }}>
        Définissez le nombre maximum de personnes par créneau.
      </p>

      <div className="planning-wrapper">
        <table className="planning-table">
          <thead>
            <tr>
              <th>Créneau</th>
              <th style={{ width: 160 }}>Max personnes</th>
            </tr>
          </thead>
          <tbody>
            {slots.map((s) => (
              <tr key={s.id}>
                <td>
                  {fmtDate(s.heure_debut)} · {fmt(s.heure_debut)} – {fmt(s.heure_fin)}
                </td>
                <td>
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
                    style={{
                      width: 70,
                      background: 'var(--bg-elevated)',
                      border: '1px solid var(--border-mid)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '6px 8px',
                      textAlign: 'center',
                      fontSize: 15,
                      color: 'var(--text-primary)',
                      outline: 'none',
                      fontFamily: 'DM Mono, monospace',
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!disabled && (
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              background: 'var(--violet)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              padding: '9px 20px',
              fontSize: 14,
              fontWeight: 500,
              cursor: saving ? 'not-allowed' : 'pointer',
              opacity: saving ? 0.6 : 1,
              fontFamily: "'DM Sans', sans-serif",
            }}
          >
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      )}
    </div>
  )
}

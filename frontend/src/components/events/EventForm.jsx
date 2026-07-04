import { useState } from 'react'
import { eventsApi } from '../../api/events.js'

// "2026-09-01T20:30:00" local, sans conversion UTC
const toLocalIso = (d) => {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:00`
}

// Options d'heures pleines 24 h ("00:00" … "23:00") — les <input type="time">
// natifs s'affichent en AM/PM selon la langue du navigateur, un select garantit le 24 h
const HOUR_OPTIONS = Array.from({ length: 24 }, (_, i) =>
  `${String(i).padStart(2, '0')}:00`
)

// Découpe [date+from, date+to] en pas de `step` minutes (to ≤ from = minuit passé)
const buildSlots = (dateStr, from, to, step) => {
  const day = dateStr.slice(0, 10)
  const start = new Date(`${day}T${from}`)
  const end = new Date(`${day}T${to}`)
  if (end <= start) end.setDate(end.getDate() + 1)
  const slots = []
  for (let t = new Date(start); t < end; ) {
    const next = new Date(t.getTime() + step * 60000)
    const fin = next > end ? end : next
    slots.push({ heure_debut: toLocalIso(t), heure_fin: toLocalIso(fin) })
    t = next
  }
  return slots
}

export default function EventForm({ onSaved, onCancel }) {
  const [form, setForm] = useState({ nom: '', date: '', type: 'soiree' })
  const [withSlots, setWithSlots] = useState(true)
  const [genFrom, setGenFrom] = useState('')
  const [genTo, setGenTo] = useState('00:00')
  const [genStep, setGenStep] = useState(60)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  // « de » suit l'heure de l'événement tant qu'il n'a pas été édité à la main
  const effectiveFrom = genFrom || (form.date ? form.date.slice(11, 16) : '20:00')
  const slotsPreview =
    withSlots && form.date ? buildSlots(form.date, effectiveFrom, genTo, genStep) : []

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (withSlots && slotsPreview.length > 100) {
      setError('Trop de créneaux (max 100) — élargis le pas ou réduis la plage.')
      return
    }
    setSaving(true)
    try {
      const event = await eventsApi.create({ ...form, date: new Date(form.date).toISOString() })
      if (withSlots && slotsPreview.length > 0) {
        try {
          await eventsApi.createSlots(event.id, slotsPreview)
        } catch (err) {
          setError(
            "Événement créé, mais échec de la création des créneaux : " +
            (err.response?.data?.detail || 'réessaie via un import CSV.')
          )
          setSaving(false)
          return
        }
      }
      onSaved()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la création.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h2 style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 4 }}>
        Nouvel événement
      </h2>

      <div>
        <label style={labelStyle}>Nom</label>
        <input
          value={form.nom}
          onChange={(e) => setForm({ ...form, nom: e.target.value })}
          required
          placeholder="ex. Soirée Printemps 2026"
          style={inputStyle}
        />
      </div>

      <div>
        <label style={labelStyle}>Date</label>
        <input
          type="datetime-local"
          value={form.date}
          onChange={(e) => setForm({ ...form, date: e.target.value })}
          required
          style={inputStyle}
        />
      </div>

      <div>
        <label style={labelStyle}>Type</label>
        <select
          value={form.type}
          onChange={(e) => setForm({ ...form, type: e.target.value })}
          style={selectStyle}
        >
          <option value="soiree">Soirée</option>
          <option value="afterwork">Afterwork</option>
        </select>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 14 }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: 'var(--text-secondary)', cursor: 'pointer', marginBottom: withSlots ? 10 : 0 }}>
          <input
            type="checkbox"
            checked={withSlots}
            onChange={(e) => setWithSlots(e.target.checked)}
            style={{ accentColor: 'var(--accent)' }}
          />
          Définir les créneaux maintenant
        </label>
        {withSlots && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 12.5, color: 'var(--text-muted)' }}>
              de
              <select value={effectiveFrom} onChange={(e) => setGenFrom(e.target.value)} style={smallInputStyle}>
                {!HOUR_OPTIONS.includes(effectiveFrom) && <option value={effectiveFrom}>{effectiveFrom}</option>}
                {HOUR_OPTIONS.map((h) => <option key={h} value={h}>{h}</option>)}
              </select>
              à
              <select value={genTo} onChange={(e) => setGenTo(e.target.value)} style={smallInputStyle}>
                {HOUR_OPTIONS.map((h) => <option key={h} value={h}>{h}</option>)}
              </select>
              par
              <select value={genStep} onChange={(e) => setGenStep(parseInt(e.target.value, 10))} style={smallInputStyle}>
                <option value={30}>30 min</option>
                <option value={60}>1 h</option>
                <option value={90}>1 h 30</option>
                <option value={120}>2 h</option>
              </select>
            </div>
            <p style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 8 }}>
              {form.date
                ? `→ ${slotsPreview.length} créneau(x) seront créés. Une fin ≤ début passe minuit. Le max de personnes par créneau s'ajuste ensuite dans l'onglet Créneaux.`
                : 'Renseigne la date pour prévisualiser les créneaux.'}
            </p>
          </>
        )}
      </div>

      {error && (
        <div
          style={{
            background: 'var(--red-soft)',
            border: '1px solid rgba(240, 82, 82, 0.2)',
            borderRadius: 'var(--radius-sm)',
            padding: '8px 12px',
            fontSize: 12,
            color: 'var(--red)',
          }}
        >
          {error}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 4 }}>
        <button type="button" onClick={onCancel} style={btnCancelStyle}>
          Annuler
        </button>
        <button type="submit" disabled={saving} style={{ ...btnSubmitStyle, opacity: saving ? 0.6 : 1 }}>
          {saving ? 'Création…' : 'Créer'}
        </button>
      </div>
    </form>
  )
}

const labelStyle = {
  display: 'block',
  fontSize: 11,
  color: 'var(--text-muted)',
  fontFamily: 'DM Mono, monospace',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  marginBottom: 5,
}

const inputStyle = {
  width: '100%',
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border-mid)',
  borderRadius: 'var(--radius-sm)',
  padding: '7px 10px',
  fontSize: 13,
  color: 'var(--text-primary)',
  outline: 'none',
  fontFamily: "'DM Sans', sans-serif",
}

const smallInputStyle = {
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border-mid)',
  borderRadius: 'var(--radius-sm)',
  padding: '5px 7px',
  fontSize: 12,
  color: 'var(--text-primary)',
  outline: 'none',
  fontFamily: "'DM Sans', sans-serif",
}

const selectStyle = {
  width: '100%',
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border-mid)',
  borderRadius: 'var(--radius-sm)',
  padding: '7px 10px',
  fontSize: 13,
  color: 'var(--text-primary)',
  outline: 'none',
  fontFamily: "'DM Sans', sans-serif",
  cursor: 'pointer',
}

const btnCancelStyle = {
  padding: '7px 14px',
  fontSize: 12,
  background: 'var(--bg-high)',
  color: 'var(--text-secondary)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)',
  cursor: 'pointer',
  fontFamily: "'DM Sans', sans-serif",
}

const btnSubmitStyle = {
  padding: '7px 14px',
  fontSize: 12,
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  cursor: 'pointer',
  fontWeight: 500,
  fontFamily: "'DM Sans', sans-serif",
}

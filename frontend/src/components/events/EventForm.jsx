import { useState } from 'react'
import { eventsApi } from '../../api/events.js'

export default function EventForm({ onSaved, onCancel }) {
  const [form, setForm] = useState({ nom: '', date: '', type: 'soiree' })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      await eventsApi.create({ ...form, date: new Date(form.date).toISOString() })
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

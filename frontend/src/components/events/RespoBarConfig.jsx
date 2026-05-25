import { useState } from 'react'
import { eventsApi } from '../../api/events.js'
import { IconArrowUp, IconArrowDown, IconX } from '@tabler/icons-react'

export default function RespoBarConfig({ eventId, members, resposBar, onSaved, disabled }) {
  const bureauMembers = members.filter((m) => m.roles?.includes('bureau'))
  const [ordered, setOrdered] = useState(resposBar.map((r) => r.membre_id))
  const [saving, setSaving] = useState(false)

  const addRespo = (memberId) => {
    if (!ordered.includes(memberId)) setOrdered([...ordered, memberId])
  }
  const removeRespo = (memberId) => setOrdered(ordered.filter((id) => id !== memberId))
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <p style={{ fontSize: 15, color: 'var(--text-secondary)' }}>
        Optionnel. Désignez les respos bar dans l'ordre d'affectation.
        Si vide, la sélection est automatique (tri par shifts cumulés).
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {ordered.length === 0 && (
          <p style={{ fontSize: 14, color: 'var(--text-muted)', fontStyle: 'italic' }}>
            Aucun respo bar désigné (sélection automatique)
          </p>
        )}
        {ordered.map((memberId, idx) => {
          const m = getMember(memberId)
          if (!m) return null
          return (
            <div
              key={memberId}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                padding: '8px 12px',
              }}
            >
              <span style={{ fontSize: 13, fontFamily: 'DM Mono, monospace', color: 'var(--text-muted)', width: 20, textAlign: 'center' }}>
                {idx + 1}
              </span>
              <span style={{ flex: 1, fontSize: 15, color: 'var(--text-primary)' }}>
                {m.prenom} {m.nom}
                <span style={{ marginLeft: 8, fontSize: 13, color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace' }}>
                  ({m.shifts_respo_bar_cumules} shifts)
                </span>
              </span>
              {!disabled && (
                <div style={{ display: 'flex', gap: 4 }}>
                  <button onClick={() => moveUp(idx)} disabled={idx === 0} style={iconBtn(idx === 0 ? 0.3 : 1)}>
                    <IconArrowUp size={11} stroke={1.5} />
                  </button>
                  <button onClick={() => moveDown(idx)} disabled={idx === ordered.length - 1} style={iconBtn(idx === ordered.length - 1 ? 0.3 : 1)}>
                    <IconArrowDown size={11} stroke={1.5} />
                  </button>
                  <button onClick={() => removeRespo(memberId)} style={{ ...iconBtn(1), color: 'var(--red)' }}>
                    <IconX size={11} stroke={1.5} />
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {!disabled && available.length > 0 && (
        <select
          defaultValue=""
          onChange={(e) => { if (e.target.value) addRespo(parseInt(e.target.value, 10)); e.target.value = '' }}
          style={selectStyle}
        >
          <option value="">+ Ajouter un respo bar…</option>
          {available.map((m) => (
            <option key={m.id} value={m.id}>
              {m.prenom} {m.nom} ({m.shifts_respo_bar_cumules} shifts)
            </option>
          ))}
        </select>
      )}

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

const iconBtn = (opacity = 1) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 22,
  height: 22,
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border)',
  borderRadius: 4,
  cursor: 'pointer',
  color: 'var(--text-muted)',
  opacity,
})

const selectStyle = {
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border-mid)',
  borderRadius: 'var(--radius-sm)',
  padding: '9px 12px',
  fontSize: 15,
  color: 'var(--text-primary)',
  outline: 'none',
  fontFamily: "'DM Sans', sans-serif",
  cursor: 'pointer',
}

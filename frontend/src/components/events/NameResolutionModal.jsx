import { useState } from 'react'
import { IconX } from '@tabler/icons-react'

export default function NameResolutionModal({ pending, onResolved, onCancel }) {
  const [resolutions, setResolutions] = useState(
    pending.map((p) => ({
      csv_name: p.csv_name,
      member_id: p.suggestions?.[0]?.member_id ?? null,
      create_new: p.suggestions?.length === 0,
      availabilities: p.availabilities,
    }))
  )

  const updateResolution = (idx, updates) => {
    setResolutions((prev) => {
      const next = [...prev]
      next[idx] = { ...next[idx], ...updates }
      return next
    })
  }

  const handleConfirm = () => onResolved(resolutions)

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
        padding: 16,
      }}
    >
      <div
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-mid)',
          borderRadius: 'var(--radius-lg)',
          width: '100%',
          maxWidth: 580,
          maxHeight: '80vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h2 style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>
              Résolution manuelle des noms ({pending.length})
            </h2>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 3 }}>
              Choisissez le membre correspondant ou créez-en un nouveau.
            </p>
          </div>
          <button
            onClick={onCancel}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}
          >
            <IconX size={16} stroke={1.5} />
          </button>
        </div>

        {/* Scrollable content */}
        <div style={{ overflowY: 'auto', flex: 1, padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {pending.map((p, idx) => {
            const res = resolutions[idx]
            return (
              <div
                key={p.csv_name}
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '12px 14px',
                }}
              >
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 10 }}>
                  Nom brut :{' '}
                  <span style={{ fontFamily: 'DM Mono, monospace', color: 'var(--text-primary)', background: 'var(--bg-high)', padding: '1px 6px', borderRadius: 3 }}>
                    {p.csv_name}
                  </span>
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {p.suggestions.map((s) => (
                    <label
                      key={s.member_id}
                      style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontSize: 13, color: 'var(--text-primary)' }}
                    >
                      <input
                        type="radio"
                        name={`resolution-${idx}`}
                        checked={!res.create_new && res.member_id === s.member_id}
                        onChange={() => updateResolution(idx, { member_id: s.member_id, create_new: false })}
                        style={{ accentColor: 'var(--accent)' }}
                      />
                      {s.display_name}
                      <span style={{ fontSize: 11, fontFamily: 'DM Mono, monospace', color: 'var(--text-muted)' }}>
                        {s.score}%
                      </span>
                    </label>
                  ))}
                  <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontSize: 13, color: 'var(--accent)' }}>
                    <input
                      type="radio"
                      name={`resolution-${idx}`}
                      checked={res.create_new}
                      onChange={() => updateResolution(idx, { create_new: true, member_id: null })}
                      style={{ accentColor: 'var(--accent)' }}
                    />
                    + Créer un nouveau membre « {p.csv_name} »
                  </label>
                </div>
              </div>
            )
          })}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '12px 20px',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 8,
          }}
        >
          <button onClick={onCancel} style={btnCancelStyle}>Annuler</button>
          <button onClick={handleConfirm} style={btnConfirmStyle}>
            Confirmer les résolutions
          </button>
        </div>
      </div>
    </div>
  )
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

const btnConfirmStyle = {
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

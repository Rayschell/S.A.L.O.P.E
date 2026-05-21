import { useState } from 'react'
import { eventsApi } from '../../api/events.js'
import { IconHeart, IconTrash, IconPlus } from '@tabler/icons-react'

export default function AffinityConfig({ eventId, members, affinities, onChanged, disabled }) {
  const [memberAId, setMemberAId] = useState('')
  const [memberBId, setMemberBId] = useState('')
  const [error, setError] = useState('')

  const getName = (id) => {
    const m = members.find((m) => m.id === id)
    return m ? `${m.prenom} ${m.nom}` : `#${id}`
  }

  const handleAdd = async () => {
    setError('')
    if (!memberAId || !memberBId) return
    if (memberAId === memberBId) { setError('Choisissez deux membres différents.'); return }
    try {
      await eventsApi.addAffinity(eventId, {
        membre_a_id: parseInt(memberAId, 10),
        membre_b_id: parseInt(memberBId, 10),
      })
      setMemberAId('')
      setMemberBId('')
      onChanged()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur.')
    }
  }

  const handleDelete = async (affId) => {
    await eventsApi.deleteAffinity(eventId, affId)
    onChanged()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
        Indiquez les paires de membres qui souhaitent être sur le même créneau.
        Utilisé en critère de départage lors de la génération.
      </p>

      {/* Existing affinities */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {affinities.length === 0 && (
          <p style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
            Aucune contrainte d'affinité définie.
          </p>
        )}
        {affinities.map((aff) => (
          <div
            key={aff.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              background: 'var(--violet-soft)',
              border: '1px solid rgba(124, 106, 247, 0.15)',
              borderRadius: 'var(--radius-sm)',
              padding: '8px 12px',
            }}
          >
            <IconHeart size={12} stroke={1.5} color="var(--violet)" />
            <span style={{ flex: 1, fontSize: 13, color: 'var(--text-primary)' }}>
              {getName(aff.membre_a_id)} &amp; {getName(aff.membre_b_id)}
            </span>
            {!disabled && (
              <button
                onClick={() => handleDelete(aff.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '3px 8px',
                  fontSize: 11,
                  background: 'var(--red-soft)',
                  color: 'var(--red)',
                  border: 'none',
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontFamily: "'DM Sans', sans-serif",
                }}
              >
                <IconTrash size={10} stroke={1.5} />
                Supprimer
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Add affinity */}
      {!disabled && (
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, flexWrap: 'wrap' }}>
          <div>
            <label style={labelStyle}>Membre A</label>
            <select value={memberAId} onChange={(e) => setMemberAId(e.target.value)} style={selectStyle}>
              <option value="">— Choisir —</option>
              {members.map((m) => (
                <option key={m.id} value={m.id}>{m.prenom} {m.nom}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Membre B</label>
            <select value={memberBId} onChange={(e) => setMemberBId(e.target.value)} style={selectStyle}>
              <option value="">— Choisir —</option>
              {members.map((m) => (
                <option key={m.id} value={m.id}>{m.prenom} {m.nom}</option>
              ))}
            </select>
          </div>
          <button
            onClick={handleAdd}
            disabled={!memberAId || !memberBId}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '7px 14px',
              fontSize: 12,
              background: 'var(--violet)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: !memberAId || !memberBId ? 'not-allowed' : 'pointer',
              opacity: !memberAId || !memberBId ? 0.5 : 1,
              fontWeight: 500,
              fontFamily: "'DM Sans', sans-serif",
            }}
          >
            <IconPlus size={12} stroke={1.5} />
            Ajouter
          </button>
          {error && (
            <span style={{ fontSize: 12, color: 'var(--red)' }}>{error}</span>
          )}
        </div>
      )}
    </div>
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

const selectStyle = {
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

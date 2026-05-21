import { useState } from 'react'
import { membersApi } from '../../api/members.js'
import { IconEye, IconEyeOff } from '@tabler/icons-react'

const ALL_ROLES = ['staff', 'bureau']

export default function MemberForm({ initial, onSaved, onCancel }) {
  const isEdit = !!initial
  const [form, setForm] = useState({
    prenom: initial?.prenom || '',
    nom: initial?.nom || '',
    email: initial?.email || '',
    roles: initial?.roles || ['staff'],
    shifts_respo_bar_cumules: initial?.shifts_respo_bar_cumules ?? 0,
    password: '',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const toggleRole = (role) => {
    setForm((f) => ({
      ...f,
      roles: f.roles.includes(role) ? f.roles.filter((r) => r !== role) : [...f.roles, role],
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (form.roles.length === 0) { setError('Au moins un rôle est requis.'); return }
    setSaving(true)
    try {
      const payload = { ...form }
      if (!payload.password) delete payload.password
      if (!payload.email) delete payload.email
      if (isNaN(payload.shifts_respo_bar_cumules)) payload.shifts_respo_bar_cumules = 0
      if (isEdit) {
        await membersApi.update(initial.id, payload)
      } else {
        await membersApi.create(payload)
      }
      onSaved()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la sauvegarde.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <h2 style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 2 }}>
        {isEdit ? 'Modifier le membre' : 'Ajouter un membre'}
      </h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div>
          <label style={labelStyle}>Prénom</label>
          <input value={form.prenom} onChange={(e) => setForm({ ...form, prenom: e.target.value })} required style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>Nom</label>
          <input value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} required style={inputStyle} />
        </div>
      </div>

      <div>
        <label style={labelStyle}>Email</label>
        <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} style={inputStyle} />
      </div>

      <div>
        <label style={labelStyle}>
          Mot de passe{isEdit ? ' (laisser vide pour ne pas changer)' : ''}
        </label>
        <div style={{ position: 'relative' }}>
          <input
            type={showPassword ? 'text' : 'password'}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            style={{ ...inputStyle, paddingRight: 36 }}
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            tabIndex={-1}
            style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}
          >
            {showPassword ? <IconEyeOff size={13} stroke={1.5} /> : <IconEye size={13} stroke={1.5} />}
          </button>
        </div>
      </div>

      <div>
        <label style={labelStyle}>Rôles</label>
        <div style={{ display: 'flex', gap: 16, marginTop: 4 }}>
          {ALL_ROLES.map((r) => (
            <label key={r} style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)' }}>
              <input
                type="checkbox"
                checked={form.roles.includes(r)}
                onChange={() => toggleRole(r)}
                style={{ accentColor: 'var(--violet)', width: 14, height: 14 }}
              />
              {r === 'staff' ? 'Staff' : 'Bureau'}
            </label>
          ))}
        </div>
      </div>

      <div>
        <label style={labelStyle}>Shifts respo bar</label>
        <input
          type="number"
          min="0"
          value={form.shifts_respo_bar_cumules}
          onChange={(e) => setForm({ ...form, shifts_respo_bar_cumules: parseInt(e.target.value, 10) })}
          style={{ ...inputStyle, width: 100 }}
        />
      </div>

      {error && (
        <div style={{ background: 'var(--red-soft)', border: '1px solid rgba(240,82,82,0.2)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', fontSize: 12, color: 'var(--red)' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 4 }}>
        <button type="button" onClick={onCancel} style={btnCancelStyle}>Annuler</button>
        <button type="submit" disabled={saving} style={{ ...btnSubmitStyle, opacity: saving ? 0.6 : 1 }}>
          {saving ? 'Enregistrement…' : 'Enregistrer'}
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
  background: 'var(--violet)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  cursor: 'pointer',
  fontWeight: 500,
  fontFamily: "'DM Sans', sans-serif",
}

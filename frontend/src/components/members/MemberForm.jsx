import { useState, useEffect } from 'react'
import { membersApi } from '../../api/members.js'
import { IconEye, IconEyeOff, IconX, IconPlus } from '@tabler/icons-react'

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

  const [aliases, setAliases] = useState([])
  const [aliasInput, setAliasInput] = useState('')
  const [aliasError, setAliasError] = useState('')

  const [allMembers, setAllMembers] = useState([])
  const [mergeTarget, setMergeTarget] = useState('')
  const [merging, setMerging] = useState(false)

  useEffect(() => {
    if (!isEdit) return
    membersApi.get(initial.id).then((m) => setAliases(m.aliases || []))
    membersApi.list().then((list) => setAllMembers(list.filter((m) => m.id !== initial.id)))
  }, [isEdit, initial?.id])

  const loadAliases = () => membersApi.get(initial.id).then((m) => setAliases(m.aliases || []))

  const handleAddAlias = async () => {
    if (!aliasInput.trim()) return
    setAliasError('')
    try {
      await membersApi.addAlias(initial.id, aliasInput.trim())
      setAliasInput('')
      await loadAliases()
    } catch (err) {
      setAliasError(err.response?.data?.detail || "Erreur lors de l'ajout.")
    }
  }

  const handleDeleteAlias = async (aliasId) => {
    await membersApi.deleteAlias(initial.id, aliasId)
    await loadAliases()
  }

  const handleMerge = async () => {
    if (!mergeTarget) return
    const target = allMembers.find((m) => String(m.id) === String(mergeTarget))
    if (!target) return
    const ok = confirm(
      `Fusionner "${target.prenom} ${target.nom}" dans "${initial.prenom} ${initial.nom}" ?\n\nLe membre sélectionné sera supprimé. Ses heures, disponibilités et alias seront transférés.`
    )
    if (!ok) return
    setMerging(true)
    try {
      await membersApi.merge(initial.id, target.id)
      onSaved()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la fusion.')
      setMerging(false)
    }
  }

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
                style={{ accentColor: 'var(--accent)', width: 14, height: 14 }}
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

      {isEdit && (
        <>
          <div>
            <label style={labelStyle}>Alias (imports CSV)</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
              {aliases.length === 0
                ? <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Aucun alias</span>
                : aliases.map((a) => (
                  <span key={a.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '3px 8px', fontSize: 12, color: 'var(--text-secondary)' }}>
                    {a.valeur}
                    <button type="button" onClick={() => handleDeleteAlias(a.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', padding: 0 }}>
                      <IconX size={11} stroke={1.5} />
                    </button>
                  </span>
                ))
              }
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                type="text"
                value={aliasInput}
                onChange={(e) => { setAliasInput(e.target.value); setAliasError('') }}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddAlias() } }}
                placeholder="Nouvel alias…"
                style={{ ...inputStyle, flex: 1 }}
              />
              <button type="button" onClick={handleAddAlias} style={{ ...btnCancelStyle, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <IconPlus size={12} stroke={1.5} />
                Ajouter
              </button>
            </div>
            {aliasError && <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--red)' }}>{aliasError}</p>}
          </div>

          <div style={{ border: '1px solid var(--red-soft)', borderRadius: 'var(--radius-sm)', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <label style={{ ...labelStyle, marginBottom: 0 }}>Fusionner un doublon</label>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0 }}>Le membre sélectionné sera supprimé ; ses heures, dispos et alias seront transférés ici.</p>
            <div style={{ display: 'flex', gap: 6 }}>
              <select
                value={mergeTarget}
                onChange={(e) => setMergeTarget(e.target.value)}
                style={{ ...inputStyle, flex: 1 }}
              >
                <option value="">— Sélectionner un doublon —</option>
                {allMembers.map((m) => (
                  <option key={m.id} value={m.id}>{m.prenom} {m.nom}</option>
                ))}
              </select>
              <button
                type="button"
                disabled={!mergeTarget || merging}
                onClick={handleMerge}
                style={{ padding: '7px 14px', fontSize: 12, background: 'var(--red)', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)', cursor: mergeTarget ? 'pointer' : 'not-allowed', opacity: (!mergeTarget || merging) ? 0.5 : 1, fontFamily: "'DM Sans', sans-serif", whiteSpace: 'nowrap' }}
              >
                {merging ? 'Fusion…' : 'Fusionner'}
              </button>
            </div>
          </div>
        </>
      )}

      {error && (
        <div style={{ background: 'var(--red-soft)', border: '1px solid rgba(240, 82, 82,0.2)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', fontSize: 12, color: 'var(--red)' }}>
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
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  cursor: 'pointer',
  fontWeight: 500,
  fontFamily: "'DM Sans', sans-serif",
}

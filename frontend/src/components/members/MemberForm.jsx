import { useState } from 'react'
import { membersApi } from '../../api/members.js'

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
      roles: f.roles.includes(role)
        ? f.roles.filter((r) => r !== role)
        : [...f.roles, role],
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (form.roles.length === 0) {
      setError('Au moins un rôle est requis.')
      return
    }
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
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-800">
        {isEdit ? 'Modifier le membre' : 'Ajouter un membre'}
      </h2>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Prénom</label>
          <input
            value={form.prenom}
            onChange={(e) => setForm({ ...form, prenom: e.target.value })}
            required
            className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Nom</label>
          <input
            value={form.nom}
            onChange={(e) => setForm({ ...form, nom: e.target.value })}
            required
            className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
        <input
          type="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Mot de passe{isEdit ? ' (laisser vide pour ne pas changer)' : ''}</label>
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="w-full border rounded px-3 py-1.5 pr-9 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute inset-y-0 right-2 flex items-center text-gray-400 hover:text-gray-700"
            tabIndex={-1}
          >
            {showPassword ? '🙈' : '👁️'}
          </button>
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-2">Rôles</label>
        <div className="flex gap-3">
          {ALL_ROLES.map((r) => (
            <label key={r} className="flex items-center gap-2 cursor-pointer text-sm">
              <input
                type="checkbox"
                checked={form.roles.includes(r)}
                onChange={() => toggleRole(r)}
                className="rounded"
              />
              {r === 'staff' ? 'Staff' : 'Bureau'}
            </label>
          ))}
        </div>
      </div>

      

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Shifts respo bar</label>
        <input
          type="number" min="0"
          value={form.shifts_respo_bar_cumules}
          onChange={(e) => setForm({ ...form, shifts_respo_bar_cumules: parseInt(e.target.value, 10) })}
          className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {error && (
        <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-2 pt-2">
        <button type="button" onClick={onCancel} className="px-4 py-2 text-sm rounded border hover:bg-gray-50">
          Annuler
        </button>
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 text-sm rounded bg-blue-700 text-white hover:bg-blue-600 disabled:opacity-50"
        >
          {saving ? 'Enregistrement…' : 'Enregistrer'}
        </button>
      </div>
    </form>
  )
}

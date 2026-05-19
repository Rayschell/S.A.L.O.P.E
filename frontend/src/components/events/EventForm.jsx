import { useState } from 'react'
import { eventsApi } from '../../api/events.js'

export default function EventForm({ onSaved, onCancel }) {
  const [form, setForm] = useState({
    nom: '',
    date: '',
    type: 'soiree',
  })
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
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-800">Nouvel événement</h2>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Nom</label>
        <input
          value={form.nom}
          onChange={(e) => setForm({ ...form, nom: e.target.value })}
          required
          placeholder="ex. Soirée Printemps 2026"
          className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Date</label>
        <input
          type="datetime-local"
          value={form.date}
          onChange={(e) => setForm({ ...form, date: e.target.value })}
          required
          className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Type</label>
        <select
          value={form.type}
          onChange={(e) => setForm({ ...form, type: e.target.value })}
          className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="soiree">Soirée</option>
          <option value="afterwork">Afterwork</option>
        </select>
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
          {saving ? 'Création…' : 'Créer'}
        </button>
      </div>
    </form>
  )
}

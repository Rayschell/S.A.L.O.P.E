import { useState } from 'react'
import { eventsApi } from '../../api/events.js'

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
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-700">Contraintes d'affinité</h2>
      <p className="text-sm text-gray-500">
        Indiquez les paires de membres qui souhaitent être sur le même créneau. Utilisé en
        critère de départage lors de la génération.
      </p>

      {/* Existing affinities */}
      <div className="space-y-2">
        {affinities.length === 0 && (
          <p className="text-sm text-gray-400 italic">Aucune contrainte d'affinité définie.</p>
        )}
        {affinities.map((aff) => (
          <div
            key={aff.id}
            className="flex items-center gap-3 bg-white border border-purple-100 rounded-lg px-4 py-2.5"
          >
            <span className="flex-1 text-sm text-gray-800">
              💜 {getName(aff.membre_a_id)} &amp; {getName(aff.membre_b_id)}
            </span>
            {!disabled && (
              <button
                onClick={() => handleDelete(aff.id)}
                className="px-2 py-0.5 text-xs rounded bg-red-50 text-red-600 hover:bg-red-100"
              >
                Supprimer
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Add affinity */}
      {!disabled && (
        <div className="flex items-end gap-3 flex-wrap">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Membre A</label>
            <select
              value={memberAId}
              onChange={(e) => setMemberAId(e.target.value)}
              className="border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">— Choisir —</option>
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.prenom} {m.nom}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Membre B</label>
            <select
              value={memberBId}
              onChange={(e) => setMemberBId(e.target.value)}
              className="border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">— Choisir —</option>
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.prenom} {m.nom}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={handleAdd}
            disabled={!memberAId || !memberBId}
            className="px-4 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-500 disabled:opacity-50"
          >
            Ajouter
          </button>
          {error && <p className="text-red-600 text-sm">{error}</p>}
        </div>
      )}
    </div>
  )
}

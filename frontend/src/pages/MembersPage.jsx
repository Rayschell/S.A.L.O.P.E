import { useEffect, useState } from 'react'
import { membersApi } from '../api/members.js'
import { useAuth } from '../contexts/AuthContext.jsx'
import MemberForm from '../components/members/MemberForm.jsx'
import MemberTable from '../components/members/MemberTable.jsx'

export default function MembersPage() {
  const { user } = useAuth()
  const isBureau = user?.roles?.includes('bureau')

  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = () => {
    setLoading(true)
    membersApi.list().then(setMembers).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id) => {
    if (!confirm('Supprimer ce membre ?')) return
    await membersApi.delete(id)
    load()
  }

  const handleResetCounters = async (id) => {
    if (!confirm('Réinitialiser les compteurs de ce membre ?')) return
    await membersApi.resetCounters(id)
    load()
  }

  const handleResetAll = async () => {
    if (!confirm('Réinitialiser TOUS les compteurs ?')) return
    await membersApi.resetAllCounters()
    load()
  }

  const handleSaved = () => {
    setShowForm(false)
    setEditing(null)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Membres</h1>
        {isBureau && (
          <div className="flex gap-2">
            <button
              onClick={handleResetAll}
              className="px-3 py-2 text-sm border border-orange-400 text-orange-700 rounded-lg hover:bg-orange-50"
            >
              Réinit. tous les compteurs
            </button>
            <button
              onClick={() => { setEditing(null); setShowForm(true) }}
              className="px-4 py-2 text-sm bg-blue-700 text-white rounded-lg hover:bg-blue-600"
            >
              + Ajouter un membre
            </button>
          </div>
        )}
      </div>

      {loading ? (
        <p className="text-gray-500">Chargement…</p>
      ) : (
        <MemberTable
          members={members}
          isBureau={isBureau}
          onEdit={(m) => { setEditing(m); setShowForm(true) }}
          onDelete={handleDelete}
          onResetCounters={handleResetCounters}
        />
      )}

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg mx-4">
            <MemberForm
              initial={editing}
              onSaved={handleSaved}
              onCancel={() => { setShowForm(false); setEditing(null) }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

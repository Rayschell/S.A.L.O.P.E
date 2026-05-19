import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { eventsApi } from '../api/events.js'
import { useAuth } from '../contexts/AuthContext.jsx'
import EventForm from '../components/events/EventForm.jsx'

const TYPE_LABEL = { afterwork: 'Afterwork', soiree: 'Soirée' }
const STATUT_LABEL = { brouillon: 'Brouillon', publie: 'Publié' }
const STATUT_COLOR = {
  brouillon: 'bg-yellow-100 text-yellow-800',
  publie: 'bg-green-100 text-green-800',
}

export default function EventsPage() {
  const { user } = useAuth()
  const isBureau = user?.roles?.includes('bureau')

  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)

  const load = () => {
    setLoading(true)
    eventsApi.list().then(setEvents).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id) => {
    if (!confirm('Supprimer cet événement ?')) return
    await eventsApi.delete(id)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Événements</h1>
        {isBureau && (
          <button
            onClick={() => setShowForm(true)}
            className="px-4 py-2 text-sm bg-blue-700 text-white rounded-lg hover:bg-blue-600"
          >
            + Nouvel événement
          </button>
        )}
      </div>

      {loading ? (
        <p className="text-gray-500">Chargement…</p>
      ) : events.length === 0 ? (
        <p className="text-gray-400 text-center py-12">Aucun événement. Créez-en un !</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {events.map((ev) => (
            <div
              key={ev.id}
              className="bg-white rounded-xl shadow border border-gray-100 p-5 flex flex-col gap-3"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-semibold text-gray-800">{ev.nom}</h2>
                  <p className="text-sm text-gray-500">
                    {new Date(ev.date).toLocaleDateString('fr-FR', {
                      day: 'numeric',
                      month: 'long',
                      year: 'numeric',
                    })}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className="text-xs font-medium text-gray-600 bg-gray-100 px-2 py-0.5 rounded">
                    {TYPE_LABEL[ev.type]}
                  </span>
                  <span
                    className={`text-xs font-medium px-2 py-0.5 rounded ${STATUT_COLOR[ev.statut]}`}
                  >
                    {STATUT_LABEL[ev.statut]}
                  </span>
                </div>
              </div>
              <div className="flex gap-2 mt-auto">
                <Link
                  to={`/events/${ev.id}`}
                  className="flex-1 text-center px-3 py-1.5 text-sm bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100"
                >
                  Ouvrir
                </Link>
                {isBureau && ev.statut === 'brouillon' && (
                  <button
                    onClick={() => handleDelete(ev.id)}
                    className="px-3 py-1.5 text-sm bg-red-50 text-red-600 rounded-lg hover:bg-red-100"
                  >
                    Supprimer
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
            <EventForm
              onSaved={() => { setShowForm(false); load() }}
              onCancel={() => setShowForm(false)}
            />
          </div>
        </div>
      )}
    </div>
  )
}

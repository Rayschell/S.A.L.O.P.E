import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { eventsApi } from '../api/events.js'
import { membersApi } from '../api/members.js'
import { useAuth } from '../contexts/AuthContext.jsx'
import CsvImport from '../components/events/CsvImport.jsx'
import RespoBarConfig from '../components/events/RespoBarConfig.jsx'
import AffinityConfig from '../components/events/AffinityConfig.jsx'
import SlotConfig from '../components/events/SlotConfig.jsx'
import PlanningGrid from '../components/planning/PlanningGrid.jsx'
import WarningsList from '../components/planning/WarningsList.jsx'

const TABS = ['import', 'config', 'respos', 'affinites', 'planning']
const TAB_LABELS = {
  import: '1. Import CSV',
  config: '2. Créneaux',
  respos: '3. Respos bar',
  affinites: '4. Affinités',
  planning: '5. Planning',
}

export default function EventDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const isBureau = user?.roles?.includes('bureau')

  const [event, setEvent] = useState(null)
  const [slots, setSlots] = useState([])
  const [members, setMembers] = useState([])
  const [assignments, setAssignments] = useState([])
  const [affinities, setAffinities] = useState([])
  const [resposBar, setResposBar] = useState([])
  const [warnings, setWarnings] = useState([])
  const [tab, setTab] = useState('import')
  const [generating, setGenerating] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [loading, setLoading] = useState(true)

  const reload = async () => {
    const [ev, sl, asgn, aff, rb, mem] = await Promise.all([
      eventsApi.get(id),
      eventsApi.listSlots(id),
      eventsApi.listAssignments(id),
      eventsApi.listAffinities(id),
      eventsApi.listResposBar(id),
      membersApi.list(),
    ])
    setEvent(ev)
    setSlots(sl.sort((a, b) => new Date(a.heure_debut) - new Date(b.heure_debut)))
    setAssignments(asgn)
    setAffinities(aff)
    setResposBar(rb)
    setMembers(mem)
    setLoading(false)
  }

  useEffect(() => { reload() }, [id])

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const result = await eventsApi.generate(id)
      setWarnings(result.warnings)
      setAssignments(result.assignments)
      setTab('planning')
    } finally {
      setGenerating(false)
    }
  }

  const handlePublish = async () => {
    if (!confirm('Valider le planning et incrémenter les compteurs ?')) return
    setPublishing(true)
    try {
      const ev = await eventsApi.publish(id)
      setEvent(ev)
    } finally {
      setPublishing(false)
    }
  }

  if (loading) {
    return <p className="text-gray-500">Chargement…</p>
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <button
            onClick={() => navigate('/events')}
            className="text-sm text-blue-600 hover:underline mb-1"
          >
            ← Retour
          </button>
          <h1 className="text-2xl font-bold text-gray-800">
            {event.nom}
            <span className="ml-3 text-base font-normal text-gray-500">
              {new Date(event.date).toLocaleDateString('fr-FR', {
                day: 'numeric', month: 'long', year: 'numeric',
              })}
            </span>
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Type : <strong>{event.type === 'soiree' ? 'Soirée' : 'Afterwork'}</strong>
            {' · '}Statut : <strong>{event.statut === 'publie' ? '✅ Publié' : '📝 Brouillon'}</strong>
          </p>
        </div>
        {isBureau && (
          <div className="flex gap-2">
            <button
              onClick={handleGenerate}
              disabled={generating || event.statut === 'publie'}
              className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 disabled:opacity-50"
            >
              {generating ? 'Génération…' : '⚙ Générer le planning'}
            </button>
            {event.statut === 'brouillon' && (
              <button
                onClick={handlePublish}
                disabled={publishing}
                className="px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-500 disabled:opacity-50"
              >
                {publishing ? 'Publication…' : '✓ Valider & publier'}
              </button>
            )}
            <a
              href={eventsApi.exportPngUrl(id)}
              download={`planning-${id}.png`}
              className="px-4 py-2 text-sm bg-gray-700 text-white rounded-lg hover:bg-gray-600"
            >
              ↓ Export PNG
            </a>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 mb-6 overflow-x-auto">
        {TABS.filter((t) => t !== 'respos' || event.type === 'soiree').map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
              tab === t
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'import' && (
        <CsvImport
          eventId={id}
          onImported={reload}
          disabled={!isBureau || event.statut === 'publie'}
        />
      )}

      {tab === 'config' && (
        <SlotConfig
          slots={slots}
          eventId={id}
          onSaved={reload}
          disabled={!isBureau || event.statut === 'publie'}
        />
      )}

      {tab === 'respos' && (
        <RespoBarConfig
          eventId={id}
          members={members}
          resposBar={resposBar}
          onSaved={(rb) => setResposBar(rb)}
          disabled={!isBureau || event.statut === 'publie'}
        />
      )}

      {tab === 'affinites' && (
        <AffinityConfig
          eventId={id}
          members={members}
          affinities={affinities}
          onChanged={reload}
          disabled={!isBureau || event.statut === 'publie'}
        />
      )}

      {tab === 'planning' && (
        <div className="space-y-4">
          {warnings.length > 0 && (
            <WarningsList warnings={warnings} slots={slots} members={members} />
          )}
          <PlanningGrid
            event={event}
            slots={slots}
            members={members}
            assignments={assignments}
            affinities={affinities}
            onAssignmentChange={(newAsgns) => setAssignments(newAsgns)}
            eventId={id}
            disabled={!isBureau || event.statut === 'publie'}
          />
        </div>
      )}
    </div>
  )
}

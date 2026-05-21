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
import Badge from '../components/ui/Badge.jsx'
import { IconArrowLeft, IconPlayerPlay, IconCheck, IconDownload } from '@tabler/icons-react'

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
  const [availabilities, setAvailabilities] = useState([])
  const [warnings, setWarnings] = useState([])
  const [tab, setTab] = useState('import')
  const [generating, setGenerating] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [loading, setLoading] = useState(true)

  const reload = async () => {
    const [ev, sl, asgn, aff, rb, mem, avs] = await Promise.all([
      eventsApi.get(id),
      eventsApi.listSlots(id),
      eventsApi.listAssignments(id),
      eventsApi.listAffinities(id),
      eventsApi.listResposBar(id),
      membersApi.list(),
      eventsApi.listAvailabilities(id),
    ])
    setEvent(ev)
    setSlots(sl.sort((a, b) => new Date(a.heure_debut) - new Date(b.heure_debut)))
    setAssignments(asgn)
    setAffinities(aff)
    setResposBar(rb)
    setMembers(mem)
    setAvailabilities(avs)
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
    return <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Chargement…</p>
  }

  const isPublished = event.statut === 'publie'

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, gap: 16 }}>
        <div>
          <button
            onClick={() => navigate('/events')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              fontSize: 13,
              color: 'var(--text-muted)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              marginBottom: 8,
              fontFamily: "'DM Sans', sans-serif",
            }}
          >
            <IconArrowLeft size={13} stroke={1.5} />
            Retour
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <h1 style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-primary)' }}>{event.nom}</h1>
            <Badge variant={isPublished ? 'green' : 'amber'}>
              {isPublished ? 'Publié' : 'Brouillon'}
            </Badge>
            <Badge variant="default">{event.type === 'soiree' ? 'Soirée' : 'Afterwork'}</Badge>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
            {new Date(event.date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
        </div>
        {isBureau && (
          <div style={{ display: 'flex', gap: 8, flexShrink: 0, flexWrap: 'wrap' }}>
            <button
              onClick={handleGenerate}
              disabled={generating || isPublished}
              style={{ ...actionBtnStyle('var(--accent)'), opacity: generating || isPublished ? 0.5 : 1, cursor: generating || isPublished ? 'not-allowed' : 'pointer' }}
            >
              <IconPlayerPlay size={13} stroke={1.5} />
              {generating ? 'Génération…' : 'Générer'}
            </button>
            {!isPublished && (
              <button
                onClick={handlePublish}
                disabled={publishing}
                style={{ ...actionBtnStyle('var(--green)'), opacity: publishing ? 0.5 : 1, cursor: publishing ? 'not-allowed' : 'pointer' }}
              >
                <IconCheck size={13} stroke={1.5} />
                {publishing ? 'Publication…' : 'Valider & publier'}
              </button>
            )}
            <a
              href={eventsApi.exportPngUrl(id)}
              download={`planning-${id}.png`}
              style={{ ...actionBtnStyle('var(--bg-high)', 'var(--text-secondary)', '1px solid var(--border)'), textDecoration: 'none' }}
            >
              <IconDownload size={13} stroke={1.5} />
              Export PNG
            </a>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: 20, overflowX: 'auto' }}>
        {TABS.filter((t) => t !== 'respos' || event.type === 'soiree').map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '8px 16px',
              fontSize: 14,
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              color: tab === t ? 'var(--text-primary)' : 'var(--text-muted)',
              borderBottom: tab === t ? '2px solid var(--violet)' : '2px solid transparent',
              fontFamily: "'DM Sans', sans-serif",
              fontWeight: tab === t ? 500 : 400,
              transition: 'color 120ms ease',
              marginBottom: -1,
            }}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'import' && (
        <CsvImport eventId={id} onImported={reload} disabled={!isBureau || isPublished} />
      )}
      {tab === 'config' && (
        <SlotConfig slots={slots} eventId={id} onSaved={reload} disabled={!isBureau || isPublished} />
      )}
      {tab === 'respos' && (
        <RespoBarConfig
          eventId={id}
          members={members}
          resposBar={resposBar}
          onSaved={(rb) => setResposBar(rb)}
          disabled={!isBureau || isPublished}
        />
      )}
      {tab === 'affinites' && (
        <AffinityConfig
          eventId={id}
          members={members}
          affinities={affinities}
          onChanged={reload}
          disabled={!isBureau || isPublished}
        />
      )}
      {tab === 'planning' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {warnings.length > 0 && (
            <WarningsList warnings={warnings} slots={slots} members={members} />
          )}
          <PlanningGrid
            event={event}
            slots={slots}
            members={members}
            assignments={assignments}
            affinities={affinities}
            availabilities={availabilities}
            onAssignmentChange={(newAsgns) => setAssignments(newAsgns)}
            eventId={id}
            disabled={!isBureau || isPublished}
          />
        </div>
      )}
    </div>
  )
}

const actionBtnStyle = (bg, color = '#fff', border = 'none') => ({
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  background: bg,
  color,
  border,
  borderRadius: 'var(--radius-sm)',
  padding: '8px 14px',
  fontSize: 13,
  fontWeight: 500,
  cursor: 'pointer',
  fontFamily: "'DM Sans', sans-serif",
  transition: 'opacity 120ms ease',
})

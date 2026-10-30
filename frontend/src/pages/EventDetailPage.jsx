import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { eventsApi } from '../api/events.js'
import { computeWarnings } from '../utils/computeWarnings.js'
import { membersApi } from '../api/members.js'
import { useAuth } from '../contexts/AuthContext.jsx'
import CsvImport from '../components/events/CsvImport.jsx'
import PublicPollAdmin from '../components/events/PublicPollAdmin.jsx'
import RespoBarConfig from '../components/events/RespoBarConfig.jsx'
import AffinityConfig from '../components/events/AffinityConfig.jsx'
import SlotConfig from '../components/events/SlotConfig.jsx'
import ParticipantsFilter from '../components/events/ParticipantsFilter.jsx'
import PlanningGrid from '../components/planning/PlanningGrid.jsx'
import WarningsList from '../components/planning/WarningsList.jsx'
import ProposalCompareModal from '../components/planning/ProposalCompareModal.jsx'
import LogoPicker from '../components/events/LogoPicker.jsx'
import { logosApi } from '../api/logos.js'
import Badge from '../components/ui/Badge.jsx'
import { toast } from '../components/ui/Toaster.jsx'
import { IconArrowLeft, IconPlayerPlay, IconCheck, IconDownload, IconCopy, IconArrowBackUp, IconAlertTriangle, IconLayoutColumns, IconTrash, IconDots, IconX } from '@tabler/icons-react'

const TABS = ['import', 'config', 'respos', 'affinites', 'participants', 'planning']
const TAB_LABELS = {
  import: '1. Disponibilités',
  config: '2. Créneaux',
  respos: '3. Respos bar',
  affinites: '4. Affinités (opt.)',
  participants: '5. Participants (opt.)',
  planning: '6. Planning',
}

export default function EventDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const isBureau = user?.roles?.includes('bureau')

  const [showMore, setShowMore] = useState(false) // actions secondaires dépliées (téléphone)
  const [event, setEvent] = useState(null)
  const [slots, setSlots] = useState([])
  const [members, setMembers] = useState([])
  const [assignments, setAssignments] = useState([])
  const [affinities, setAffinities] = useState([])
  const [resposBar, setResposBar] = useState([])
  const [availabilities, setAvailabilities] = useState([])
  const [excludedMemberIds, setExcludedMemberIds] = useState(new Set())
  const [tab, setTab] = useState('import')
  const [generating, setGenerating] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [showClearModal, setShowClearModal] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [exportingPng, setExportingPng] = useState(false)
  const [copyingPng, setCopyingPng] = useState(false)
  const [pngCopied, setPngCopied] = useState(false)
  const [highlight, setHighlight] = useState(null) // { slotId, memberId }
  const [showPublishModal, setShowPublishModal] = useState(false)
  const [showProposals, setShowProposals] = useState(false)
  const [showLogoPicker, setShowLogoPicker] = useState(false)
  const [loading, setLoading] = useState(true)

  // Pile d'annulation : chaque entrée = liste d'opérations inverses identifiées
  // par la clé naturelle (creneau_id, membre_id) — jamais par id d'affectation
  // (les ids changent quand on re-crée une affectation supprimée)
  const undoStackRef = useRef([])
  const [undoCount, setUndoCount] = useState(0)

  const pushUndo = (ops) => {
    undoStackRef.current.push(ops)
    if (undoStackRef.current.length > 50) undoStackRef.current.shift()
    setUndoCount(undoStackRef.current.length)
  }

  const clearUndo = () => {
    undoStackRef.current = []
    setUndoCount(0)
  }

  const handleUndo = async () => {
    const ops = undoStackRef.current.pop()
    setUndoCount(undoStackRef.current.length)
    if (!ops) return
    try {
      let current = assignments
      for (const op of ops) {
        if (op.op === 'add') {
          await eventsApi.addAssignment(id, { creneau_id: op.creneau_id, membre_id: op.membre_id, type: op.type })
        } else {
          const a = current.find((x) => x.creneau_id === op.creneau_id && x.membre_id === op.membre_id)
          if (!a) continue
          if (op.op === 'delete') await eventsApi.deleteAssignment(id, a.id)
          else await eventsApi.updateAssignment(id, a.id, { type: op.type })
        }
      }
      const fresh = await eventsApi.listAssignments(id)
      setAssignments(fresh)
      toast.success('Action annulée')
    } catch {
      // l'intercepteur axios affiche déjà l'erreur en toast
    }
  }

  // Ctrl/Cmd+Z — ré-enregistré à chaque rendu pour capturer l'état frais
  useEffect(() => {
    const onKey = (e) => {
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== 'z') return
      const tag = e.target.tagName
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || e.target.isContentEditable) return
      if (!isBureau || event?.statut === 'publie' || undoStackRef.current.length === 0) return
      e.preventDefault()
      handleUndo()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

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
    setExcludedMemberIds(new Set(ev.excluded_member_ids || []))
    clearUndo()
    setLoading(false)
  }

  useEffect(() => { reload() }, [id])

  const handleGenerate = async () => {
    if (
      assignments.length > 0 &&
      !confirm('Régénérer le planning ? Les affectations automatiques seront remplacées ; les affectations manuelles sont conservées.')
    ) return
    setGenerating(true)
    try {
      const result = await eventsApi.generate(id, [...excludedMemberIds])
      setAssignments(result.assignments)
      clearUndo()
      setTab('planning')
    } finally {
      setGenerating(false)
    }
  }

  const handleClearPlanning = async () => {
    setClearing(true)
    try {
      await eventsApi.clearAssignments(id)
      setAssignments([])
      clearUndo()
      setShowClearModal(false)
      toast.success('Planning vidé')
    } finally {
      setClearing(false)
    }
  }

  const handleApplyProposal = (result) => {
    setAssignments(result.assignments)
    clearUndo()
    setShowProposals(false)
    setTab('planning')
    toast.success('Variante appliquée')
  }

  const handlePublish = async () => {
    setPublishing(true)
    try {
      const ev = await eventsApi.publish(id)
      setEvent(ev)
      clearUndo()
      setShowPublishModal(false)
    } finally {
      setPublishing(false)
    }
  }

  const handleUnpublish = async () => {
    if (!confirm('Dépublier cet événement ? Les compteurs incrémentés à la publication seront décrémentés.')) return
    setPublishing(true)
    try {
      const ev = await eventsApi.unpublish(id)
      setEvent(ev)
    } finally {
      setPublishing(false)
    }
  }

  const handleToggleExclusion = (memberId) => {
    setExcludedMemberIds((prev) => {
      const next = new Set(prev)
      if (next.has(memberId)) next.delete(memberId)
      else next.add(memberId)
      eventsApi.setExclusions(id, [...next]).catch(() => {})
      return next
    })
  }

  const fetchPngBlob = async () => {
    // Auth par cookie httpOnly — envoyé automatiquement en same-origin
    const res = await fetch(`/api/events/${id}/export-png`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.blob()
  }

  const handleExportPng = async () => {
    setExportingPng(true)
    try {
      const blob = await fetchPngBlob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `planning-${id}.png`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExportingPng(false)
    }
  }

  const handleSelectLogo = async (logoId) => {
    const ev = await eventsApi.setLogo(id, logoId)
    setEvent((prev) => ({ ...prev, logo_id: ev.logo_id }))
  }

  const handleCopyPng = async () => {
    setCopyingPng(true)
    try {
      const blob = await fetchPngBlob()
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
      setPngCopied(true)
      setTimeout(() => setPngCopied(false), 2500)
    } finally {
      setCopyingPng(false)
    }
  }

  // Warnings W1-W7 recalculés en continu (restent justes après édition manuelle)
  const liveWarnings = useMemo(
    () =>
      !event || assignments.length === 0
        ? []
        : computeWarnings({ event, slots, assignments, members, availabilities, affinities }),
    [event, slots, assignments, members, availabilities, affinities]
  )

  const handleWarningSelect = (w) => {
    setHighlight({ slotId: w.slot_id ?? null, memberId: w.member_id ?? null })
    setTimeout(() => setHighlight(null), 4000)
  }

  if (loading) {
    return <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Chargement…</p>
  }

  const isPublished = event.statut === 'publie'
  const canGenerate = availabilities.length > 0

  const visibleTabs = TABS.filter((t) => t !== 'respos' || event.type === 'soiree')

  // Wizard : après une action réussie, on enchaîne sur l'étape suivante
  const advanceFrom = (t) => {
    const i = visibleTabs.indexOf(t)
    if (i >= 0 && i < visibleTabs.length - 1) setTab(visibleTabs[i + 1])
  }

  const tabDone = {
    import: availabilities.length > 0,
    config: slots.length > 0,
    respos: resposBar.length > 0,
    affinites: affinities.length > 0,
    participants: excludedMemberIds.size > 0,
    planning: assignments.length > 0,
  }
  const doneCount = visibleTabs.filter((t) => tabDone[t]).length

  const slotCounts = {}
  for (const a of assignments) slotCounts[a.creneau_id] = (slotCounts[a.creneau_id] || 0) + 1
  const understaffedSlots = slots.filter((s) => (slotCounts[s.id] || 0) < s.max_personnes)
  const fmtTime = (dt) => new Date(dt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', hour12: false })

  return (
    <div>
      {/* Header */}
      <div className="event-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, gap: 16 }}>
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
          <div className={`event-actions${showMore ? ' show-more' : ''}`} style={{ display: 'flex', gap: 8, flexShrink: 0, flexWrap: 'wrap' }}>
            <button
              onClick={handleGenerate}
              disabled={generating || isPublished || !canGenerate}
              title={!canGenerate ? "Importez d'abord les disponibilités (onglet Import CSV)" : undefined}
              style={{ ...actionBtnStyle('var(--accent)'), opacity: generating || isPublished || !canGenerate ? 0.5 : 1, cursor: generating || isPublished || !canGenerate ? 'not-allowed' : 'pointer' }}
            >
              <IconPlayerPlay size={13} stroke={1.5} />
              {generating ? 'Génération…' : 'Générer'}
            </button>
            <button
              onClick={() => setShowProposals(true)}
              className="event-secondary"
              disabled={generating || isPublished || !canGenerate}
              title={!canGenerate ? "Importez d'abord les disponibilités (onglet Import CSV)" : 'Générer 3 variantes et choisir la meilleure'}
              style={{ ...actionBtnStyle('var(--bg-high)', 'var(--text-secondary)', '1px solid var(--border)'), opacity: generating || isPublished || !canGenerate ? 0.5 : 1, cursor: generating || isPublished || !canGenerate ? 'not-allowed' : 'pointer' }}
            >
              <IconLayoutColumns size={13} stroke={1.5} />
              Comparer 3 variantes
            </button>
            {!isPublished && (
              <button
                onClick={() => setShowPublishModal(true)}
                disabled={publishing || assignments.length === 0}
                title={assignments.length === 0 ? "Aucune affectation à publier" : undefined}
                style={{ ...actionBtnStyle('var(--green)'), opacity: publishing || assignments.length === 0 ? 0.5 : 1, cursor: publishing || assignments.length === 0 ? 'not-allowed' : 'pointer' }}
              >
                <IconCheck size={13} stroke={1.5} />
                Valider & publier
              </button>
            )}
            {isPublished && (
              <button
                onClick={handleUnpublish}
                disabled={publishing}
                style={{ ...actionBtnStyle('var(--red-soft)', 'var(--red)', '1px solid rgba(240, 82, 82,0.3)'), opacity: publishing ? 0.5 : 1, cursor: publishing ? 'not-allowed' : 'pointer' }}
              >
                <IconArrowBackUp size={13} stroke={1.5} />
                {publishing ? 'Dépublication…' : 'Dépublier'}
              </button>
            )}
            <button
              onClick={handleExportPng}
              className="event-secondary"
              disabled={exportingPng}
              style={{ ...actionBtnStyle('var(--bg-high)', 'var(--text-secondary)', '1px solid var(--border)'), opacity: exportingPng ? 0.5 : 1, cursor: exportingPng ? 'not-allowed' : 'pointer' }}
            >
              <IconDownload size={13} stroke={1.5} />
              {exportingPng ? 'Export…' : 'Export PNG'}
            </button>
            {typeof ClipboardItem !== 'undefined' && (
              <button
                onClick={handleCopyPng}
                className="event-secondary"
                disabled={copyingPng}
                title="Copier l'image dans le presse-papier"
                style={{ ...actionBtnStyle('var(--bg-high)', pngCopied ? 'var(--green)' : 'var(--text-secondary)', '1px solid var(--border)'), opacity: copyingPng ? 0.5 : 1, cursor: copyingPng ? 'not-allowed' : 'pointer' }}
              >
                {pngCopied ? <IconCheck size={13} stroke={1.5} /> : <IconCopy size={13} stroke={1.5} />}
                {pngCopied ? 'Copié !' : copyingPng ? 'Copie…' : 'Copier'}
              </button>
            )}
            <button
              onClick={() => setShowLogoPicker(true)}
              className="event-secondary"
              title="Choisir le logo de l'export PNG"
              style={actionBtnStyle('var(--bg-high)', 'var(--text-secondary)', '1px solid var(--border)')}
            >
              <img
                src={logosApi.imageUrl(event.logo_id)}
                alt=""
                style={{ height: 16, width: 16, objectFit: 'contain' }}
              />
              Logo
            </button>
            <button
              onClick={() => setShowMore((v) => !v)}
              className="mobile-only"
              aria-label="Plus d'actions"
              style={actionBtnStyle('var(--bg-high)', 'var(--text-secondary)', '1px solid var(--border)')}
            >
              {showMore ? <IconX size={13} stroke={1.5} /> : <IconDots size={13} stroke={1.5} />}
            </button>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', overflowX: 'auto' }}>
        {visibleTabs.map((t) => (
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
              borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
              fontFamily: "'DM Sans', sans-serif",
              fontWeight: tab === t ? 500 : 400,
              transition: 'color 120ms ease',
              marginBottom: -1,
            }}
          >
            {TAB_LABELS[t]}
            {tabDone[t] && (
              <IconCheck size={11} stroke={2.5} color="var(--green)" style={{ marginLeft: 5, verticalAlign: 'middle' }} />
            )}
          </button>
        ))}
      </div>

      {/* Progression du wizard */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '10px 0 20px' }}>
        <div style={{ flex: 1, height: 3, background: 'var(--bg-high)', borderRadius: 99, overflow: 'hidden' }}>
          <div
            style={{
              width: `${(doneCount / visibleTabs.length) * 100}%`,
              height: '100%',
              background: 'var(--accent)',
              borderRadius: 99,
              transition: 'width 0.3s ease',
            }}
          />
        </div>
        <span style={{ fontSize: 10, fontFamily: 'DM Mono, monospace', color: 'var(--text-muted)', flexShrink: 0 }}>
          {doneCount}/{visibleTabs.length} étapes
        </span>
      </div>

      {/* Tab content */}
      {tab === 'import' && (
        <>
          <CsvImport
            eventId={id}
            onImported={async () => { await reload(); advanceFrom('import') }}
            disabled={!isBureau || isPublished}
          />
          <PublicPollAdmin
            eventId={id}
            onImported={async () => { await reload(); advanceFrom('import') }}
            disabled={!isBureau || isPublished}
          />
        </>
      )}
      {tab === 'config' && (
        <SlotConfig
          slots={slots}
          eventId={id}
          onSaved={async () => { await reload(); advanceFrom('config') }}
          disabled={!isBureau || isPublished}
        />
      )}
      {tab === 'respos' && (
        <RespoBarConfig
          eventId={id}
          members={members}
          resposBar={resposBar}
          onSaved={(rb) => { setResposBar(rb); advanceFrom('respos') }}
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
      {tab === 'participants' && (
        <ParticipantsFilter
          members={members}
          availabilities={availabilities}
          excludedIds={excludedMemberIds}
          onToggle={handleToggleExclusion}
          onClearAll={() => {
            setExcludedMemberIds(new Set())
            eventsApi.setExclusions(id, []).catch(() => {})
          }}
          disabled={!isBureau || isPublished}
        />
      )}
      {tab === 'planning' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {liveWarnings.length > 0 && (
            <WarningsList
              warnings={liveWarnings}
              slots={slots}
              members={members}
              availabilities={availabilities}
              assignments={assignments}
              resposBar={resposBar}
              excludedMemberIds={excludedMemberIds}
              eventId={id}
              disabled={!isBureau || isPublished}
              onSelect={handleWarningSelect}
              onAssignmentChange={(newAsgns) => setAssignments(newAsgns)}
              onUndoableAction={pushUndo}
            />
          )}
          <PlanningGrid
            highlight={highlight}
            event={event}
            slots={slots}
            members={members}
            assignments={assignments}
            affinities={affinities}
            availabilities={availabilities}
            excludedMemberIds={excludedMemberIds}
            onAssignmentChange={(newAsgns) => setAssignments(newAsgns)}
            onUndoableAction={pushUndo}
            canUndo={undoCount > 0}
            onUndo={handleUndo}
            canClear={assignments.length > 0 && !generating}
            onClear={() => setShowClearModal(true)}
            eventId={id}
            disabled={!isBureau || isPublished}
          />
        </div>
      )}

      {/* Comparaison de variantes */}
      {showProposals && (
        <ProposalCompareModal
          eventId={id}
          slots={slots}
          members={members}
          excludedMemberIds={excludedMemberIds}
          onApply={handleApplyProposal}
          onClose={() => setShowProposals(false)}
        />
      )}

      {showLogoPicker && (
        <LogoPicker
          currentLogoId={event.logo_id ?? null}
          onSelect={handleSelectLogo}
          onClose={() => setShowLogoPicker(false)}
        />
      )}

      {/* Clear planning confirmation modal */}
      {showClearModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-mid)', borderRadius: 'var(--radius-lg)', padding: 24, width: '100%', maxWidth: 460, margin: '0 16px' }}>
            <h2 style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 14 }}>
              Vider le planning ?
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              <span>{assignments.length} affectation{assignments.length > 1 ? 's' : ''} {assignments.length > 1 ? 'seront supprimées' : 'sera supprimée'}, automatiques et manuelles.</span>
              <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                Cette action ne peut pas être annulée. Les disponibilités, créneaux et respos ne sont pas touchés.
              </span>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowClearModal(false)}
                style={actionBtnStyle('var(--bg-high)', 'var(--text-secondary)', '1px solid var(--border)')}
              >
                Annuler
              </button>
              <button
                onClick={handleClearPlanning}
                disabled={clearing}
                style={{ ...actionBtnStyle('var(--red)'), opacity: clearing ? 0.5 : 1 }}
              >
                <IconTrash size={13} stroke={1.5} />
                {clearing ? 'Vidage…' : 'Vider'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Publish confirmation modal */}
      {showPublishModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-mid)', borderRadius: 'var(--radius-lg)', padding: 24, width: '100%', maxWidth: 460, margin: '0 16px' }}>
            <h2 style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 14 }}>
              Publier le planning ?
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              <span>{assignments.length} affectation{assignments.length > 1 ? 's' : ''} sur {slots.length} créneau{slots.length > 1 ? 'x' : ''}.</span>
              {understaffedSlots.length > 0 && (
                <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--amber)' }}>
                  <IconAlertTriangle size={13} stroke={1.5} />
                  {understaffedSlots.length} créneau{understaffedSlots.length > 1 ? 'x' : ''} sous-staffé{understaffedSlots.length > 1 ? 's' : ''} :{' '}
                  {understaffedSlots.map((s) => `${fmtTime(s.heure_debut)} (${slotCounts[s.id] || 0}/${s.max_personnes})`).join(', ')}
                </span>
              )}
              {liveWarnings.length > 0 && (
                <span style={{ color: 'var(--amber)' }}>{liveWarnings.length} avertissement{liveWarnings.length > 1 ? 's' : ''} non résolu{liveWarnings.length > 1 ? 's' : ''}.</span>
              )}
              {excludedMemberIds.size > 0 && (
                <span>{excludedMemberIds.size} membre{excludedMemberIds.size > 1 ? 's' : ''} exclu{excludedMemberIds.size > 1 ? 's' : ''} de la génération.</span>
              )}
              <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                La publication incrémente les compteurs d'heures et de respo bar de chaque membre affecté. Elle peut être annulée via « Dépublier ».
              </span>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowPublishModal(false)}
                style={actionBtnStyle('var(--bg-high)', 'var(--text-secondary)', '1px solid var(--border)')}
              >
                Annuler
              </button>
              <button
                onClick={handlePublish}
                disabled={publishing}
                style={{ ...actionBtnStyle('var(--green)'), opacity: publishing ? 0.5 : 1 }}
              >
                <IconCheck size={13} stroke={1.5} />
                {publishing ? 'Publication…' : 'Publier'}
              </button>
            </div>
          </div>
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

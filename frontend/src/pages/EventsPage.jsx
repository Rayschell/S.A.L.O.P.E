import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { eventsApi } from '../api/events.js'
import { useAuth } from '../contexts/AuthContext.jsx'
import EventForm from '../components/events/EventForm.jsx'
import Badge from '../components/ui/Badge.jsx'
import { IconPlus, IconCalendarEvent, IconTrash, IconCopy } from '@tabler/icons-react'

const sectionLabelStyle = {
  fontSize: 12,
  fontFamily: "'DM Mono', monospace",
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.1em',
  marginBottom: 10,
  marginTop: 4,
}

const pillStyle = (active) => ({
  padding: '4px 10px',
  fontSize: 12,
  borderRadius: 999,
  border: '1px solid var(--border)',
  background: active ? 'var(--bg-high)' : 'transparent',
  color: active ? 'var(--text-primary)' : 'var(--text-muted)',
  cursor: 'pointer',
  fontFamily: "'DM Sans', sans-serif",
})

export default function EventsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const isBureau = user?.roles?.includes('bureau')

  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [filterType, setFilterType] = useState('tous')
  const [filterStatut, setFilterStatut] = useState('tous')
  const [duplicating, setDuplicating] = useState(null) // événement source
  const [dupForm, setDupForm] = useState({ nom: '', date: '' })
  const [dupBusy, setDupBusy] = useState(false)

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

  const openDuplicate = (ev) => {
    setDuplicating(ev)
    setDupForm({ nom: ev.nom, date: '' })
  }

  const handleDuplicate = async (e) => {
    e.preventDefault()
    if (!dupForm.date) return
    setDupBusy(true)
    try {
      const created = await eventsApi.duplicate(duplicating.id, {
        nom: dupForm.nom.trim() || null,
        date: new Date(dupForm.date).toISOString(),
      })
      navigate(`/events/${created.id}`)
    } finally {
      setDupBusy(false)
    }
  }

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const filtered = events.filter((ev) => {
    if (filterType !== 'tous' && ev.type !== filterType) return false
    if (filterStatut !== 'tous' && ev.statut !== filterStatut) return false
    return true
  })

  const upcoming = filtered
    .filter((ev) => new Date(ev.date) >= today)
    .sort((a, b) => new Date(a.date) - new Date(b.date))

  const past = filtered
    .filter((ev) => new Date(ev.date) < today)
    .sort((a, b) => new Date(b.date) - new Date(a.date))

  const renderCard = (ev) => (
    <div
      key={ev.id}
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        padding: '16px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 3 }}>
            {ev.nom}
          </h2>
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {new Date(ev.date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
          <Badge variant="default">{ev.type === 'soiree' ? 'Soirée' : 'Afterwork'}</Badge>
          <Badge variant={ev.statut === 'publie' ? 'green' : 'amber'}>
            {ev.statut === 'publie' ? 'Publié' : 'Brouillon'}
          </Badge>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 'auto' }}>
        <Link
          to={`/events/${ev.id}`}
          style={{
            flex: 1,
            textAlign: 'center',
            padding: '6px 0',
            fontSize: 12,
            color: 'var(--accent)',
            background: 'var(--accent-soft)',
            borderRadius: 'var(--radius-sm)',
            textDecoration: 'none',
          }}
        >
          Ouvrir
        </Link>
        {isBureau && (
          <button
            onClick={() => openDuplicate(ev)}
            title="Créer un nouvel événement à partir de celui-ci (créneaux + exclusions)"
            style={{
              padding: '6px 10px',
              fontSize: 12,
              color: 'var(--accent)',
              background: 'var(--accent-soft)',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <IconCopy size={11} stroke={1.5} />
            Dupliquer
          </button>
        )}
        {isBureau && ev.statut === 'brouillon' && (
          <button
            onClick={() => handleDelete(ev.id)}
            style={{
              padding: '6px 10px',
              fontSize: 12,
              color: 'var(--red)',
              background: 'var(--red-soft)',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <IconTrash size={11} stroke={1.5} />
            Supprimer
          </button>
        )}
      </div>
    </div>
  )

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 24 }}>
        <IconCalendarEvent size={16} stroke={1.5} color="var(--text-muted)" />
        <h1 style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-primary)' }}>Événements</h1>
        {isBureau && (
          <button onClick={() => setShowForm(true)} style={btnPrimaryStyle}>
            <IconPlus size={12} stroke={1.5} />
            Nouvel événement
          </button>
        )}
      </div>

      {/* Filtres */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {[
            { key: 'tous', label: 'Tous' },
            { key: 'afterwork', label: 'Afterwork' },
            { key: 'soiree', label: 'Soirée' },
          ].map(({ key, label }) => (
            <button key={key} onClick={() => setFilterType(key)} style={pillStyle(filterType === key)}>
              {label}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {[
            { key: 'tous', label: 'Tous' },
            { key: 'brouillon', label: 'Brouillon' },
            { key: 'publie', label: 'Publié' },
          ].map(({ key, label }) => (
            <button key={key} onClick={() => setFilterStatut(key)} style={pillStyle(filterStatut === key)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Chargement…</p>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)', fontSize: 12 }}>
          Aucun événement.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {upcoming.length > 0 && (
            <div>
              <p style={sectionLabelStyle}>À venir</p>
              <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
                {upcoming.map(renderCard)}
              </div>
            </div>
          )}
          {past.length > 0 && (
            <div>
              <p style={sectionLabelStyle}>Passés</p>
              <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
                {past.map(renderCard)}
              </div>
            </div>
          )}
        </div>
      )}

      {showForm && (
        <div style={overlayStyle} onClick={() => setShowForm(false)}>
          <div style={panelStyle} onClick={(e) => e.stopPropagation()}>
            <EventForm
              onSaved={() => { setShowForm(false); load() }}
              onCancel={() => setShowForm(false)}
            />
          </div>
        </div>
      )}

      {duplicating && (
        <div style={overlayStyle} onClick={() => setDuplicating(null)}>
          <div style={panelStyle} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 4 }}>
              Dupliquer « {duplicating.nom} »
            </h2>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
              Copie les créneaux (avec leurs capacités) et les exclusions vers la nouvelle date.
              Les respos bar, affinités et disponibilités ne sont pas copiés — les dispos viendront
              du nouvel import CSV.
            </p>
            <form onSubmit={handleDuplicate} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <label style={dupLabelStyle}>
                Nom
                <input
                  type="text"
                  value={dupForm.nom}
                  onChange={(e) => setDupForm((f) => ({ ...f, nom: e.target.value }))}
                  placeholder={`${duplicating.nom} (copie)`}
                  style={dupInputStyle}
                />
              </label>
              <label style={dupLabelStyle}>
                Date
                <input
                  type="datetime-local"
                  value={dupForm.date}
                  onChange={(e) => setDupForm((f) => ({ ...f, date: e.target.value }))}
                  required
                  style={dupInputStyle}
                />
              </label>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
                <button
                  type="button"
                  onClick={() => setDuplicating(null)}
                  style={{ ...btnPrimaryStyle, background: 'var(--bg-high)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={dupBusy || !dupForm.date}
                  style={{ ...btnPrimaryStyle, opacity: dupBusy || !dupForm.date ? 0.5 : 1 }}
                >
                  <IconCopy size={12} stroke={1.5} />
                  {dupBusy ? 'Duplication…' : 'Dupliquer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

const dupLabelStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: 5,
  fontSize: 12,
  color: 'var(--text-secondary)',
  fontFamily: "'DM Sans', sans-serif",
}

const dupInputStyle = {
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)',
  padding: '8px 10px',
  fontSize: 13,
  color: 'var(--text-primary)',
  fontFamily: "'DM Sans', sans-serif",
  outline: 'none',
}

const btnPrimaryStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  padding: '7px 14px',
  fontSize: 12,
  fontWeight: 500,
  cursor: 'pointer',
  fontFamily: "'DM Sans', sans-serif",
}

const overlayStyle = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0, 0, 0, 0.6)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 50,
}

const panelStyle = {
  background: 'var(--bg-surface)',
  border: '1px solid var(--border-mid)',
  borderRadius: 'var(--radius-lg)',
  padding: 24,
  width: '100%',
  maxWidth: 440,
  margin: '0 16px',
}

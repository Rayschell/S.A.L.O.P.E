import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { eventsApi } from '../api/events.js'
import { useAuth } from '../contexts/AuthContext.jsx'
import EventForm from '../components/events/EventForm.jsx'
import Badge from '../components/ui/Badge.jsx'
import { IconPlus, IconCalendarEvent, IconTrash } from '@tabler/icons-react'

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

      {loading ? (
        <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Chargement…</p>
      ) : events.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)', fontSize: 12 }}>
          Aucun événement. Créez-en un&nbsp;!
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
          {events.map((ev) => (
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
          ))}
        </div>
      )}

      {showForm && (
        <div style={overlayStyle}>
          <div style={panelStyle}>
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

const btnPrimaryStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  background: 'var(--violet)',
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

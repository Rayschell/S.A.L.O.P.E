import { useEffect, useState } from 'react'
import { membersApi } from '../api/members.js'
import { useAuth } from '../contexts/AuthContext.jsx'
import MemberForm from '../components/members/MemberForm.jsx'
import MemberTable from '../components/members/MemberTable.jsx'
import MemberStats from '../components/members/MemberStats.jsx'
import { IconPlus, IconRefresh, IconX, IconUsers } from '@tabler/icons-react'

export default function MembersPage() {
  const { user } = useAuth()
  const isBureau = user?.roles?.includes('bureau')

  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [statsModal, setStatsModal] = useState(null)   // { member, stats }
  const [statsLoading, setStatsLoading] = useState(false)

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

  const handleShowStats = async (m) => {
    setStatsModal({ member: m, stats: null })
    setStatsLoading(true)
    try {
      const stats = await membersApi.getStats(m.id)
      setStatsModal({ member: m, stats })
    } catch {
      setStatsModal({ member: m, stats: { afterwork: [], soiree: [] } })
    } finally {
      setStatsLoading(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <IconUsers size={16} stroke={1.5} color="var(--text-muted)" />
          <h1 style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-primary)' }}>Membres</h1>
        </div>
        {isBureau && (
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleResetAll} style={btnGhostStyle}>
              <IconRefresh size={12} stroke={1.5} />
              Réinit. compteurs
            </button>
            <button onClick={() => { setEditing(null); setShowForm(true) }} style={btnPrimaryStyle}>
              <IconPlus size={12} stroke={1.5} />
              Ajouter un membre
            </button>
          </div>
        )}
      </div>

      {loading ? (
        <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Chargement…</p>
      ) : (
        <MemberTable
          members={members}
          isBureau={isBureau}
          onEdit={(m) => { setEditing(m); setShowForm(true) }}
          onDelete={handleDelete}
          onResetCounters={handleResetCounters}
          onStats={handleShowStats}
        />
      )}

      {showForm && (
        <div style={overlayStyle}>
          <div style={panelStyle}>
            <MemberForm
              initial={editing}
              onSaved={handleSaved}
              onCancel={() => { setShowForm(false); setEditing(null) }}
            />
          </div>
        </div>
      )}

      {statsModal && (
        <div style={overlayStyle}>
          <div style={{ ...panelStyle, maxWidth: 540 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>
                Stats — {statsModal.member.prenom} {statsModal.member.nom}
              </h2>
              <button
                onClick={() => setStatsModal(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}
              >
                <IconX size={16} stroke={1.5} />
              </button>
            </div>
            {statsLoading
              ? <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Chargement…</p>
              : <MemberStats stats={statsModal.stats} />
            }
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

const btnGhostStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  background: 'var(--bg-high)',
  color: 'var(--text-secondary)',
  border: '1px solid var(--border)',
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

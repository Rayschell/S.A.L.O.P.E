import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { membersApi } from '../api/members.js'
import { saisonsApi } from '../api/saisons.js'
import { useAuth } from '../contexts/AuthContext.jsx'
import MemberForm from '../components/members/MemberForm.jsx'
import MemberTable from '../components/members/MemberTable.jsx'
import MemberStats from '../components/members/MemberStats.jsx'
import TeamOverview from '../components/members/TeamOverview.jsx'
import SaisonManager from '../components/members/SaisonManager.jsx'
import { IconPlus, IconRefresh, IconUsers, IconSearch, IconX, IconCalendarCog } from '@tabler/icons-react'

export default function MembersPage() {
  const { user } = useAuth()
  const isBureau = user?.roles?.includes('bureau')

  const [members, setMembers] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const [detail, setDetail] = useState(null) // { stats, timeline }
  const [detailLoading, setDetailLoading] = useState(false)
  const [saisons, setSaisons] = useState([])
  const [saisonsLoaded, setSaisonsLoaded] = useState(false)
  const [showSaisons, setShowSaisons] = useState(false)

  const selectedId = Number(searchParams.get('membre')) || null
  const selectedMember = members.find((m) => m.id === selectedId) || null

  // ?saison= : absent → défaut (saison contenant aujourd'hui), 'all' → tout l'historique
  const saisonParam = searchParams.get('saison')
  const saisonId = saisonParam && saisonParam !== 'all' ? Number(saisonParam) : null
  const selectedSaison = saisons.find((s) => s.id === saisonId) || null

  // Mise à jour de l'URL en préservant les autres paramètres (membre + saison)
  const setParams = (updates, opts) => {
    const next = new URLSearchParams(searchParams)
    for (const [k, v] of Object.entries(updates)) {
      if (v == null || v === '') next.delete(k)
      else next.set(k, String(v))
    }
    setSearchParams(next, opts)
  }

  const loadSaisons = () =>
    saisonsApi.list()
      .then((s) => setSaisons(s))
      .finally(() => setSaisonsLoaded(true))

  useEffect(() => { loadSaisons() }, [])

  // Défaut : saison contenant la date du jour (seulement si l'URL n'impose rien)
  useEffect(() => {
    if (!saisonsLoaded || searchParams.get('saison') !== null) return
    const today = new Date().toISOString().slice(0, 10)
    const current = saisons.find((s) => s.date_debut <= today && (!s.date_fin || today <= s.date_fin))
    if (current) setParams({ saison: current.id }, { replace: true })
  }, [saisonsLoaded])

  const load = () => {
    setLoading(true)
    Promise.all([
      membersApi.list(),
      isBureau ? membersApi.statsOverview(saisonId) : Promise.resolve([]),
    ])
      .then(([mem, overview]) => {
        const statsById = Object.fromEntries(overview.map((o) => [o.id, o]))
        setMembers(mem.map((m) => ({ ...m, ...statsById[m.id] })))
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [saisonId])

  useEffect(() => {
    if (!selectedId || !isBureau) {
      setDetail(null)
      return
    }
    let cancelled = false
    setDetailLoading(true)
    Promise.all([membersApi.getStats(selectedId, saisonId), membersApi.getTimeline(selectedId, saisonId)])
      .then(([stats, timeline]) => { if (!cancelled) setDetail({ stats, timeline }) })
      .catch(() => { if (!cancelled) setDetail({ stats: { afterwork: [], soiree: [] }, timeline: [] }) })
      .finally(() => { if (!cancelled) setDetailLoading(false) })
    return () => { cancelled = true }
  }, [selectedId, isBureau, saisonId])

  // Clic « dans le vide » de la zone de contenu (hors header de page, table,
  // carte détail et modales) → désélectionne le membre et referme la carte stats
  useEffect(() => {
    if (!selectedId || showForm || showSaisons) return
    const onDown = (e) => {
      if (!(e.target instanceof Element)) return
      if (!e.target.closest('main') || e.target.closest('[data-keep-selection]')) return
      setParams({ membre: null })
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [selectedId, showForm, showSaisons, searchParams])

  const handleDelete = async (id) => {
    if (!confirm('Supprimer ce membre ?')) return
    await membersApi.delete(id)
    if (id === selectedId) setParams({ membre: null })
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

  const handleRoleChange = async (id, newRoles) => {
    await membersApi.update(id, { roles: newRoles })
    load()
  }

  const handleSaved = () => {
    setShowForm(false)
    setEditing(null)
    load()
  }

  const handleSelect = (m) => {
    if (m.id === selectedId) setParams({ membre: null })
    else setParams({ membre: m.id })
  }

  const normalize = (s) => (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  const needle = normalize(search)
  const filteredMembers = needle
    ? members.filter((m) => normalize(`${m.prenom} ${m.nom}`).includes(needle))
    : members

  const maxRespoBar = Math.max(
    ...members.filter((m) => m.roles?.includes('bureau')).map((m) => m.shifts_respo_bar_cumules || 0),
    1
  )

  return (
    <div>
      <div data-keep-selection style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        <IconUsers size={16} stroke={1.5} color="var(--text-muted)" />
        <h1 style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-primary)' }}>Membres</h1>
        {!loading && (
          <span style={{ fontSize: 12, fontFamily: 'DM Mono, monospace', color: 'var(--text-muted)' }}>
            {members.length}
          </span>
        )}
        <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', marginLeft: 8 }}>
          <IconSearch size={14} stroke={1.5} color="var(--text-muted)" style={{ position: 'absolute', left: 9, pointerEvents: 'none' }} />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher un membre…"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '6px 10px 6px 30px', fontSize: 13, color: 'var(--text-primary)', fontFamily: "'DM Sans', sans-serif", outline: 'none', width: 220 }}
          />
        </div>
        {isBureau && (
          <select
            value={saisonParam ?? 'all'}
            onChange={(e) => setParams({ saison: e.target.value })}
            title="Filtrer les stats par saison (mandat de bureau)"
            style={{
              background: 'var(--bg-elevated)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)', padding: '6px 10px', fontSize: 13,
              color: 'var(--text-primary)', fontFamily: "'DM Sans', sans-serif",
              outline: 'none', cursor: 'pointer',
            }}
          >
            <option value="all">Tout l'historique</option>
            {saisons.map((s) => (
              <option key={s.id} value={s.id}>{s.nom}</option>
            ))}
          </select>
        )}
        {isBureau && (
          <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
            <button onClick={() => setShowSaisons(true)} style={btnGhostStyle} title="Gérer les saisons (mandats de bureau)">
              <IconCalendarCog size={12} stroke={1.5} />
              Saisons
            </button>
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

      {isBureau && selectedSaison && (
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: -14, marginBottom: 18 }}>
          Stats de la saison « {selectedSaison.nom} » — badge ✦ et heures calculés sur cette période.
        </p>
      )}

      {loading ? (
        <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Chargement…</p>
      ) : (
        <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div data-keep-selection style={{ flex: '1 1 560px', minWidth: 0 }}>
            <MemberTable
              members={filteredMembers}
              isBureau={isBureau}
              showStats={isBureau}
              selectedId={selectedId}
              onSelect={handleSelect}
              onEdit={(m) => { setEditing(m); setShowForm(true) }}
              onDelete={handleDelete}
              onResetCounters={handleResetCounters}
              onRoleChange={handleRoleChange}
            />
          </div>

          {isBureau && (
            <div
              data-keep-selection
              style={{
                flex: '0 0 400px',
                minWidth: 320,
                position: 'sticky',
                top: 16,
                maxHeight: 'calc(100vh - 96px)',
                overflowY: 'auto',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)',
                padding: 20,
              }}
            >
              {selectedMember ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 18, gap: 8 }}>
                    <div>
                      <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
                        {selectedMember.prenom} {selectedMember.nom}
                        {selectedMember.bien_membre && (
                          <span title="Bien membré·e·s" style={{ marginLeft: 6, color: 'var(--green)', fontSize: 13 }}>✦</span>
                        )}
                      </h2>
                      <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 3 }}>
                        {(selectedMember.roles || []).map((r) => (r === 'bureau' ? 'Bureau' : 'Staff')).join(' · ') || 'Aucun rôle'}
                        {selectedMember.email ? ` — ${selectedMember.email}` : ''}
                      </p>
                    </div>
                    <button
                      onClick={() => setParams({ membre: null })}
                      title="Fermer"
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', flexShrink: 0, marginTop: 2 }}
                    >
                      <IconX size={16} stroke={1.5} />
                    </button>
                  </div>
                  {detailLoading ? (
                    <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Chargement…</p>
                  ) : (
                    <MemberStats
                      stats={detail?.stats}
                      respoBar={selectedMember.shifts_respo_bar_cumules}
                      maxRespoBar={maxRespoBar}
                      isMemberBureau={selectedMember.roles?.includes('bureau')}
                      timeline={detail?.timeline}
                    />
                  )}
                </>
              ) : (
                <TeamOverview members={members} onSelect={handleSelect} />
              )}
            </div>
          )}
        </div>
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

      {showSaisons && (
        <SaisonManager
          saisons={saisons}
          onChanged={() => { loadSaisons(); load() }}
          onClose={() => setShowSaisons(false)}
        />
      )}
    </div>
  )
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

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
import { SkeletonRow } from '../components/ui/Skeleton.jsx'
import Skeleton from '../components/ui/Skeleton.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import { showConfirm } from '../components/ui/ConfirmModal.jsx'
import { toast } from '../components/ui/Toaster.jsx'
import {
  IconPlus, IconRefresh, IconUsers, IconSearch, IconX, IconCalendarCog,
} from '@tabler/icons-react'

export default function MembersPage() {
  const { user } = useAuth()
  const isBureau = user?.roles?.includes('bureau')

  const [members, setMembers] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [saisons, setSaisons] = useState([])
  const [saisonsLoaded, setSaisonsLoaded] = useState(false)
  const [showSaisons, setShowSaisons] = useState(false)

  const selectedId = Number(searchParams.get('membre')) || null
  const selectedMember = members.find((m) => m.id === selectedId) || null

  const saisonParam = searchParams.get('saison')
  const saisonId = saisonParam && saisonParam !== 'all' ? Number(saisonParam) : null
  const selectedSaison = saisons.find((s) => s.id === saisonId) || null

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
    if (!selectedId || !isBureau) { setDetail(null); return }
    let cancelled = false
    setDetailLoading(true)
    Promise.all([membersApi.getStats(selectedId, saisonId), membersApi.getTimeline(selectedId, saisonId)])
      .then(([stats, timeline]) => { if (!cancelled) setDetail({ stats, timeline }) })
      .catch(() => { if (!cancelled) setDetail({ stats: { afterwork: [], soiree: [] }, timeline: [] }) })
      .finally(() => { if (!cancelled) setDetailLoading(false) })
    return () => { cancelled = true }
  }, [selectedId, isBureau, saisonId])

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
    const m = members.find((x) => x.id === id)
    const ok = await showConfirm({
      title: `Supprimer ${m ? `${m.prenom} ${m.nom}` : 'ce membre'} ?`,
      message: 'Toutes ses disponibilités, affectations et statistiques seront supprimées.',
      confirmLabel: 'Supprimer',
      cancelLabel: 'Annuler',
      variant: 'danger',
    })
    if (!ok) return
    await membersApi.delete(id)
    toast.success('Membre supprimé.')
    if (id === selectedId) setParams({ membre: null })
    load()
  }

  const handleResetCounters = async (id) => {
    const m = members.find((x) => x.id === id)
    const ok = await showConfirm({
      title: `Réinitialiser les compteurs de ${m ? `${m.prenom} ${m.nom}` : 'ce membre'} ?`,
      message: 'Les compteurs heures et respo bar seront remis à zéro.',
      confirmLabel: 'Réinitialiser',
      cancelLabel: 'Annuler',
    })
    if (!ok) return
    await membersApi.resetCounters(id)
    toast.success('Compteurs réinitialisés.')
    load()
  }

  const handleResetAll = async () => {
    const ok = await showConfirm({
      title: 'Réinitialiser TOUS les compteurs ?',
      message: 'Les compteurs heures et respo bar de tous les membres seront remis à zéro.',
      confirmLabel: 'Réinitialiser tout',
      cancelLabel: 'Annuler',
      variant: 'danger',
    })
    if (!ok) return
    await membersApi.resetAllCounters()
    toast.success('Tous les compteurs ont été réinitialisés.')
    load()
  }

  const handleRoleChange = async (id, newRoles) => {
    await membersApi.update(id, { roles: newRoles })
    load()
  }

  const handleSaved = () => { setShowForm(false); setEditing(null); load() }
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
        <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 560px', minWidth: 0 }}>
            {/* En-tête tableau */}
            <div style={{ display: 'flex', gap: 12, padding: '10px 12px', marginBottom: 2 }}>
              <Skeleton height={10} width="30%" />
              <Skeleton height={10} width="20%" />
              <Skeleton height={10} width="20%" />
            </div>
            {[...Array(6)].map((_, i) => (
              <SkeletonRow key={i} style={{ opacity: 1 - i * 0.1 }} />
            ))}
          </div>
          {isBureau && (
            <div style={{
              flex: '0 0 400px', minWidth: 320,
              background: 'var(--bg-surface)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)', padding: 20,
              display: 'flex', flexDirection: 'column', gap: 16,
            }}>
              <Skeleton height={14} width="55%" />
              <Skeleton height={10} width="40%" />
              <Skeleton height={80} borderRadius={8} style={{ marginTop: 8 }} />
              <Skeleton height={80} borderRadius={8} />
            </div>
          )}
        </div>
      ) : members.length === 0 ? (
        <EmptyState
          icon={IconUsers}
          title="Aucun membre pour l'instant"
          description={isBureau ? 'Ajoute le premier membre pour commencer à gérer le staff.' : 'Les membres apparaîtront ici.'}
          action={isBureau ? { label: 'Ajouter un membre', icon: IconPlus, onClick: () => { setEditing(null); setShowForm(true) } } : undefined}
        />
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
                flex: '0 0 400px', minWidth: 320,
                position: 'sticky', top: 16,
                maxHeight: 'calc(100vh - 96px)', overflowY: 'auto',
                background: 'var(--bg-surface)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)', padding: 20,
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
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <Skeleton height={11} width="75%" />
                      <Skeleton height={11} width="55%" />
                      <Skeleton height={90} borderRadius={8} style={{ marginTop: 6 }} />
                      <Skeleton height={90} borderRadius={8} />
                      <Skeleton height={60} borderRadius={8} />
                    </div>
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
  display: 'inline-flex', alignItems: 'center', gap: 6,
  background: 'var(--accent)', color: '#fff', border: 'none',
  borderRadius: 'var(--radius-sm)', padding: '7px 14px',
  fontSize: 12, fontWeight: 500, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif",
}

const btnGhostStyle = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  background: 'var(--bg-high)', color: 'var(--text-secondary)',
  border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
  padding: '7px 14px', fontSize: 12, fontWeight: 500,
  cursor: 'pointer', fontFamily: "'DM Sans', sans-serif",
}

const overlayStyle = {
  position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.6)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
}

const panelStyle = {
  background: 'var(--bg-surface)', border: '1px solid var(--border-mid)',
  borderRadius: 'var(--radius-lg)', padding: 24,
  width: '100%', maxWidth: 440, margin: '0 16px',
}

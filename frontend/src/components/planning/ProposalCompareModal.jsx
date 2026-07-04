import { useEffect, useMemo, useState } from 'react'
import { IconCheck, IconAlertTriangle, IconX } from '@tabler/icons-react'
import { eventsApi } from '../../api/events.js'
import '../../styles/planning.css'

const VARIANT_LABELS = ['A', 'B', 'C']

/**
 * Modale de comparaison de variantes de planning.
 * Génère 3 propositions côté serveur (sans écrire en base), surligne les
 * affectations qui diffèrent entre variantes, et applique celle choisie.
 */
export default function ProposalCompareModal({ eventId, slots, members, excludedMemberIds, onApply, onClose }) {
  const [loading, setLoading] = useState(true)
  const [applying, setApplying] = useState(null)
  const [proposals, setProposals] = useState([])

  useEffect(() => {
    let cancelled = false
    eventsApi
      .generateProposals(eventId, [...excludedMemberIds], 3)
      .then((res) => {
        if (cancelled) return
        setProposals(res.proposals)
        setLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [eventId])

  const membersById = useMemo(() => {
    const m = {}
    for (const mb of members) m[mb.id] = mb
    return m
  }, [members])

  const sortedSlots = useMemo(
    () => [...slots].sort((a, b) => new Date(a.heure_debut) - new Date(b.heure_debut)),
    [slots]
  )

  // Une affectation « diffère » si elle n'apparaît pas dans TOUTES les variantes
  const keySets = useMemo(
    () => proposals.map((p) => new Set(p.assignments.map((a) => `${a.creneau_id}-${a.membre_id}-${a.type}`))),
    [proposals]
  )
  const isDiff = (a) => {
    const key = `${a.creneau_id}-${a.membre_id}-${a.type}`
    return !keySets.every((set) => set.has(key))
  }

  // Lignes des mini-grilles : union des membres affectés dans au moins une
  // variante — mêmes lignes partout pour comparer d'un coup d'œil
  const rowMembers = useMemo(() => {
    const ids = new Set()
    for (const p of proposals) for (const a of p.assignments) ids.add(a.membre_id)
    return [...ids]
      .map((id) => membersById[id] || { id, prenom: `#${id}`, nom: '' })
      .sort((a, b) => a.nom.localeCompare(b.nom) || a.prenom.localeCompare(b.prenom))
  }, [proposals, membersById])

  // Par variante : affectations indexées par cellule + effectif par créneau
  const proposalMaps = useMemo(
    () =>
      proposals.map((p) => {
        const cells = {}
        const counts = {}
        for (const a of p.assignments) {
          cells[`${a.creneau_id}-${a.membre_id}`] = a
          counts[a.creneau_id] = (counts[a.creneau_id] || 0) + 1
        }
        return { cells, counts }
      }),
    [proposals]
  )

  const handleApply = async (p) => {
    setApplying(p.index)
    try {
      const result = await eventsApi.applyProposal(eventId, {
        assignments: p.assignments,
        warnings: p.warnings,
        excluded_member_ids: [...excludedMemberIds],
      })
      onApply(result)
    } finally {
      setApplying(null)
    }
  }

  const fmtTime = (dt) =>
    new Date(dt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', hour12: false })

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border-mid)',
        borderRadius: 'var(--radius-lg)', width: '100%', maxWidth: 1500, margin: '0 16px',
        maxHeight: '85vh', display: 'flex', flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>
            Comparer les variantes de planning
          </h2>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex' }}
          >
            <IconX size={16} stroke={1.5} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: 20, overflowY: 'auto', flex: 1 }}>
          {loading && (
            <p style={{ fontSize: 13, color: 'var(--text-muted)', textAlign: 'center', padding: '40px 0' }}>
              Calcul de 3 variantes… (jusqu'à ~20 s, les affectations manuelles sont conservées dans chacune)
            </p>
          )}
          {!loading && proposals.length === 0 && (
            <p style={{ fontSize: 13, color: 'var(--text-muted)', textAlign: 'center', padding: '40px 0' }}>
              Impossible de générer des variantes — vérifiez les créneaux et les disponibilités.
            </p>
          )}
          {!loading && proposals.length === 1 && (
            <p style={{ fontSize: 12, color: 'var(--amber)', marginBottom: 12 }}>
              Une seule solution possible : les contraintes ne laissent pas d'alternative réellement différente.
            </p>
          )}
          {!loading && proposals.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${proposals.length}, 1fr)`, gap: 14 }}>
              {proposals.map((p, pi) => (
                <div
                  key={p.index}
                  style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden', display: 'flex', flexDirection: 'column', minWidth: 0 }}
                >
                  {/* En-tête de variante */}
                  <div style={{ padding: '10px 14px', background: 'var(--bg-high)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                      Variante {VARIANT_LABELS[p.index] || p.index + 1}
                    </span>
                    <span style={{ fontSize: 11, fontFamily: 'DM Mono, monospace', color: 'var(--text-muted)' }} title="Pénalité totale du solveur (plus bas = mieux)">
                      score {p.score}
                    </span>
                    {p.warnings.length > 0 && (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, marginLeft: 'auto', fontSize: 11, color: 'var(--amber)' }}>
                        <IconAlertTriangle size={11} stroke={1.5} />
                        {p.warnings.length}
                      </span>
                    )}
                  </div>

                  {/* Mini-planning : mêmes lignes dans chaque variante */}
                  <div style={{ overflowX: 'auto', flex: 1 }}>
                    <table className="planning-table mini-planning">
                      <thead>
                        <tr>
                          <th>Membre</th>
                          {sortedSlots.map((s) => (
                            <th key={s.id} title={`${fmtTime(s.heure_debut)}–${fmtTime(s.heure_fin)}`}>
                              {fmtTime(s.heure_debut)}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {rowMembers.map((m) => (
                          <tr key={m.id}>
                            <td>{m.prenom} {m.nom}</td>
                            {sortedSlots.map((s) => {
                              const a = proposalMaps[pi]?.cells[`${s.id}-${m.id}`]
                              const respo = a?.type === 'respo_bar'
                              return (
                                <td
                                  key={s.id}
                                  className={a ? (respo ? 'cell-respo' : 'cell-staff') : ''}
                                  title={a ? (respo ? 'Respo bar' : 'Staff') : undefined}
                                  style={{
                                    position: 'relative',
                                    outline: a && isDiff(a) ? '1px dashed var(--violet)' : 'none',
                                    outlineOffset: -2,
                                  }}
                                >
                                  {a ? (respo ? 'R' : 'S') : ''}
                                  {a?.source === 'manuel' && (
                                    <span className="manual-dot" title="Affectation manuelle (conservée)" />
                                  )}
                                </td>
                              )
                            })}
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr>
                          <td>Staffés / max</td>
                          {sortedSlots.map((s) => {
                            const n = proposalMaps[pi]?.counts[s.id] || 0
                            const max = s.max_personnes
                            const cls = n < max ? 'foot-under' : n > max ? 'foot-over' : 'foot-full'
                            return (
                              <td key={s.id} className={cls}>
                                {n}/{max}
                              </td>
                            )
                          })}
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* Pied de variante */}
                  <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border)' }}>
                    <button
                      onClick={() => handleApply(p)}
                      disabled={applying !== null}
                      style={{
                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                        width: '100%', background: 'var(--accent)', color: '#fff', border: 'none',
                        borderRadius: 'var(--radius-sm)', padding: '7px 12px', fontSize: 12.5,
                        fontWeight: 500, cursor: applying !== null ? 'not-allowed' : 'pointer',
                        fontFamily: "'DM Sans', sans-serif", opacity: applying !== null && applying !== p.index ? 0.5 : 1,
                      }}
                    >
                      <IconCheck size={13} stroke={1.5} />
                      {applying === p.index ? 'Application…' : 'Appliquer cette variante'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {!loading && proposals.length > 1 && (
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 12 }}>
              Les affectations en pointillé violet diffèrent d'une variante à l'autre.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

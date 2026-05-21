import { useState } from 'react'
import { eventsApi } from '../../api/events.js'
import '../../styles/planning.css'

export default function PlanningGrid({
  event,
  slots,
  members,
  assignments,
  affinities,
  onAssignmentChange,
  eventId,
  disabled,
}) {
  const [editCell, setEditCell] = useState(null)
  const [cellLoading, setCellLoading] = useState(null)
  const [cellError, setCellError] = useState(null)

  const asgMap = {}
  for (const a of assignments) {
    asgMap[`${a.membre_id}-${a.creneau_id}`] = a
  }

  const affSet = new Set()
  for (const aff of affinities) {
    affSet.add(`${aff.membre_a_id}-${aff.membre_b_id}`)
    affSet.add(`${aff.membre_b_id}-${aff.membre_a_id}`)
  }

  const assignedMemberIds = new Set(assignments.map((a) => a.membre_id))
  const visibleMembers = members
    .filter((m) => assignedMemberIds.has(m.id))
    .sort((a, b) => a.nom.localeCompare(b.nom))

  const slotTotals = {}
  for (const a of assignments) {
    slotTotals[a.creneau_id] = (slotTotals[a.creneau_id] || 0) + 1
  }

  const fmtTime = (dt) =>
    new Date(dt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })

  const getCellClass = (asgn) => {
    if (!asgn) return ''
    if (asgn.type === 'respo_bar') return 'cell-respo'
    return 'cell-staff'
  }

  const getCellLabel = (asgn) => {
    if (!asgn) return ''
    if (asgn.type === 'respo_bar') return 'Respo'
    return asgn.maybe_force ? 'Maybe' : 'Staff'
  }

  const slotMemberIds = {}
  for (const a of assignments) {
    if (!slotMemberIds[a.creneau_id]) slotMemberIds[a.creneau_id] = new Set()
    slotMemberIds[a.creneau_id].add(a.membre_id)
  }

  const affinityOnSlot = (memberId, slotId) => {
    const others = slotMemberIds[slotId] || new Set()
    for (const otherId of others) {
      if (otherId !== memberId && affSet.has(`${memberId}-${otherId}`)) return true
    }
    return false
  }

  const handleCellClick = (memberId, slotId) => {
    if (disabled) return
    setEditCell({ memberId, slotId })
  }

  const handleAssign = async (memberId, slotId, type) => {
    const key = `${memberId}-${slotId}`
    setCellLoading(key)
    setCellError(null)
    try {
      if (type === 'none') {
        const existing = asgMap[key]
        if (existing) await eventsApi.deleteAssignment(eventId, existing.id)
      } else {
        const existing = asgMap[key]
        if (existing) {
          await eventsApi.updateAssignment(eventId, existing.id, { type })
        } else {
          await eventsApi.addAssignment(eventId, { creneau_id: slotId, membre_id: memberId, type })
        }
      }
      const fresh = await eventsApi.listAssignments(eventId)
      onAssignmentChange(fresh)
    } catch (err) {
      setCellError({ memberId, slotId, message: err.response?.data?.detail || "Erreur lors de l'affectation" })
    } finally {
      setCellLoading(null)
      setEditCell(null)
    }
  }

  if (visibleMembers.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)', fontSize: 12 }}>
        Aucune affectation. Lancez la génération automatique.
      </div>
    )
  }

  return (
    <div>
      <div className="planning-wrapper">
        <div style={{ overflowX: 'auto' }}>
          <table className="planning-table">
            <thead>
              <tr>
                <th>Membre</th>
                {slots.map((s) => (
                  <th key={s.id}>
                    <div>{new Date(s.heure_debut).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })}</div>
                    <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, opacity: 0.75, fontWeight: 400 }}>
                      {fmtTime(s.heure_debut)}–{fmtTime(s.heure_fin)}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleMembers.map((member) => (
                <tr key={member.id}>
                  <td>
                    {member.prenom} {member.nom}
                    {member.roles?.includes('bureau') && (
                      <span className="bureau-dot" title="Bureau" />
                    )}
                  </td>
                  {slots.map((slot) => {
                    const asgn = asgMap[`${member.id}-${slot.id}`]
                    const cellKey = `${member.id}-${slot.id}`
                    const isEditing = editCell?.memberId === member.id && editCell?.slotId === slot.id
                    const isLoading = cellLoading === cellKey
                    const satisfied = asgn ? affinityOnSlot(member.id, slot.id) : false
                    return (
                      <td
                        key={slot.id}
                        className={getCellClass(asgn)}
                        onClick={() => handleCellClick(member.id, slot.id)}
                        style={{ cursor: !disabled ? 'pointer' : 'default', opacity: isLoading ? 0.5 : 1, position: 'relative' }}
                      >
                        {asgn && (
                          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                            <span>{getCellLabel(asgn)}</span>
                            {satisfied && (
                              <span style={{ fontSize: 10, color: 'var(--violet)' }} title="Affinité satisfaite">♥</span>
                            )}
                            {asgn.maybe_force && (
                              <span style={{ fontSize: 10, color: 'var(--amber)' }} title="Forcé (maybe)">!</span>
                            )}
                          </div>
                        )}

                        {isEditing && !disabled && (
                          <div
                            style={{
                              position: 'absolute',
                              zIndex: 30,
                              background: 'var(--bg-elevated)',
                              border: '1px solid var(--border-mid)',
                              borderRadius: 'var(--radius-md)',
                              padding: 6,
                              left: 0,
                              top: '100%',
                              marginTop: 4,
                              minWidth: 130,
                            }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button onClick={() => handleAssign(member.id, slot.id, 'staff')} style={editorBtn('var(--green-soft)', 'var(--green)')}>
                              Staff
                            </button>
                            {event.type === 'soiree' && (
                              <button onClick={() => handleAssign(member.id, slot.id, 'respo_bar')} style={editorBtn('var(--red-soft)', 'var(--red)')}>
                                Respo bar
                              </button>
                            )}
                            {asgn && (
                              <button onClick={() => handleAssign(member.id, slot.id, 'none')} style={editorBtn('transparent', 'var(--text-muted)')}>
                                Retirer
                              </button>
                            )}
                            <button
                              onClick={() => setEditCell(null)}
                              style={{ ...editorBtn('transparent', 'var(--text-muted)'), borderTop: '1px solid var(--border)', marginTop: 2, paddingTop: 6 }}
                            >
                              Annuler
                            </button>
                          </div>
                        )}

                        {cellError?.memberId === member.id && cellError?.slotId === slot.id && (
                          <div style={{
                            position: 'absolute', zIndex: 40, left: 0, top: '100%', marginTop: 4,
                            background: 'var(--red-soft)', border: '1px solid rgba(240,82,82,0.3)',
                            borderRadius: 'var(--radius-sm)', padding: '4px 8px', fontSize: 11,
                            color: 'var(--red)', whiteSpace: 'nowrap',
                          }}>
                            {cellError.message}
                          </div>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td>Total staffés</td>
                {slots.map((s) => (
                  <td key={s.id}>{slotTotals[s.id] || 0}</td>
                ))}
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, padding: '10px 14px 4px', flexWrap: 'wrap' }}>
        <LegendItem color="rgba(52,199,123,0.25)" border="rgba(52,199,123,0.4)" label="Staff" />
        <LegendItem color="rgba(240,82,82,0.2)" border="rgba(240,82,82,0.4)" label="Respo bar" />
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
          <span style={{ color: 'var(--violet)', fontSize: 12 }}>♥</span>
          Affinité satisfaite
        </div>
        {!disabled && (
          <span style={{ fontSize: 11, color: 'var(--accent)', marginLeft: 'auto' }}>
            Cliquez sur une cellule pour modifier
          </span>
        )}
      </div>
    </div>
  )
}

function LegendItem({ color, border, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
      <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 3, background: color, border: `1px solid ${border}` }} />
      {label}
    </div>
  )
}

const editorBtn = (bg, color) => ({
  display: 'block',
  width: '100%',
  textAlign: 'left',
  padding: '5px 10px',
  fontSize: 11,
  background: bg,
  color,
  border: 'none',
  borderRadius: 4,
  cursor: 'pointer',
  fontFamily: "'DM Sans', sans-serif",
  transition: 'background 120ms ease',
})

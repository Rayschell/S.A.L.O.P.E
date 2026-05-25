import { useState, useEffect, useRef } from 'react'
import { eventsApi } from '../../api/events.js'
import '../../styles/planning.css'

export default function PlanningGrid({
  event,
  slots,
  members,
  assignments,
  affinities,
  availabilities = [],
  onAssignmentChange,
  eventId,
  disabled,
}) {
  const [editCell, setEditCell] = useState(null) // { memberId, slotId, x, y }
  const [cellLoading, setCellLoading] = useState(null)
  const [cellError, setCellError] = useState(null)
  const popupRef = useRef(null)

  // Close popup on outside click
  useEffect(() => {
    if (!editCell) return
    const onDown = (e) => {
      if (popupRef.current && !popupRef.current.contains(e.target)) setEditCell(null)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [editCell])

  // Auto-dismiss error after 3.5s
  useEffect(() => {
    if (!cellError) return
    const t = setTimeout(() => setCellError(null), 3500)
    return () => clearTimeout(t)
  }, [cellError])

  // Build a set of (membre_id, creneau_id) where statut = 'no'
  const noDispoSet = new Set(
    availabilities.filter((a) => a.statut === 'no').map((a) => `${a.membre_id}-${a.creneau_id}`)
  )

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
    return 'Staff'
  }

  const handleCellClick = (e, memberId, slotId) => {
    if (disabled) return
    setCellError(null)
    const key = `${memberId}-${slotId}`
    if (!asgMap[key] && noDispoSet.has(key)) {
      setCellError({ memberId, slotId, message: 'Ce membre est indisponible sur ce créneau' })
      return
    }
    if (editCell?.memberId === memberId && editCell?.slotId === slotId) {
      setEditCell(null)
      return
    }
    const rect = e.currentTarget.getBoundingClientRect()
    setEditCell({ memberId, slotId, x: rect.left, y: rect.bottom + 6 })
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
      <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)', fontSize: 15 }}>
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
                    <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 14, fontWeight: 500 }}>
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
                    const isLoading = cellLoading === cellKey
                    const isEditing = editCell?.memberId === member.id && editCell?.slotId === slot.id
                    return (
                      <td
                        key={slot.id}
                        className={getCellClass(asgn)}
                        onClick={(e) => handleCellClick(e, member.id, slot.id)}
                        style={{ cursor: !disabled ? 'pointer' : 'default', opacity: isLoading ? 0.5 : 1, position: 'relative' }}
                      >
                        {asgn && <span>{getCellLabel(asgn)}</span>}

                        {cellError?.memberId === member.id && cellError?.slotId === slot.id && (
                          <div style={{
                            position: 'fixed', zIndex: 40,
                            left: editCell?.x ?? 0, top: (editCell?.y ?? 0),
                            background: 'var(--red-soft)', border: '1px solid rgba(240,82,82,0.3)',
                            borderRadius: 'var(--radius-sm)', padding: '5px 10px', fontSize: 13,
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

      {/* Fixed popup for cell editing */}
      {editCell && !disabled && (() => {
        const asgn = asgMap[`${editCell.memberId}-${editCell.slotId}`]
        return (
          <div
            ref={popupRef}
            onMouseDown={(e) => e.stopPropagation()}
            style={{
              position: 'fixed',
              zIndex: 9999,
              left: editCell.x,
              top: editCell.y,
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-mid)',
              borderRadius: 'var(--radius-md)',
              padding: 6,
              minWidth: 130,
              boxShadow: '0 4px 16px rgba(0,0,0,0.35)',
            }}
          >
            <button onClick={() => handleAssign(editCell.memberId, editCell.slotId, 'staff')} style={editorBtn('var(--green-soft)', 'var(--green)')}>
              Staff
            </button>
            {event.type === 'soiree' && (
              <button onClick={() => handleAssign(editCell.memberId, editCell.slotId, 'respo_bar')} style={editorBtn('var(--red-soft)', 'var(--red)')}>
                Respo bar
              </button>
            )}
            {asgn && (
              <button onClick={() => handleAssign(editCell.memberId, editCell.slotId, 'none')} style={editorBtn('transparent', 'var(--text-muted)')}>
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
        )
      })()}

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, padding: '10px 14px 4px', flexWrap: 'wrap' }}>
        {!disabled && (
          <span style={{ fontSize: 14, color: 'var(--accent)', marginLeft: 'auto' }}>
            Cliquez sur une cellule pour modifier
          </span>
        )}
      </div>
    </div>
  )
}

const editorBtn = (bg, color) => ({
  display: 'block',
  width: '100%',
  textAlign: 'left',
  padding: '7px 12px',
  fontSize: 14,
  background: bg,
  color,
  border: 'none',
  borderRadius: 4,
  cursor: 'pointer',
  fontFamily: "'DM Sans', sans-serif",
  transition: 'background 120ms ease',
})

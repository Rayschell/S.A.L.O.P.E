import { useState } from 'react'
import { eventsApi } from '../../api/events.js'

/**
 * PlanningGrid — read/write planning table.
 *
 * Columns = slots, Rows = members with at least one assignment or availability.
 * Cell colours: green = staff, red = respo_bar, white = unassigned.
 * Clicking a cell (bureau only) opens an inline editor.
 */
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
  const [editCell, setEditCell] = useState(null) // {memberId, slotId}
  const [cellLoading, setCellLoading] = useState(null)
  const [cellError, setCellError] = useState(null) // {memberId, slotId, message}

  // Build quick lookup maps
  const asgMap = {} // key = `${memberId}-${slotId}` -> assignment
  for (const a of assignments) {
    asgMap[`${a.membre_id}-${a.creneau_id}`] = a
  }

  const affSet = new Set()
  for (const aff of affinities) {
    affSet.add(`${aff.membre_a_id}-${aff.membre_b_id}`)
    affSet.add(`${aff.membre_b_id}-${aff.membre_a_id}`)
  }

  // Only show members who have at least one assignment
  const assignedMemberIds = new Set(assignments.map((a) => a.membre_id))
  const visibleMembers = members
    .filter((m) => assignedMemberIds.has(m.id))
    .sort((a, b) => a.nom.localeCompare(b.nom))

  // Totals per slot
  const slotTotals = {}
  for (const a of assignments) {
    slotTotals[a.creneau_id] = (slotTotals[a.creneau_id] || 0) + 1
  }

  const fmtTime = (dt) =>
    new Date(dt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })

  const getCellColor = (asgn) => {
    if (!asgn) return 'bg-white'
    if (asgn.type === 'respo_bar') return 'bg-red-200 border-red-400'
    return 'bg-green-200 border-green-400'
  }

  const getCellLabel = (asgn) => {
    if (!asgn) return ''
    if (asgn.type === 'respo_bar') return 'Respo'
    return asgn.maybe_force ? 'Maybe' : 'Staff'
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
        if (existing) {
          await eventsApi.deleteAssignment(eventId, existing.id)
        }
      } else {
        const existing = asgMap[key]
        if (existing) {
          await eventsApi.updateAssignment(eventId, existing.id, { type })
        } else {
          await eventsApi.addAssignment(eventId, {
            creneau_id: slotId,
            membre_id: memberId,
            type,
          })
        }
      }
      const fresh = await eventsApi.listAssignments(eventId)
      onAssignmentChange(fresh)
    } catch (err) {
      const msg = err.response?.data?.detail || 'Erreur lors de l\'affectation'
      setCellError({ memberId, slotId, message: msg })
    } finally {
      setCellLoading(null)
      setEditCell(null)
    }
  }

  // Check if two members have affinity
  const haveAffinity = (id1, id2) => affSet.has(`${id1}-${id2}`)

  // For a given slot, find all member IDs assigned
  const slotMemberIds = {}
  for (const a of assignments) {
    if (!slotMemberIds[a.creneau_id]) slotMemberIds[a.creneau_id] = new Set()
    slotMemberIds[a.creneau_id].add(a.membre_id)
  }

  // Check if affinity satisfied for a member on a slot
  const affinityOnSlot = (memberId, slotId) => {
    const others = slotMemberIds[slotId] || new Set()
    for (const otherId of others) {
      if (otherId !== memberId && haveAffinity(memberId, otherId)) return true
    }
    return false
  }

  if (visibleMembers.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400 text-sm">
        Aucune affectation. Lancez la génération automatique.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 shadow bg-white">
      <table className="text-xs border-collapse w-full">
        <thead>
          <tr className="bg-blue-700 text-white">
            <th className="px-3 py-3 text-left min-w-[140px] font-semibold">Membre</th>
            {slots.map((s) => (
              <th key={s.id} className="px-2 py-3 text-center min-w-[80px] font-medium border-l border-blue-600">
                <div>{new Date(s.heure_debut).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })}</div>
                <div className="text-blue-200 font-normal">
                  {fmtTime(s.heure_debut)}-{fmtTime(s.heure_fin)}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {visibleMembers.map((member, rowIdx) => (
            <tr
              key={member.id}
              className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
            >
              <td className="px-3 py-2 font-medium text-gray-800 whitespace-nowrap">
                {member.prenom} {member.nom}
                {member.roles?.includes('bureau') && (
                  <span className="ml-1 text-xs bg-blue-100 text-blue-700 px-1 rounded">B</span>
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
                    onClick={() => handleCellClick(member.id, slot.id)}
                    className={`px-2 py-1 text-center border-l border-gray-100 relative transition-colors
                      ${getCellColor(asgn)}
                      ${!disabled ? 'cursor-pointer hover:opacity-80' : ''}
                      ${isLoading ? 'opacity-50' : ''}
                    `}
                  >
                    {asgn ? (
                      <div className="flex flex-col items-center">
                        <span className="font-semibold text-gray-700">{getCellLabel(asgn)}</span>
                        {satisfied && <span title="Affinité satisfaite" className="text-purple-500">💜</span>}
                        {asgn.maybe_force && <span title="Forcé (maybe)" className="text-orange-500">⚠</span>}
                      </div>
                    ) : null}

                    {/* Inline editor */}
                    {isEditing && !disabled && (
                      <div
                        className="absolute z-30 bg-white border border-gray-200 rounded-lg shadow-lg p-2 left-0 top-full mt-1 min-w-[120px]"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          className="block w-full text-left px-3 py-1.5 text-xs rounded hover:bg-green-50 text-green-800"
                          onClick={() => handleAssign(member.id, slot.id, 'staff')}
                        >
                          ✅ Staff
                        </button>
                        {event.type === 'soiree' && (
                          <button
                            className="block w-full text-left px-3 py-1.5 text-xs rounded hover:bg-red-50 text-red-700"
                            onClick={() => handleAssign(member.id, slot.id, 'respo_bar')}
                          >
                            🔴 Respo bar
                          </button>
                        )}
                        {asgn && (
                          <button
                            className="block w-full text-left px-3 py-1.5 text-xs rounded hover:bg-gray-50 text-gray-600"
                            onClick={() => handleAssign(member.id, slot.id, 'none')}
                          >
                            ✖ Retirer
                          </button>
                        )}
                        <button
                          className="block w-full text-left px-3 py-1.5 text-xs rounded hover:bg-gray-50 text-gray-400 mt-1 border-t"
                          onClick={() => setEditCell(null)}
                        >
                          Annuler
                        </button>
                      </div>
                    )}
                    {/* Inline error for this cell */}
                    {cellError?.memberId === member.id && cellError?.slotId === slot.id && (
                      <div className="absolute z-40 left-0 top-full mt-1 bg-red-50 border border-red-300 rounded px-2 py-1 text-xs text-red-700 whitespace-nowrap shadow">
                        {cellError.message}
                      </div>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}

          {/* Total row */}
          <tr className="bg-gray-100 font-semibold text-gray-700">
            <td className="px-3 py-2 text-xs uppercase tracking-wide">Total ✓ voix</td>
            {slots.map((s) => (
              <td key={s.id} className="px-2 py-2 text-center text-sm border-l border-gray-200">
                {slotTotals[s.id] || 0}
              </td>
            ))}
          </tr>
        </tbody>
      </table>

      {/* Legend */}
      <div className="flex gap-4 px-4 py-2 border-t border-gray-100 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="inline-block w-4 h-4 rounded bg-green-200 border border-green-400"></span> Staff
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-4 h-4 rounded bg-red-200 border border-red-400"></span> Respo bar
        </span>
        <span>💜 Affinité satisfaite</span>
        <span>⚠ Forcé (maybe)</span>
        {!disabled && <span className="text-blue-600">Cliquez sur une cellule pour modifier</span>}
      </div>
    </div>
  )
}

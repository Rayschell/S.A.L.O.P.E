import { useEffect, useMemo, useRef, useState } from 'react'
import { IconAlertTriangle, IconAlertCircle, IconInfoCircle, IconWand } from '@tabler/icons-react'
import { eventsApi } from '../../api/events.js'
import { popupPos } from '../../utils/popupPos.js'

const WARNING_LABELS = {
  no_respo_bar: 'Respo bar manquant',
  slot_understaffed: 'Créneau sous-effectif',
  no_bureau: 'Aucun membre bureau',
  maybe_forced: 'Disponibilité "maybe" forcée',
  affinity_unsatisfied: 'Affinité non satisfaite',
  over_quota: 'Quota dépassé (escalade)',
  long_pause: 'Pause 2h entre blocs (info)',
  no_slots: 'Info',
}

const WARNING_STYLE = {
  no_respo_bar: { bg: 'var(--red-soft)', border: 'rgba(240, 82, 82,0.2)', color: 'var(--red)', Icon: IconAlertCircle },
  slot_understaffed: { bg: 'var(--amber-soft)', border: 'rgba(245, 158, 11,0.2)', color: 'var(--amber)', Icon: IconAlertTriangle },
  maybe_forced: { bg: 'var(--amber-soft)', border: 'rgba(245, 158, 11,0.2)', color: 'var(--amber)', Icon: IconAlertTriangle },
  over_quota: { bg: 'var(--red-soft)', border: 'rgba(240, 82, 82,0.2)', color: 'var(--red)', Icon: IconAlertCircle },
  no_bureau: { bg: 'var(--accent-soft)', border: 'rgba(91, 127, 166,0.2)', color: 'var(--accent)', Icon: IconInfoCircle },
  affinity_unsatisfied: { bg: 'var(--violet-soft)', border: 'rgba(124, 106, 247,0.2)', color: 'var(--violet)', Icon: IconInfoCircle },
  long_pause: { bg: 'rgba(255,255,255,0.04)', border: 'var(--border)', color: 'var(--text-muted)', Icon: IconInfoCircle },
  no_slots: { bg: 'rgba(255,255,255,0.04)', border: 'var(--border)', color: 'var(--text-muted)', Icon: IconInfoCircle },
}

const DEFAULT_STYLE = { bg: 'rgba(255,255,255,0.04)', border: 'var(--border)', color: 'var(--text-muted)', Icon: IconInfoCircle }

export default function WarningsList({
  warnings,
  slots = [],
  members = [],
  availabilities = [],
  assignments = [],
  resposBar = [],
  excludedMemberIds,
  eventId,
  disabled = true,
  onSelect,
  onAssignmentChange,
  onUndoableAction,
}) {
  const [popover, setPopover] = useState(null) // { groups, x, y }
  const [busy, setBusy] = useState(false)
  const popoverRef = useRef(null)

  useEffect(() => {
    if (!popover) return
    const onDown = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) setPopover(null)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [popover])

  const availMap = useMemo(() => {
    const m = {}
    for (const a of availabilities) m[`${a.membre_id}-${a.creneau_id}`] = a.statut
    return m
  }, [availabilities])

  const membersById = useMemo(() => {
    const m = {}
    for (const mb of members) m[mb.id] = mb
    return m
  }, [members])

  if (warnings.length === 0) return null

  const excluded = excludedMemberIds instanceof Set
    ? excludedMemberIds
    : new Set(excludedMemberIds || [])

  const memberHours = {}
  for (const a of assignments) memberHours[a.membre_id] = (memberHours[a.membre_id] || 0) + 1
  const assignedOnSlot = (slotId) =>
    new Set(assignments.filter((a) => a.creneau_id === slotId).map((a) => a.membre_id))

  const dispoCandidates = (slotId, filterFn = () => true) => {
    const assigned = assignedOnSlot(slotId)
    return members
      .filter((m) => filterFn(m) && !assigned.has(m.id) && !excluded.has(m.id))
      .map((m) => ({ member: m, dispo: availMap[`${m.id}-${slotId}`] }))
      .filter((c) => c.dispo === 'yes' || c.dispo === 'maybe')
      .sort((a, b) =>
        a.dispo === b.dispo
          ? (memberHours[a.member.id] || 0) - (memberHours[b.member.id] || 0)
          : a.dispo === 'yes' ? -1 : 1
      )
  }

  // Groupes d'actions « Corriger » pour un warning donné (null si aucune action)
  const getFixGroups = (w) => {
    if (disabled || !eventId || w.slot_id == null) return null

    if (w.type === 'slot_understaffed') {
      const items = dispoCandidates(w.slot_id).map((c) => ({
        kind: 'add', type: 'staff', member: c.member, dispo: c.dispo, creneau_id: w.slot_id,
      }))
      return items.length ? [{ label: 'Disponibles non placés', items }] : null
    }

    if (w.type === 'no_respo_bar') {
      const candidateIds = new Set([
        ...resposBar.map((r) => r.membre_id),
        ...members.filter((m) => m.roles?.includes('bureau')).map((m) => m.id),
      ])
      const groups = []
      const onSlot = assignments
        .filter((a) => a.creneau_id === w.slot_id && a.type === 'staff' && candidateIds.has(a.membre_id))
        .map((a) => ({
          kind: 'promote', asgnId: a.id, member: membersById[a.membre_id], creneau_id: w.slot_id,
        }))
        .filter((x) => x.member)
      if (onSlot.length) groups.push({ label: 'Déjà sur le créneau', items: onSlot })
      const dispo = dispoCandidates(w.slot_id, (m) => candidateIds.has(m.id)).map((c) => ({
        kind: 'add', type: 'respo_bar', member: c.member, dispo: c.dispo, creneau_id: w.slot_id,
      }))
      if (dispo.length) groups.push({ label: 'Disponibles', items: dispo })
      return groups.length ? groups : null
    }

    if (w.type === 'no_bureau') {
      const items = dispoCandidates(w.slot_id, (m) => m.roles?.includes('bureau')).map((c) => ({
        kind: 'add', type: 'staff', member: c.member, dispo: c.dispo, creneau_id: w.slot_id,
      }))
      return items.length ? [{ label: 'Bureau disponibles', items }] : null
    }

    return null
  }

  const openFix = (e, groups) => {
    e.stopPropagation()
    const rect = e.currentTarget.getBoundingClientRect()
    setPopover({ groups, ...popupPos(rect, 240, 280) })
  }

  const runFix = async (item) => {
    setBusy(true)
    try {
      if (item.kind === 'promote') {
        await eventsApi.updateAssignment(eventId, item.asgnId, { type: 'respo_bar' })
        onUndoableAction?.([{ op: 'update', creneau_id: item.creneau_id, membre_id: item.member.id, type: 'staff' }])
      } else {
        await eventsApi.addAssignment(eventId, {
          creneau_id: item.creneau_id, membre_id: item.member.id, type: item.type,
        })
        onUndoableAction?.([{ op: 'delete', creneau_id: item.creneau_id, membre_id: item.member.id }])
      }
      const fresh = await eventsApi.listAssignments(eventId)
      onAssignmentChange?.(fresh)
      setPopover(null)
    } catch {
      // l'intercepteur axios affiche déjà l'erreur en toast
    } finally {
      setBusy(false)
    }
  }

  const grouped = {}
  for (const w of warnings) {
    if (!grouped[w.type]) grouped[w.type] = []
    grouped[w.type].push(w)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Replié par défaut sur téléphone pour ne pas repousser la grille */}
      <details open={!window.matchMedia('(max-width: 767px)').matches}>
      <summary style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500, cursor: 'pointer', marginBottom: 8 }}>
        {warnings.length} avertissement(s) après génération
      </summary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {Object.entries(grouped).map(([type, items]) => {
        const { bg, border, color, Icon } = WARNING_STYLE[type] || DEFAULT_STYLE
        return (
          <div
            key={type}
            style={{
              background: bg,
              border: `1px solid ${border}`,
              borderRadius: 'var(--radius-sm)',
              padding: '10px 14px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: items.length > 1 ? 6 : 0 }}>
              <Icon size={13} stroke={1.5} color={color} />
              <span style={{ fontSize: 12, fontWeight: 500, color }}>
                {WARNING_LABELS[type] || type} ({items.length})
              </span>
            </div>
            {items.map((w, i) => {
              const clickable = onSelect && (w.slot_id != null || w.member_id != null)
              const fixGroups = getFixGroups(w)
              return (
                <p
                  key={i}
                  onClick={clickable ? () => onSelect(w) : undefined}
                  title={clickable ? 'Voir dans la grille' : undefined}
                  style={{
                    fontSize: 11,
                    color: 'var(--text-secondary)',
                    marginTop: 3,
                    paddingLeft: 20,
                    cursor: clickable ? 'pointer' : 'default',
                    textDecoration: clickable ? 'underline dotted' : 'none',
                    textUnderlineOffset: 3,
                  }}
                >
                  · {w.message}
                  {fixGroups && (
                    <button
                      onClick={(e) => openFix(e, fixGroups)}
                      title="Proposer une correction"
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        marginLeft: 8, padding: '1px 8px', fontSize: 10,
                        background: 'var(--bg-elevated)', color,
                        border: `1px solid ${border}`, borderRadius: 99,
                        cursor: 'pointer', fontFamily: "'DM Sans', sans-serif",
                        verticalAlign: 'middle',
                      }}
                    >
                      <IconWand size={10} stroke={1.5} />
                      Corriger
                    </button>
                  )}
                </p>
              )
            })}
          </div>
        )
      })}
      </div>
      </details>

      {/* Popover de correction */}
      {popover && (
        <div
          ref={popoverRef}
          onMouseDown={(e) => e.stopPropagation()}
          style={{
            position: 'fixed', zIndex: 9999, left: popover.x, top: popover.y,
            background: 'var(--bg-elevated)', border: '1px solid var(--border-mid)',
            borderRadius: 'var(--radius-md)', padding: 6, minWidth: 230, maxHeight: 280,
            overflowY: 'auto', boxShadow: '0 4px 16px rgba(0,0,0,0.35)',
            opacity: busy ? 0.6 : 1, pointerEvents: busy ? 'none' : 'auto',
          }}
        >
          {popover.groups.map((g) => (
            <div key={g.label}>
              <div style={{
                fontSize: 10, fontFamily: 'DM Mono, monospace', textTransform: 'uppercase',
                letterSpacing: '0.07em', color: 'var(--text-muted)', padding: '6px 10px 3px',
              }}>
                {g.label}
              </div>
              {g.items.map((item) => (
                <button
                  key={`${item.kind}-${item.member.id}`}
                  onClick={() => runFix(item)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                    textAlign: 'left', padding: '6px 10px', fontSize: 13,
                    background: 'transparent', color: 'var(--text-primary)',
                    border: 'none', borderRadius: 4, cursor: 'pointer',
                    fontFamily: "'DM Sans', sans-serif",
                  }}
                  className="hover-high"
                >
                  {item.member.prenom} {item.member.nom}
                  <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-muted)' }}>
                    {item.kind === 'promote' ? 'passer respo' : item.dispo === 'maybe' ? 'maybe' : ''}
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

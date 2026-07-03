/**
 * Recalcule les warnings W1–W7 à partir de l'état courant du planning,
 * pour qu'ils restent justes après les ajustements manuels (les warnings
 * retournés par la génération deviennent obsolètes dès la première édition).
 * Mêmes codes que le backend (scheduler.py) → réutilisés par WarningsList.
 */
export function computeWarnings({ event, slots, assignments, members, availabilities, affinities }) {
  const warnings = []
  const sorted = [...slots].sort((a, b) => new Date(a.heure_debut) - new Date(b.heure_debut))
  const fmt = (dt) => new Date(dt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })

  const memberMap = new Map(members.map((m) => [m.id, m]))
  const name = (id) => {
    const m = memberMap.get(id)
    return m ? `${m.prenom} ${m.nom}` : `membre #${id}`
  }

  const bySlot = new Map()
  const byMember = new Map()
  for (const a of assignments) {
    if (!bySlot.has(a.creneau_id)) bySlot.set(a.creneau_id, [])
    bySlot.get(a.creneau_id).push(a)
    if (!byMember.has(a.membre_id)) byMember.set(a.membre_id, [])
    byMember.get(a.membre_id).push(a)
  }
  const availMap = new Map(availabilities.map((a) => [`${a.membre_id}-${a.creneau_id}`, a.statut]))

  for (const s of sorted) {
    const asgns = bySlot.get(s.id) || []
    if (asgns.length < s.max_personnes) {
      warnings.push({
        type: 'slot_understaffed', slot_id: s.id, member_id: null,
        message: `Créneau ${fmt(s.heure_debut)} : ${asgns.length}/${s.max_personnes} staffé·e·s (W2)`,
      })
    }
    if (event.type === 'soiree' && !asgns.some((a) => a.type === 'respo_bar')) {
      warnings.push({
        type: 'no_respo_bar', slot_id: s.id, member_id: null,
        message: `Créneau ${fmt(s.heure_debut)} : aucun respo bar (W1)`,
      })
    }
    if (asgns.length > 0 && !asgns.some((a) => memberMap.get(a.membre_id)?.roles?.includes('bureau'))) {
      warnings.push({
        type: 'no_bureau', slot_id: s.id, member_id: null,
        message: `Créneau ${fmt(s.heure_debut)} : aucun membre bureau (W3)`,
      })
    }
    for (const a of asgns) {
      if (availMap.get(`${a.membre_id}-${a.creneau_id}`) === 'maybe') {
        warnings.push({
          type: 'maybe_forced', slot_id: s.id, member_id: a.membre_id,
          message: `Créneau ${fmt(s.heure_debut)} : ${name(a.membre_id)} placé sur « peut-être » (W5)`,
        })
      }
    }
  }

  // W4 (> 2 h) et W7 (pause entre deux blocs), par membre
  const slotIdx = new Map(sorted.map((s, i) => [s.id, i]))
  for (const [mid, asgns] of byMember) {
    if (asgns.length > 2) {
      warnings.push({
        type: 'over_quota', slot_id: null, member_id: mid,
        message: `${name(mid)} : ${asgns.length} h affectées (au-delà du quota de 2 h) — W4`,
      })
    }
    const idxs = asgns
      .map((a) => slotIdx.get(a.creneau_id))
      .filter((i) => i != null)
      .sort((x, y) => x - y)
    for (let k = 1; k < idxs.length; k++) {
      const gap = idxs[k] - idxs[k - 1] - 1
      if (gap >= 2) {
        warnings.push({
          type: 'long_pause', slot_id: null, member_id: mid,
          message: `${name(mid)} : pause de ${gap} h entre deux blocs (W7)`,
        })
      }
    }
  }

  // W6 : affinité satisfaite si les deux membres partagent au moins un créneau
  for (const aff of affinities || []) {
    const slotsA = new Set((byMember.get(aff.membre_a_id) || []).map((a) => a.creneau_id))
    const together = (byMember.get(aff.membre_b_id) || []).some((a) => slotsA.has(a.creneau_id))
    if (!together) {
      warnings.push({
        type: 'affinity_unsatisfied', slot_id: null, member_id: aff.membre_a_id,
        message: `Affinité non satisfaite : ${name(aff.membre_a_id)} & ${name(aff.membre_b_id)} (W6)`,
      })
    }
  }

  return warnings
}

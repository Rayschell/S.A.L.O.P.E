"""
Scheduling algorithm for bar event planning — CP-SAT solver (OR-Tools).

Only truly hard constraint: R6 — max_personnes per slot must be respected exactly
(or as close as possible if not enough available members).

Everything else is soft, expressed as weighted penalties in the objective:
  P_understaffed  — slot has fewer than max_personnes (weight 10000)
  P_no_bureau     — slot has no bureau member         (weight 500)
  P_no_respo      — soirée slot has no respo bar      (weight 800)
  P_long_pause    — member has a gap ≥3h between blocks (weight 200 per gap-hour)
  P_medium_pause  — member has a gap of 2h             (weight 50)
  P_quota_exceeded— member assigned > 2h               (weight 100 per extra hour)
  P_imbalance     — difference between max and min hours assigned (weight 300)
  P_maybe         — member placed on a "maybe" slot    (weight 30)
  P_no_2h_block   — member has an isolated 1h assignment when 2h was feasible (weight 20)

The solver finds the global optimum within a 10-second time limit, then falls back
to the best solution found if the optimum is not proven.

Warnings generated (same codes as before):
  W1 — no respo bar on a slot (soirée only)
  W2 — slot understaffed
  W3 — no bureau member on a slot
  W4 — member assigned beyond 2h base quota
  W5 — member placed despite "maybe" availability
  W6 — affinity constraint unsatisfied
  W7 — long pause (≥3h gap) between two assignment blocks
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from ortools.sat.python import cp_model
from sqlalchemy.orm import Session

from ..models.models import (
    AffinityConstraint,
    Assignment,
    AssignmentSourceEnum,
    AssignmentTypeEnum,
    Availability,
    Event,
    EventTypeEnum,
    Member,
    ResponsableBar,
    Slot,
    StatsMemberHeureRelative,
)


# ---------------------------------------------------------------------------
# Data structures (kept identical for API compatibility)
# ---------------------------------------------------------------------------


@dataclass
class WarningItem:
    type: str
    slot_id: Optional[int] = None
    member_id: Optional[int] = None
    message: str = ""


@dataclass
class _SlotAssignment:
    member_id: int
    asgn_type: str    # "staff" | "respo_bar"
    source: str       # "auto" | "manuel"
    maybe_force: bool = False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_schedule(db: Session, event_id: int) -> List[WarningItem]:
    """
    Generate (or regenerate) the automatic schedule for an event.
    Clears existing *auto* assignments and replaces them.
    Returns a list of WarningItem.
    """
    event: Optional[Event] = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise ValueError(f"Event {event_id} not found")

    slots: List[Slot] = sorted(
        db.query(Slot).filter(Slot.evenement_id == event_id).all(),
        key=lambda s: s.heure_debut,
    )
    if not slots:
        return [WarningItem(type="no_slots", message="Aucun créneau configuré")]

    n = len(slots)
    slot_id_to_idx: Dict[int, int] = {s.id: i for i, s in enumerate(slots)}

    all_members: List[Member] = db.query(Member).all()
    member_map: Dict[int, Member] = {m.id: m for m in all_members}

    # Availability: (member_id, slot_idx) -> "yes" | "no" | "maybe"
    avail: Dict[Tuple[int, int], str] = {}
    for av in db.query(Availability).filter(Availability.evenement_id == event_id).all():
        idx = slot_id_to_idx.get(av.creneau_id)
        if idx is not None:
            avail[(av.membre_id, idx)] = av.statut.value

    # Historical stats
    total_fois_staffe: Dict[int, int] = {m.id: 0 for m in all_members}
    for stat in db.query(StatsMemberHeureRelative).filter(
        StatsMemberHeureRelative.type_evenement == event.type
    ).all():
        total_fois_staffe[stat.membre_id] = (
            total_fois_staffe.get(stat.membre_id, 0) + stat.fois_staffe
        )

    # Affinity pairs (bidirectional)
    affinity_set: Set[Tuple[int, int]] = set()
    for ac in db.query(AffinityConstraint).filter(
        AffinityConstraint.evenement_id == event_id
    ).all():
        affinity_set.add((ac.membre_a_id, ac.membre_b_id))
        affinity_set.add((ac.membre_b_id, ac.membre_a_id))

    # Respo bar designated order
    respo_order: Dict[int, int] = {
        r.membre_id: r.ordre
        for r in db.query(ResponsableBar).filter(
            ResponsableBar.evenement_id == event_id
        ).all()
    }

    # ------------------------------------------------------------------
    # Remove previous auto assignments
    # ------------------------------------------------------------------
    for slot in slots:
        db.query(Assignment).filter(
            Assignment.creneau_id == slot.id,
            Assignment.source == AssignmentSourceEnum.auto,
        ).delete(synchronize_session=False)
    db.flush()

    # ------------------------------------------------------------------
    # Load manual assignments (fixed, not touched by solver)
    # ------------------------------------------------------------------
    manual: Dict[Tuple[int, int], str] = {}  # (member_id, slot_idx) -> asgn_type
    for slot_idx, slot in enumerate(slots):
        for a in db.query(Assignment).filter(
            Assignment.creneau_id == slot.id,
            Assignment.source == AssignmentSourceEnum.manuel,
        ).all():
            manual[(a.membre_id, slot_idx)] = a.type.value

    # Members with at least one available slot
    eligible_members = [
        m for m in all_members
        if any(avail.get((m.id, s), "no") != "no" for s in range(n))
        or any((m.id, s) in manual for s in range(n))
    ]
    M = len(eligible_members)
    member_idx: Dict[int, int] = {m.id: i for i, m in enumerate(eligible_members)}

    # ------------------------------------------------------------------
    # Build CP-SAT model
    # ------------------------------------------------------------------
    model = cp_model.CpModel()

    # x[i][s] = 1 if member i is assigned to slot s
    x: List[List[cp_model.IntVar]] = [
        [model.new_bool_var(f"x_{i}_{s}") for s in range(n)]
        for i in range(M)
    ]

    # Fix manual assignments
    for (mid, s), _ in manual.items():
        if mid in member_idx:
            i = member_idx[mid]
            model.add(x[i][s] == 1)

    # Fix unavailable slots (avail == "no" and not manual)
    for i, m in enumerate(eligible_members):
        for s in range(n):
            if avail.get((m.id, s), "no") == "no" and (m.id, s) not in manual:
                model.add(x[i][s] == 0)

    # ------------------------------------------------------------------
    # Penalty variables
    # ------------------------------------------------------------------
    penalties: List[cp_model.LinearExprT] = []

    # --- P_understaffed & P_overstaffed (R6) ---
    # Soft understaffing (no members available → can't do better)
    # Hard overstaffing (never exceed max_personnes)
    for s in range(n):
        assigned_on_s = [x[i][s] for i in range(M)]
        # Hard: never exceed max_personnes
        model.add(sum(assigned_on_s) <= slots[s].max_personnes)
        # Soft: penalise falling short
        shortage = model.new_int_var(0, slots[s].max_personnes, f"shortage_{s}")
        model.add(shortage == slots[s].max_personnes - sum(assigned_on_s))
        penalties.append(10000 * shortage)

    # --- P_no_bureau (W3) ---
    bureau_indices = [i for i, m in enumerate(eligible_members)
                      if m.roles and "bureau" in m.roles]
    for s in range(n):
        no_bureau = model.new_bool_var(f"no_bureau_{s}")
        if bureau_indices:
            # no_bureau = 1 iff all bureau members are absent from slot s
            bureau_sum = sum(x[i][s] for i in bureau_indices)
            # bureau_sum == 0 → no_bureau == 1
            # bureau_sum >= 1 → no_bureau == 0
            model.add(bureau_sum + no_bureau >= 1)
            model.add(bureau_sum <= len(bureau_indices) * (1 - no_bureau))
        else:
            model.add(no_bureau == 1)
        penalties.append(500 * no_bureau)

    # --- P_no_respo (W1, soirée only) ---
    if event.type == EventTypeEnum.soiree:
        respo_candidates = [
            i for i, m in enumerate(eligible_members)
            if m.id in respo_order or (m.roles and "bureau" in m.roles)
        ]
        r: List[List[cp_model.IntVar]] = [
            [model.new_bool_var(f"r_{i}_{s}") for s in range(n)]
            for i in range(M)
        ]
        for i in range(M):
            for s in range(n):
                model.add(r[i][s] <= x[i][s])
                if i not in respo_candidates:
                    model.add(r[i][s] == 0)

        # At most 1 respo per slot
        for s in range(n):
            model.add(sum(r[i][s] for i in range(M)) <= 1)

        # At most 2h respo per member (one pair)
        for i in range(M):
            model.add(sum(r[i][s] for s in range(n)) <= 2)

        # No gaps: r[i][s]=1 and r[i][s+2]=1 implies r[i][s+1]=1
        # Prevents non-consecutive double respo (e.g. 04h + 06h without 05h)
        for i in range(M):
            for s in range(n - 2):
                model.add(r[i][s] + r[i][s + 2] <= 1 + r[i][s + 1])

        # Penalise uncovered slots (W1) — weight 800
        for s in range(n):
            no_respo = model.new_int_var(0, 1, f"no_respo_{s}")
            respo_sum = sum(r[i][s] for i in range(M))
            model.add(respo_sum + no_respo >= 1)
            model.add(respo_sum <= 1)
            penalties.append(800 * no_respo)

        # Penalise singleton respos (member covers only 1 slot instead of a 2h pair).
        # Weight 400 < 800: solver tolerates 1 singleton only when n is odd (unavoidable).
        # n even → 0 singletons (pairs cover all slots at 0 cost)
        # n odd  → exactly 1 singleton needed (400 < 800 for an uncovered slot)
        for i in range(M):
            for s in range(n):
                isolated = model.new_bool_var(f"iso_r_{i}_{s}")
                model.add(isolated <= r[i][s])
                adj: List[cp_model.IntVar] = []
                if s > 0:
                    adj.append(r[i][s - 1])
                    model.add(isolated <= 1 - r[i][s - 1])
                if s < n - 1:
                    adj.append(r[i][s + 1])
                    model.add(isolated <= 1 - r[i][s + 1])
                model.add(isolated >= r[i][s] - sum(adj))
                penalties.append(400 * isolated)
    else:
        r = None

    # --- P_long_pause / P_medium_pause (W7) ---
    # Penalise gaps at BLOCK BOUNDARIES only — no double counting.
    # gs[s]=1 if member assigned at s but NOT at s+1 (end of a block)
    # ge[s]=1 if member assigned at s but NOT at s-1 (start of a block)
    # Penalty fires only for pairs (s1, s2) where s1 is a block end and s2 a block start.
    for i in range(M):
        g_starts: List[cp_model.IntVar] = []
        g_ends: List[cp_model.IntVar] = []
        for s in range(n):
            gst = model.new_bool_var(f"gs_{i}_{s}")
            gen = model.new_bool_var(f"ge_{i}_{s}")
            if s < n - 1:
                model.add(gst <= x[i][s])
                model.add(gst <= 1 - x[i][s + 1])
                model.add(gst >= x[i][s] - x[i][s + 1])
            else:
                model.add(gst == x[i][s])
            if s > 0:
                model.add(gen <= x[i][s])
                model.add(gen <= 1 - x[i][s - 1])
                model.add(gen >= x[i][s] - x[i][s - 1])
            else:
                model.add(gen == x[i][s])
            g_starts.append(gst)
            g_ends.append(gen)

        for s1 in range(n - 1):
            for s2 in range(s1 + 2, n):
                gap = s2 - s1 - 1
                pair = model.new_bool_var(f"gp_{i}_{s1}_{s2}")
                model.add(pair <= g_starts[s1])
                model.add(pair <= g_ends[s2])
                model.add(pair >= g_starts[s1] + g_ends[s2] - 1)
                if gap >= 3:
                    weight = 200 * gap
                elif gap == 2:
                    weight = 150
                else:  # gap == 1 → 2h actual pause
                    weight = 60
                penalties.append(weight * pair)

    # --- R1: max 2 consecutive slots per member (soft) ---
    for i in range(M):
        for s in range(n - 2):
            triple = model.new_bool_var(f"triple_{i}_{s}")
            model.add(triple <= x[i][s])
            model.add(triple <= x[i][s + 1])
            model.add(triple <= x[i][s + 2])
            model.add(triple >= x[i][s] + x[i][s + 1] + x[i][s + 2] - 2)
            penalties.append(500 * triple)  # last resort: strongly discouraged

    # --- P_quota_exceeded (W4) ---
    # Progressive penalty:
    #   3rd hour (1st excess): bureau=80, non-bureau=300  → bureau preferred for first extension
    #   4th hour and beyond  : 600 for everyone           → strongly discourages stacking on one person
    # This makes Bureau@4h (80+600=680) more expensive than Bureau@3h + NonBureau@3h (80+300=380).
    base_quota = 2
    bureau_set = set(bureau_indices)
    for i in range(M):
        hours = sum(x[i][s] for s in range(n))
        excess = model.new_int_var(0, n, f"excess_{i}")
        model.add(excess >= hours - base_quota)
        model.add(excess >= 0)
        # First extra hour (3rd): cheap for bureau, expensive for non-bureau
        weight_first = 80 if i in bureau_set else 300
        penalties.append(weight_first * excess)
        # Additional extra hours (4th+): very expensive for everyone
        excess_beyond1 = model.new_int_var(0, n, f"excess_b1_{i}")
        model.add(excess_beyond1 >= excess - 1)
        model.add(excess_beyond1 >= 0)
        penalties.append(600 * excess_beyond1)

    # --- P_imbalance ---
    hours_vars = []
    for i in range(M):
        h = model.new_int_var(0, n, f"hours_{i}")
        model.add(h == sum(x[i][s] for s in range(n)))
        hours_vars.append(h)
    max_h = model.new_int_var(0, n, "max_h")
    min_h = model.new_int_var(0, n, "min_h")
    model.add_max_equality(max_h, hours_vars)
    model.add_min_equality(min_h, hours_vars)
    imbalance = model.new_int_var(0, n, "imbalance")
    model.add(imbalance == max_h - min_h)
    penalties.append(300 * imbalance)

    # --- P_maybe ---
    for i, m in enumerate(eligible_members):
        for s in range(n):
            if avail.get((m.id, s), "no") == "maybe" and (m.id, s) not in manual:
                penalties.append(30 * x[i][s])

    # --- P_no_2h_block: prefer adjacent placements (soft R4) ---
    # Reward consecutive pairs: subtract penalty for each consecutive pair
    for i in range(M):
        for s in range(n - 1):
            consec = model.new_bool_var(f"consec_{i}_{s}")
            model.add(consec <= x[i][s])
            model.add(consec <= x[i][s + 1])
            model.add(consec >= x[i][s] + x[i][s + 1] - 1)
            penalties.append(-15 * consec)  # negative = reward

    # ------------------------------------------------------------------
    # Objective: minimise total penalty
    # ------------------------------------------------------------------
    model.minimize(sum(penalties))

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 15.0
    solver.parameters.num_search_workers = 4
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [WarningItem(
            type="solver_failed",
            message="Le solveur n'a pas trouvé de solution. Vérifiez les disponibilités.",
        )]

    # ------------------------------------------------------------------
    # Extract solution
    # ------------------------------------------------------------------
    assignments: List[List[_SlotAssignment]] = [[] for _ in range(n)]

    # Manual assignments first
    for (mid, s), atype in manual.items():
        m = member_map.get(mid)
        av_status = avail.get((mid, s), "no")
        assignments[s].append(_SlotAssignment(
            member_id=mid,
            asgn_type=atype,
            source="manuel",
            maybe_force=(av_status == "maybe"),
        ))

    # Auto assignments from solver
    respo_assigned: Set[Tuple[int, int]] = set()
    if r is not None:
        for i in range(M):
            m = eligible_members[i]
            for s in range(n):
                if solver.value(r[i][s]) == 1:
                    respo_assigned.add((m.id, s))

    for i, m in enumerate(eligible_members):
        for s in range(n):
            if (m.id, s) in manual:
                continue
            if solver.value(x[i][s]) == 1:
                atype = "respo_bar" if (m.id, s) in respo_assigned else "staff"
                av_status = avail.get((m.id, s), "no")
                assignments[s].append(_SlotAssignment(
                    member_id=m.id,
                    asgn_type=atype,
                    source="auto",
                    maybe_force=(av_status == "maybe"),
                ))

    # ------------------------------------------------------------------
    # Persist auto assignments
    # ------------------------------------------------------------------
    for slot_idx, slot in enumerate(slots):
        for a in assignments[slot_idx]:
            if a.source != "auto":
                continue
            db.add(Assignment(
                creneau_id=slot.id,
                membre_id=a.member_id,
                type=AssignmentTypeEnum(a.asgn_type),
                source=AssignmentSourceEnum.auto,
                maybe_force=a.maybe_force,
            ))
    db.commit()

    # ------------------------------------------------------------------
    # Generate warnings W1-W7
    # ------------------------------------------------------------------
    return _generate_warnings(
        event, slots, member_map, assignments, affinity_set,
        solver, x, eligible_members, n, base_quota,
    )


# ---------------------------------------------------------------------------
# Warning generation
# ---------------------------------------------------------------------------


def _generate_warnings(
    event: Event,
    slots: List[Slot],
    member_map: Dict[int, Member],
    assignments: List[List[_SlotAssignment]],
    affinity_set: Set[Tuple[int, int]],
    solver: cp_model.CpSolver,
    x: List[List[cp_model.IntVar]],
    eligible_members: List[Member],
    n: int,
    base_quota: int,
) -> List[WarningItem]:
    warnings: List[WarningItem] = []
    slot_indices_by_member: Dict[int, Set[int]] = {}

    for slot_idx, slot in enumerate(slots):
        asgns = assignments[slot_idx]

        # W1
        if event.type == EventTypeEnum.soiree:
            if not any(a.asgn_type == "respo_bar" for a in asgns):
                warnings.append(WarningItem(
                    type="no_respo_bar",
                    slot_id=slot.id,
                    message=f"Créneau {slot.heure_debut.strftime('%H:%M')} : aucun respo bar (W1)",
                ))

        # W2
        if len(asgns) < slot.max_personnes:
            warnings.append(WarningItem(
                type="slot_understaffed",
                slot_id=slot.id,
                message=(
                    f"Créneau {slot.heure_debut.strftime('%H:%M')} : "
                    f"{len(asgns)}/{slot.max_personnes} personnes (W2)"
                ),
            ))

        # W3
        has_bureau = any(
            "bureau" in (member_map[a.member_id].roles or [])
            for a in asgns if a.member_id in member_map
        )
        if asgns and not has_bureau:
            warnings.append(WarningItem(
                type="no_bureau",
                slot_id=slot.id,
                message=f"Créneau {slot.heure_debut.strftime('%H:%M')} : aucun membre bureau (W3)",
            ))

        # W5
        for a in asgns:
            if a.maybe_force:
                m = member_map.get(a.member_id)
                name = f"{m.prenom} {m.nom}" if m else str(a.member_id)
                warnings.append(WarningItem(
                    type="maybe_forced",
                    slot_id=slot.id,
                    member_id=a.member_id,
                    message=f"Créneau {slot.heure_debut.strftime('%H:%M')} : {name} forcé (maybe) — W5",
                ))
            slot_indices_by_member.setdefault(a.member_id, set()).add(slot_idx)

    # W4
    for i, m in enumerate(eligible_members):
        total_h = len(slot_indices_by_member.get(m.id, set()))
        if total_h > base_quota:
            warnings.append(WarningItem(
                type="over_quota",
                member_id=m.id,
                message=f"{m.prenom} {m.nom} : {total_h}h affectées (palier 2) — W4",
            ))

    # W6
    processed: Set[frozenset] = set()
    for a_id, b_id in affinity_set:
        pair = frozenset([a_id, b_id])
        if pair in processed:
            continue
        processed.add(pair)
        a_slots = slot_indices_by_member.get(a_id, set())
        b_slots = slot_indices_by_member.get(b_id, set())
        if not (a_slots & b_slots):
            m_a = member_map.get(a_id)
            m_b = member_map.get(b_id)
            name_a = f"{m_a.prenom} {m_a.nom}" if m_a else str(a_id)
            name_b = f"{m_b.prenom} {m_b.nom}" if m_b else str(b_id)
            warnings.append(WarningItem(
                type="affinity_unsatisfied",
                message=f"Affinité non satisfaite : {name_a} & {name_b} — W6",
            ))

    # W7
    for member_id, slot_idxs in slot_indices_by_member.items():
        sorted_idxs = sorted(slot_idxs)
        # Build blocks
        blocks: List[List[int]] = [[sorted_idxs[0]]]
        for idx in sorted_idxs[1:]:
            if idx == blocks[-1][-1] + 1:
                blocks[-1].append(idx)
            else:
                blocks.append([idx])
        for k in range(len(blocks) - 1):
            gap = blocks[k + 1][0] - blocks[k][-1] - 1
            if gap >= 3:
                m = member_map.get(member_id)
                name = f"{m.prenom} {m.nom}" if m else str(member_id)
                warnings.append(WarningItem(
                    type="long_pause",
                    member_id=member_id,
                    message=f"{name} : pause de {gap}h entre deux blocs — W7",
                ))

    return warnings


# ---------------------------------------------------------------------------
# Manual assignment validation (unchanged API)
# ---------------------------------------------------------------------------


def check_manual_assignment(
    db: Session,
    event_id: int,
    membre_id: int,
    creneau_id: int,
) -> Optional[str]:
    """
    Validate a manual assignment.
    Only blocks if the member is explicitly unavailable (statut 'no') on the slot.
    Slot capacity is not enforced for manual overrides.
    """
    slot = db.query(Slot).filter(
        Slot.id == creneau_id, Slot.evenement_id == event_id
    ).first()
    if not slot:
        return "Créneau introuvable"

    avail = db.query(Availability).filter(
        Availability.evenement_id == event_id,
        Availability.membre_id == membre_id,
        Availability.creneau_id == creneau_id,
    ).first()
    if avail and avail.statut.value == "no":
        return "Ce membre est indisponible sur ce créneau"

    return None

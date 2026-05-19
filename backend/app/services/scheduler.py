"""
Scheduling algorithm for bar event planning.

Priority order (descending):
  1. R1, R2, R4, R5, R6  — absolute rules, never violated
  2. R3                   — strong preference (1h pause > 2h pause > 3h+)
  3. Quota (escalation palier)
  4. (Soirée) ≥1 respo bar per slot
  5. ≥1 bureau per slot   — replace worst non-bureau if slot full (never exceed max_personnes)
  6. fois_staffe total for this event type (ascending)
  7. taux d'utilisation at heure_relative H (ascending)
  8. Affinity (tie-break)

Rules:
  R1  — max 2 consecutive slots per block (absolute)
  R2  — min 1h pause between two separate blocks (absolute; covered by R1 check)
  R3  — pause preference: 1h > 2h > 3h+ (non-blocking, sort key)
  R4  — prefer 2h blocks over 1h (absolute: Group A before Group B)
  R5  — "no" availability inviolable; "maybe" = last resort (flagged maybe_force)
  R6  — max_personnes is an absolute upper bound, never exceeded for any reason

Escalation:
  Palier 1 : all members,    quota 2h
  Palier 2 : bureau only,    quota 3h
  Palier 3 : non-bureau,     quota 3h
  Palier 4 : bureau only,    quota 4h
  Palier 5 : non-bureau,     quota 4h
  ...
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

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
# Data structures
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


class _MemberState:
    """
    Tracks slot assignments for one member during a scheduling run.
    Provides R1/R2 feasibility checks (run <= 2 consecutive) and pause analysis.
    """

    def __init__(self, member_id: int):
        self.member_id = member_id
        self._indices: List[int] = []

    @property
    def hours_assigned(self) -> int:
        return len(self._indices)

    @property
    def index_set(self) -> Set[int]:
        return set(self._indices)

    def can_assign_at(self, slot_idx: int, quota: int) -> bool:
        """
        True iff assigning slot_idx respects R1 (max 2 consecutive) and quota.
        R2 (min 1h pause between blocks) is automatically satisfied when R1 holds.
        """
        if self.hours_assigned >= quota:
            return False
        s = self.index_set
        if slot_idx in s:
            return False
        run = 1
        j = slot_idx - 1
        while j in s:
            run += 1
            j -= 1
        j = slot_idx + 1
        while j in s:
            run += 1
            j += 1
        return run <= 2

    def last_block_end(self) -> Optional[int]:
        return max(self._indices) if self._indices else None

    def r3_priority(self, slot_idx: int) -> int:
        """
        0 = no previous block or extending current block or 1h pause (preferred)
        1 = 2h pause (tolerated)
        2 = 3h+ pause (deconseille, triggers W7)
        """
        s = self.index_set
        end = self.last_block_end()
        if end is None:
            return 0
        if (slot_idx - 1) in s:
            return 0  # extending current block
        gap = slot_idx - end - 1
        if gap <= 1:
            return 0
        if gap == 2:
            return 1
        return 2

    def assign(self, slot_idx: int) -> None:
        self._indices.append(slot_idx)
        self._indices.sort()

    def unassign(self, slot_idx: int) -> None:
        if slot_idx in self._indices:
            self._indices.remove(slot_idx)

    def blocks(self) -> List[List[int]]:
        if not self._indices:
            return []
        sorted_idx = sorted(self._indices)
        result: List[List[int]] = [[sorted_idx[0]]]
        for idx in sorted_idx[1:]:
            if idx == result[-1][-1] + 1:
                result[-1].append(idx)
            else:
                result.append([idx])
        return result


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
        return [WarningItem(type="no_slots", message="Aucun créneau configure")]

    n = len(slots)
    slot_id_to_idx: Dict[int, int] = {s.id: i for i, s in enumerate(slots)}

    all_members: List[Member] = db.query(Member).all()
    member_map: Dict[int, Member] = {m.id: m for m in all_members}

    # Availability map: (member_id, slot_idx) -> "yes" | "no" | "maybe"
    avail: Dict[Tuple[int, int], str] = {}
    for av in db.query(Availability).filter(Availability.evenement_id == event_id).all():
        idx = slot_id_to_idx.get(av.creneau_id)
        if idx is not None:
            avail[(av.membre_id, idx)] = av.statut.value

    # Stats for sorting
    total_fois_staffe: Dict[int, int] = {m.id: 0 for m in all_members}
    stats_at: Dict[Tuple[int, int], Tuple[int, int]] = {}  # (member_id, hr) -> (fd, fs)
    for stat in db.query(StatsMemberHeureRelative).filter(
        StatsMemberHeureRelative.type_evenement == event.type
    ).all():
        stats_at[(stat.membre_id, stat.heure_relative)] = (
            stat.fois_disponible, stat.fois_staffe
        )
        total_fois_staffe[stat.membre_id] = (
            total_fois_staffe.get(stat.membre_id, 0) + stat.fois_staffe
        )

    def taux_at(member_id: int, heure_relative: int) -> float:
        fd, fs = stats_at.get((member_id, heure_relative), (0, 0))
        return fs / fd if fd > 0 else 0.0

    # Affinity pairs (bidirectional)
    affinity_set: Set[Tuple[int, int]] = set()
    for ac in db.query(AffinityConstraint).filter(
        AffinityConstraint.evenement_id == event_id
    ).all():
        affinity_set.add((ac.membre_a_id, ac.membre_b_id))
        affinity_set.add((ac.membre_b_id, ac.membre_a_id))

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
    # Load existing manual assignments
    # ------------------------------------------------------------------
    assignments: List[List[_SlotAssignment]] = [[] for _ in range(n)]
    member_states: Dict[int, _MemberState] = {m.id: _MemberState(m.id) for m in all_members}

    for slot_idx, slot in enumerate(slots):
        for a in db.query(Assignment).filter(
            Assignment.creneau_id == slot.id,
            Assignment.source == AssignmentSourceEnum.manuel,
        ).all():
            assignments[slot_idx].append(
                _SlotAssignment(
                    member_id=a.membre_id,
                    asgn_type=a.type.value,
                    source="manuel",
                    maybe_force=a.maybe_force,
                )
            )
            member_states[a.membre_id].assign(slot_idx)

    warnings: List[WarningItem] = []

    # ------------------------------------------------------------------
    # Etape 1 -- Placement des respos bar (soiree only)
    # ------------------------------------------------------------------
    if event.type == EventTypeEnum.soiree:
        warnings += _place_respos_bar(
            db, event, slots, n, all_members, member_map, avail,
            assignments, member_states, total_fois_staffe,
        )

    # ------------------------------------------------------------------
    # Etape 2 -- Remplissage via escalade
    # ------------------------------------------------------------------
    bureau = [m for m in all_members if m.roles and "bureau" in m.roles]
    non_bureau = [m for m in all_members if not (m.roles and "bureau" in m.roles)]

    escalation: List[Tuple[List[Member], int]] = [(all_members, 2)]
    for quota in range(3, n + 2):
        escalation.append((bureau, quota))
        escalation.append((non_bureau, quota))

    member_escalation_palier: Dict[int, int] = {}

    for palier_idx, (target, quota) in enumerate(escalation, start=1):
        if all(len(assignments[i]) >= slots[i].max_personnes for i in range(n)):
            break

        prev_hours = {m.id: member_states[m.id].hours_assigned for m in target}

        _fill_pass(
            slots, n, target, member_map, avail, affinity_set,
            assignments, member_states, quota, taux_at, total_fois_staffe,
            use_maybe=False,
        )
        _fill_pass(
            slots, n, target, member_map, avail, affinity_set,
            assignments, member_states, quota, taux_at, total_fois_staffe,
            use_maybe=True,
        )

        for m in target:
            if member_states[m.id].hours_assigned > prev_hours[m.id] and palier_idx > 1:
                member_escalation_palier.setdefault(m.id, palier_idx)

    # ------------------------------------------------------------------
    # Persist new auto assignments
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
    # Etape 3 -- Warnings W1-W7
    # ------------------------------------------------------------------
    warnings += _generate_warnings(
        event, slots, member_map, assignments, affinity_set, member_escalation_palier
    )
    return warnings


# ---------------------------------------------------------------------------
# Etape 1 -- Placement des respos bar
# ---------------------------------------------------------------------------


def _place_respos_bar(
    db: Session,
    event: Event,
    slots: List[Slot],
    n: int,
    all_members: List[Member],
    member_map: Dict[int, Member],
    avail: Dict[Tuple[int, int], str],
    assignments: List[List[_SlotAssignment]],
    member_states: Dict[int, _MemberState],
    total_fois_staffe: Dict[int, int],
) -> List[WarningItem]:
    warnings: List[WarningItem] = []

    designated_ids: List[int] = [
        r.membre_id
        for r in sorted(
            db.query(ResponsableBar).filter(ResponsableBar.evenement_id == event.id).all(),
            key=lambda r: r.ordre,
        )
    ]

    bureau_fallback = sorted(
        [m for m in all_members if m.roles and "bureau" in m.roles],
        key=lambda m: (m.shifts_respo_bar_cumules, total_fois_staffe.get(m.id, 0)),
    )
    bureau_fallback_ids = [m.id for m in bureau_fallback]

    candidate_ids: List[int] = []
    seen: Set[int] = set()
    for mid in designated_ids + bureau_fallback_ids:
        if mid not in seen and mid in member_map:
            candidate_ids.append(mid)
            seen.add(mid)

    slot_idx = 0
    while slot_idx < n:
        slot = slots[slot_idx]

        if any(a.asgn_type == "respo_bar" for a in assignments[slot_idx]):
            slot_idx += 1
            continue

        placed = False
        next_idx = slot_idx + 1 if slot_idx + 1 < n else None

        for mid in candidate_ids:
            if mid not in member_map:
                continue
            ms = member_states[mid]
            avail_here = avail.get((mid, slot_idx), "no")
            if avail_here == "no":
                continue

            # R6: slot must have room
            if sum(1 for a in assignments[slot_idx] if a.member_id != mid) >= slot.max_personnes:
                continue

            # R1/R2
            if not ms.can_assign_at(slot_idx, n):
                continue

            if any(a.member_id == mid for a in assignments[slot_idx]):
                continue

            # Attempt 2h block (R4)
            can_do_2h = False
            if next_idx is not None:
                avail_next = avail.get((mid, next_idx), "no")
                next_has_room = (
                    sum(1 for a in assignments[next_idx] if a.member_id != mid)
                    < slots[next_idx].max_personnes
                )
                already_next = any(a.member_id == mid for a in assignments[next_idx])
                can_do_2h = (
                    avail_next != "no"
                    and ms.can_assign_at(next_idx, n)
                    and next_has_room
                    and not already_next
                )

            assignments[slot_idx].append(_SlotAssignment(
                member_id=mid,
                asgn_type="respo_bar",
                source="auto",
                maybe_force=(avail_here == "maybe"),
            ))
            ms.assign(slot_idx)

            if can_do_2h:
                avail_next = avail.get((mid, next_idx), "no")
                assignments[next_idx].append(_SlotAssignment(
                    member_id=mid,
                    asgn_type="respo_bar",
                    source="auto",
                    maybe_force=(avail_next == "maybe"),
                ))
                ms.assign(next_idx)
                slot_idx += 2
            else:
                slot_idx += 1

            placed = True
            break

        if not placed:
            warnings.append(WarningItem(
                type="no_respo_bar",
                slot_id=slot.id,
                message=(
                    f"Creneau {slot.heure_debut.strftime('%H:%M')} : "
                    "impossible de placer un respo bar (W1)"
                ),
            ))
            slot_idx += 1

    return warnings


# ---------------------------------------------------------------------------
# Etape 2 -- Remplissage des creneaux
# ---------------------------------------------------------------------------


def _fill_pass(
    slots: List[Slot],
    n: int,
    target_members: List[Member],
    member_map: Dict[int, Member],
    avail: Dict[Tuple[int, int], str],
    affinity_set: Set[Tuple[int, int]],
    assignments: List[List[_SlotAssignment]],
    member_states: Dict[int, _MemberState],
    quota: int,
    taux_at: Callable[[int, int], float],
    total_fois_staffe: Dict[int, int],
    use_maybe: bool,
) -> None:
    for slot_idx, slot in enumerate(slots):
        if len(assignments[slot_idx]) >= slot.max_personnes:
            continue

        already_on_slot: Set[int] = {a.member_id for a in assignments[slot_idx]}
        hr = slot.heure_relative
        has_bureau = _slot_has_bureau(assignments[slot_idx], member_map)

        grp_yes_2h: List[Member] = []
        grp_yes_1h: List[Member] = []
        grp_maybe_2h: List[Member] = []
        grp_maybe_1h: List[Member] = []

        for m in target_members:
            if m.id in already_on_slot:
                continue
            if not member_states[m.id].can_assign_at(slot_idx, quota):
                continue
            status = avail.get((m.id, slot_idx), "no")
            if status == "no":
                continue
            if status == "maybe" and not use_maybe:
                continue

            can_2h = _can_do_2h(
                m.id, slot_idx, n, quota, avail, assignments, member_states, use_maybe
            )

            if status == "yes":
                (grp_yes_2h if can_2h else grp_yes_1h).append(m)
            else:
                (grp_maybe_2h if can_2h else grp_maybe_1h).append(m)

        def sort_key(m: Member) -> tuple:
            ms = member_states[m.id]
            r3 = ms.r3_priority(slot_idx)
            total_fs = total_fois_staffe.get(m.id, 0)
            taux = taux_at(m.id, hr)
            has_aff = any((m.id, oid) in affinity_set for oid in already_on_slot)
            return (r3, total_fs, taux, -int(has_aff))

        for grp in (grp_yes_2h, grp_yes_1h, grp_maybe_2h, grp_maybe_1h):
            grp.sort(key=sort_key)

        two_h_set = {m.id for m in grp_yes_2h + grp_maybe_2h}
        ordered = grp_yes_2h + grp_yes_1h + grp_maybe_2h + grp_maybe_1h

        needed = slot.max_personnes - len(assignments[slot_idx])
        placed = 0

        for m in ordered:
            if placed >= needed:
                break
            if len(assignments[slot_idx]) >= slot.max_personnes:
                break
            ms = member_states[m.id]
            if not ms.can_assign_at(slot_idx, quota):
                continue
            status = avail.get((m.id, slot_idx), "no")
            if status == "no" or (status == "maybe" and not use_maybe):
                continue
            if m.id in {a.member_id for a in assignments[slot_idx]}:
                continue

            assignments[slot_idx].append(_SlotAssignment(
                member_id=m.id,
                asgn_type="staff",
                source="auto",
                maybe_force=(status == "maybe"),
            ))
            ms.assign(slot_idx)
            already_on_slot.add(m.id)
            if m.roles and "bureau" in m.roles:
                has_bureau = True
            placed += 1

            # R4: extend to 2h block immediately
            if m.id in two_h_set and slot_idx + 1 < n:
                _try_extend_2h(
                    m, slot_idx + 1, slots[slot_idx + 1],
                    avail, assignments, member_states, quota, use_maybe,
                )

        # Bureau guarantee (R6 respected: replace, never add over max)
        if not has_bureau:
            _ensure_bureau(
                slot_idx, slot, target_members, member_map, avail,
                assignments, member_states, quota,
                already_on_slot, use_maybe, total_fois_staffe, taux_at,
            )


def _can_do_2h(
    member_id: int,
    slot_idx: int,
    n: int,
    quota: int,
    avail: Dict[Tuple[int, int], str],
    assignments: List[List[_SlotAssignment]],
    member_states: Dict[int, _MemberState],
    use_maybe: bool,
) -> bool:
    if slot_idx + 1 >= n:
        return False
    ms = member_states[member_id]
    next_status = avail.get((member_id, slot_idx + 1), "no")
    if next_status == "no":
        return False
    if next_status == "maybe" and not use_maybe:
        return False
    return ms.can_assign_at(slot_idx + 1, quota)


def _try_extend_2h(
    m: Member,
    next_idx: int,
    next_slot: Slot,
    avail: Dict[Tuple[int, int], str],
    assignments: List[List[_SlotAssignment]],
    member_states: Dict[int, _MemberState],
    quota: int,
    use_maybe: bool,
) -> None:
    ms = member_states[m.id]
    if len(assignments[next_idx]) >= next_slot.max_personnes:
        return
    status = avail.get((m.id, next_idx), "no")
    if status == "no" or (status == "maybe" and not use_maybe):
        return
    if not ms.can_assign_at(next_idx, quota):
        return
    if any(a.member_id == m.id for a in assignments[next_idx]):
        return
    assignments[next_idx].append(_SlotAssignment(
        member_id=m.id,
        asgn_type="staff",
        source="auto",
        maybe_force=(status == "maybe"),
    ))
    ms.assign(next_idx)


def _ensure_bureau(
    slot_idx: int,
    slot: Slot,
    target_members: List[Member],
    member_map: Dict[int, Member],
    avail: Dict[Tuple[int, int], str],
    assignments: List[List[_SlotAssignment]],
    member_states: Dict[int, _MemberState],
    quota: int,
    already_on_slot: Set[int],
    use_maybe: bool,
    total_fois_staffe: Dict[int, int],
    taux_at: Callable[[int, int], float],
) -> None:
    """
    Guarantee >=1 bureau on slot_idx. Never exceed max_personnes (R6).
    If room: add best bureau.
    If full: replace auto non-bureau with highest fois_staffe with best bureau.
    """
    bureau_candidates = [
        m for m in target_members
        if m.id not in already_on_slot
        and "bureau" in (m.roles or [])
        and member_states[m.id].can_assign_at(slot_idx, quota)
        and avail.get((m.id, slot_idx), "no") != "no"
        and (avail.get((m.id, slot_idx), "no") != "maybe" or use_maybe)
    ]
    if not bureau_candidates:
        return  # W3 emitted in _generate_warnings

    bureau_candidates.sort(
        key=lambda m: (total_fois_staffe.get(m.id, 0), taux_at(m.id, slot_idx))
    )
    best_bureau = bureau_candidates[0]

    if len(assignments[slot_idx]) < slot.max_personnes:
        status = avail.get((best_bureau.id, slot_idx), "no")
        assignments[slot_idx].append(_SlotAssignment(
            member_id=best_bureau.id,
            asgn_type="staff",
            source="auto",
            maybe_force=(status == "maybe"),
        ))
        member_states[best_bureau.id].assign(slot_idx)
    else:
        # Replace worst auto non-bureau
        auto_non_bureau = [
            a for a in assignments[slot_idx]
            if a.source == "auto"
            and a.member_id in member_map
            and "bureau" not in (member_map[a.member_id].roles or [])
        ]
        if not auto_non_bureau:
            return
        auto_non_bureau.sort(
            key=lambda a: total_fois_staffe.get(a.member_id, 0),
            reverse=True,
        )
        worst = auto_non_bureau[0]
        assignments[slot_idx].remove(worst)
        member_states[worst.member_id].unassign(slot_idx)
        status = avail.get((best_bureau.id, slot_idx), "no")
        assignments[slot_idx].append(_SlotAssignment(
            member_id=best_bureau.id,
            asgn_type="staff",
            source="auto",
            maybe_force=(status == "maybe"),
        ))
        member_states[best_bureau.id].assign(slot_idx)


def _slot_has_bureau(asgns: List[_SlotAssignment], member_map: Dict[int, Member]) -> bool:
    return any(
        "bureau" in (member_map[a.member_id].roles or [])
        for a in asgns
        if a.member_id in member_map
    )


# ---------------------------------------------------------------------------
# Etape 3 -- Warnings W1-W7
# ---------------------------------------------------------------------------


def _generate_warnings(
    event: Event,
    slots: List[Slot],
    member_map: Dict[int, Member],
    assignments: List[List[_SlotAssignment]],
    affinity_set: Set[Tuple[int, int]],
    member_escalation_palier: Dict[int, int],
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
                    message=f"Creneau {slot.heure_debut.strftime('%H:%M')} : aucun respo bar (W1)",
                ))

        # W2
        if len(asgns) < slot.max_personnes:
            warnings.append(WarningItem(
                type="slot_understaffed",
                slot_id=slot.id,
                message=(
                    f"Creneau {slot.heure_debut.strftime('%H:%M')} : "
                    f"{len(asgns)}/{slot.max_personnes} personnes (W2)"
                ),
            ))

        # W3
        if asgns and not _slot_has_bureau(asgns, member_map):
            warnings.append(WarningItem(
                type="no_bureau",
                slot_id=slot.id,
                message=f"Creneau {slot.heure_debut.strftime('%H:%M')} : aucun membre bureau (W3)",
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
                    message=f"Creneau {slot.heure_debut.strftime('%H:%M')} : {name} force (maybe) — W5",
                ))
            slot_indices_by_member.setdefault(a.member_id, set()).add(slot_idx)

    # W4
    for member_id, palier in member_escalation_palier.items():
        total_h = len(slot_indices_by_member.get(member_id, set()))
        m = member_map.get(member_id)
        name = f"{m.prenom} {m.nom}" if m else str(member_id)
        warnings.append(WarningItem(
            type="over_quota",
            member_id=member_id,
            message=f"{name} : {total_h}h affectees (palier {palier}) — W4",
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
                message=f"Affinite non satisfaite : {name_a} & {name_b} — W6",
            ))

    # W7 — pause >= 3h between blocks
    for member_id, slot_idxs in slot_indices_by_member.items():
        ms_tmp = _MemberState(member_id)
        for idx in sorted(slot_idxs):
            ms_tmp.assign(idx)
        blks = ms_tmp.blocks()
        for i in range(len(blks) - 1):
            gap = blks[i + 1][0] - blks[i][-1] - 1
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
# Utility: manual assignment validation
# ---------------------------------------------------------------------------


def check_manual_assignment(
    db: Session,
    event_id: int,
    membre_id: int,
    creneau_id: int,
) -> Optional[str]:
    """
    Validate R1/R5/R6 for a manual assignment.
    Returns error string if violated, None if OK.
    """
    slot = db.query(Slot).filter(
        Slot.id == creneau_id, Slot.evenement_id == event_id
    ).first()
    if not slot:
        return "Creneau introuvable"

    # R5
    avail = db.query(Availability).filter(
        Availability.evenement_id == event_id,
        Availability.membre_id == membre_id,
        Availability.creneau_id == creneau_id,
    ).first()
    if avail and avail.statut.value == "no":
        return "R5 : ce membre est indisponible (statut 'no')"

    # R6
    already_there = db.query(Assignment).filter(
        Assignment.creneau_id == creneau_id,
        Assignment.membre_id == membre_id,
    ).first()
    if not already_there:
        count = db.query(Assignment).filter(Assignment.creneau_id == creneau_id).count()
        if count >= slot.max_personnes:
            return f"R6 : creneau complet ({slot.max_personnes}/{slot.max_personnes})"

    # R1
    all_slots = sorted(
        db.query(Slot).filter(Slot.evenement_id == event_id).all(),
        key=lambda s: s.heure_debut,
    )
    slot_id_to_idx = {s.id: i for i, s in enumerate(all_slots)}
    slot_idx = slot_id_to_idx.get(creneau_id)
    if slot_idx is None:
        return "Creneau introuvable dans l'evenement"

    other_asgns = db.query(Assignment).filter(
        Assignment.creneau_id.in_([s.id for s in all_slots]),
        Assignment.membre_id == membre_id,
        Assignment.creneau_id != creneau_id,
    ).all()
    assigned_indices: Set[int] = {
        slot_id_to_idx[a.creneau_id]
        for a in other_asgns
        if a.creneau_id in slot_id_to_idx
    }

    run = 1
    j = slot_idx - 1
    while j in assigned_indices:
        run += 1
        j -= 1
    j = slot_idx + 1
    while j in assigned_indices:
        run += 1
        j += 1
    if run > 2:
        return "R1 : bloc de plus de 2h consecutives interdit"

    return None

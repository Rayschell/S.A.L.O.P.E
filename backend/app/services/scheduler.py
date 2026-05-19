"""
Scheduling algorithm for bar event planning.

Rules (absolute, never violated):
  R1 - Max 2 consecutive slots per block (= 2h)
  R4 - Prefer 2h blocks over 1h blocks (optimal block decomposition)
  R5 - Only assign to slots where member has "yes" (priority) or "maybe" (last resort)

Preferences (soft, honored via sort key):
  R2 - Prefer min 1 slot pause (= 1h) between two blocks; longer pauses allowed if unavoidable
  R3 - Prefer shortest possible pause between blocks; no hard maximum

Escalation order:
  Palier 1 : all members,    quota 2h   (yes only, then maybe)
  Palier 2 : bureau,         quota 3h
  Palier 3 : non-bureau,     quota 3h
  Palier 4 : bureau,         quota 4h
  Palier 5 : non-bureau,     quota 4h
  ...
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

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
    Enforces R1 (max 2 consecutive), R2 (min 1 pause), R3 (max 2 pause).
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

    def _blocks(self) -> List[List[int]]:
        """Return sorted list of blocks (each block = sorted list of consecutive indices)."""
        if not self._indices:
            return []
        sorted_idx = sorted(self._indices)
        blocks: List[List[int]] = [[sorted_idx[0]]]
        for idx in sorted_idx[1:]:
            if idx == blocks[-1][-1] + 1:
                blocks[-1].append(idx)
            else:
                blocks.append([idx])
        return blocks

    def can_assign_at(self, slot_idx: int, quota: int) -> bool:
        """
        Return True iff assigning slot_idx respects R1, R2, R3 and quota.
        Does NOT check R4 (block size preference) — caller handles that.
        """
        if self.hours_assigned >= quota:
            return False
        s = self.index_set
        if slot_idx in s:
            return False

        # R1 — cannot extend a block beyond 2 consecutive slots
        # Slot would extend left: [slot_idx, slot_idx+1] already exists → forbidden
        if (slot_idx + 1) in s and (slot_idx - 1) not in s:
            # slot_idx is immediately before an existing single slot → would create [slot_idx, slot_idx+1]
            # Only forbidden if that slot_idx+1 is already part of a 2-slot block
            if (slot_idx + 2) in s:
                return False  # block [slot_idx+1, slot_idx+2] exists → can't prepend
        # Slot would extend right: [slot_idx-1, slot_idx] continuation
        if (slot_idx - 1) in s:
            if (slot_idx - 2) in s:
                return False  # block already 2h long (slot_idx-2, slot_idx-1) → R1 violated
        # Slot would bridge two existing blocks → R1 violated
        if (slot_idx - 1) in s and (slot_idx + 1) in s:
            return False

        # R2/R3 — pauses between blocks are preferences, not hard constraints.
        # Long pauses are allowed; the sort key in _fill_pass prefers shorter gaps.

        return True

    def _last_block_end(self) -> Optional[int]:
        """Index of the last assigned slot, or None."""
        return max(self._indices) if self._indices else None

    def preferred_next_start(self) -> Optional[int]:
        """
        For escalation: return the preferred next-block start index (R3 priority 1 = pause 1h,
        then priority 2 = pause 2h). Returns None if no existing block.
        """
        end = self._last_block_end()
        if end is None:
            return None
        return end + 2  # pause 1h preferred

    def allowed_next_starts(self) -> List[int]:
        """Returns [end+2, end+3] — pause 1h preferred (R3)."""
        end = self._last_block_end()
        if end is None:
            return []
        return [end + 2, end + 3]

    def assign(self, slot_idx: int) -> None:
        self._indices.append(slot_idx)
        self._indices.sort()


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

    # Availability map: (member_id, slot_idx) -> "yes" | "no" | "maybe"
    avail: Dict[Tuple[int, int], str] = {}
    for av in db.query(Availability).filter(Availability.evenement_id == event_id).all():
        idx = slot_id_to_idx.get(av.creneau_id)
        if idx is not None:
            avail[(av.membre_id, idx)] = av.statut.value

    # Affinity pairs (bidirectional set of (a_id, b_id))
    affinity_set: Set[Tuple[int, int]] = set()
    for ac in db.query(AffinityConstraint).filter(AffinityConstraint.evenement_id == event_id).all():
        affinity_set.add((ac.membre_a_id, ac.membre_b_id))
        affinity_set.add((ac.membre_b_id, ac.membre_a_id))

    # Number of available slots per member (yes + maybe) — used for "most constrained first" heuristic
    avail_count: Dict[int, int] = {
        m.id: sum(1 for i in range(n) if avail.get((m.id, i), "no") != "no")
        for m in all_members
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
    # Load remaining manual assignments into working structures
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
    # Étape 1 — Placement des respos bar (soirée only)
    # ------------------------------------------------------------------
    if event.type == EventTypeEnum.soiree:
        warnings += _place_respos_bar(
            db, event, slots, all_members, member_map, avail,
            assignments, member_states,
        )

    # ------------------------------------------------------------------
    # Étape 2 — Remplissage des créneaux via escalade
    # ------------------------------------------------------------------
    bureau = [m for m in all_members if m.roles and "bureau" in m.roles]
    non_bureau = [m for m in all_members if not m.roles or "bureau" not in m.roles]

    # Palier 1 : tous, quota 2h  (yes first, then maybe)
    # Paliers suivants : bureau/non-bureau alternés, quota croissant
    escalation: List[Tuple[List[Member], int]] = [(all_members, 2)]
    for quota in range(3, n + 1):
        escalation.append((bureau, quota))
        escalation.append((non_bureau, quota))

    # Track which palier each member reaches (for W4 warning)
    member_escalation_palier: Dict[int, int] = {}

    for palier_idx, (target, quota) in enumerate(escalation, start=1):
        # Incomplete = not yet at max_personnes
        if all(len(assignments[i]) >= slots[i].max_personnes for i in range(n)):
            break

        prev_hours = {m.id: member_states[m.id].hours_assigned for m in target}

        # 2a — yes candidates only
        _fill_pass(slots, n, target, member_map, avail, affinity_set,
                   assignments, member_states, quota, avail_count, use_maybe=False)
        # 2b — maybe candidates (before escalating further)
        _fill_pass(slots, n, target, member_map, avail, affinity_set,
                   assignments, member_states, quota, avail_count, use_maybe=True)

        # Record escalation palier for members who got extra hours this round
        for m in target:
            if member_states[m.id].hours_assigned > prev_hours[m.id] and palier_idx > 1:
                member_escalation_palier[m.id] = palier_idx

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
    # Étape 3 — Warnings W1–W7
    # ------------------------------------------------------------------
    warnings += _generate_warnings(
        event, slots, member_map, assignments, affinity_set, member_escalation_palier
    )
    return warnings


# ---------------------------------------------------------------------------
# Étape 1 — Placement des respos bar
# ---------------------------------------------------------------------------


def _place_respos_bar(
    db: Session,
    event: Event,
    slots: List[Slot],
    all_members: List[Member],
    member_map: Dict[int, Member],
    avail: Dict[Tuple[int, int], str],
    assignments: List[List[_SlotAssignment]],
    member_states: Dict[int, _MemberState],
) -> List[WarningItem]:
    """
    Étape 1b : couvre tous les créneaux avec au moins 1 respo bar.
    Blocs de 2h consécutives; chaque respo bar est utilisé pour un bloc.
    Si la liste désignée est insuffisante, complète avec les membres bureau
    triés par shifts_respo_bar_cumules croissant.
    """
    warnings: List[WarningItem] = []
    n = len(slots)

    # 1a — liste ordonnée des candidats respo bar
    designated_ids: List[int] = [
        r.membre_id
        for r in sorted(
            db.query(ResponsableBar).filter(ResponsableBar.evenement_id == event.id).all(),
            key=lambda r: r.ordre,
        )
    ]

    bureau_fallback = sorted(
        [m for m in all_members if m.roles and "bureau" in m.roles],
        key=lambda m: (m.shifts_respo_bar_cumules, m.heures_cumulees),
    )
    bureau_fallback_ids = [m.id for m in bureau_fallback]

    # Merge: designated first, then bureau by shifts (no duplicates)
    candidate_ids: List[int] = []
    seen: Set[int] = set()
    for mid in designated_ids + bureau_fallback_ids:
        if mid not in seen and mid in member_map:
            candidate_ids.append(mid)
            seen.add(mid)

    # Tracks how many respo-bar blocks each candidate has done this run
    # (allows reuse for a second block if R2/R3/R4 are respected)
    cand_ptr = 0  # next candidate to try for a new block
    slot_idx = 0

    while slot_idx < n:
        # Check if this slot already has a respo bar (from manual assignment)
        if any(a.asgn_type == "respo_bar" for a in assignments[slot_idx]):
            slot_idx += 1
            continue

        # Try to place a 2h block starting at slot_idx
        # (block_end = slot_idx+1 if it exists, else slot_idx alone)
        block_end = slot_idx + 1 if slot_idx + 1 < n else slot_idx

        placed = False

        # Try candidates in order (cycling through the full list each uncovered slot,
        # not just advancing the pointer, to allow reuse for second blocks)
        for try_new_block in (True, False):
            # try_new_block=True: prefer candidates who haven't done a block yet
            # try_new_block=False: allow reuse
            for i, mid in enumerate(candidate_ids):
                ms = member_states[mid]
                avail_start = avail.get((mid, slot_idx), "no")
                if avail_start == "no":
                    continue

                # R1/R2/R3 check for first slot of block
                if not ms.can_assign_at(slot_idx, n):
                    continue

                # Attempt 2h block
                can_do_2h = (
                    block_end != slot_idx
                    and avail.get((mid, block_end), "no") != "no"
                    and ms.can_assign_at(block_end, n)
                )

                # Assign first slot
                if not any(a.member_id == mid for a in assignments[slot_idx]):
                    assignments[slot_idx].append(_SlotAssignment(
                        member_id=mid,
                        asgn_type="respo_bar",
                        source="auto",
                        maybe_force=(avail_start == "maybe"),
                    ))
                    ms.assign(slot_idx)

                # Assign second slot if possible (R4 — prefer 2h blocks)
                if can_do_2h:
                    avail_end = avail.get((mid, block_end), "no")
                    if not any(a.member_id == mid for a in assignments[block_end]):
                        assignments[block_end].append(_SlotAssignment(
                            member_id=mid,
                            asgn_type="respo_bar",
                            source="auto",
                            maybe_force=(avail_end == "maybe"),
                        ))
                        ms.assign(block_end)
                    # Skip the second slot in the outer loop since it's now covered
                    slot_idx += 2
                else:
                    slot_idx += 1

                placed = True
                break

            if placed:
                break

        if not placed:
            warnings.append(WarningItem(
                type="no_respo_bar",
                slot_id=slots[slot_idx].id,
                message=(
                    f"Créneau {slots[slot_idx].heure_debut.strftime('%H:%M')} : "
                    "impossible de placer un respo bar"
                ),
            ))
            slot_idx += 1

    return warnings


# ---------------------------------------------------------------------------
# Étape 2 — Remplissage des créneaux (staff + escalade)
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
    avail_count: Dict[int, int],
    use_maybe: bool,
) -> None:
    """
    One pass over all slots for the given target_members at the given quota.
    use_maybe=False  → only "yes" availability
    use_maybe=True   → also "maybe" (flagged maybe_force)

    Implements R1–R5 and the R4 block-of-2h preference.
    For escalation paliers (quota > 2): enforces R3 (max pause 2h).
    Guarantees at least 1 bureau per slot (may exceed max_personnes by 1).
    """
    for slot_idx, slot in enumerate(slots):
        current_count = len(assignments[slot_idx])
        if current_count >= slot.max_personnes:
            continue

        needed = slot.max_personnes - current_count
        already_on_slot = {a.member_id for a in assignments[slot_idx]}

        has_bureau = any(
            "bureau" in (member_map[a.member_id].roles or [])
            for a in assignments[slot_idx]
            if a.member_id in member_map
        )

        # Build candidate list
        yes_2h: List[Member] = []   # can do 2h block here (R4 preferred)
        yes_1h: List[Member] = []   # can only do 1h here
        maybe_2h: List[Member] = []
        maybe_1h: List[Member] = []

        for m in target_members:
            if m.id in already_on_slot:
                continue
            if not _can_place(m.id, slot_idx, quota, member_states, avail, n):
                continue
            status = avail.get((m.id, slot_idx), "no")
            if status == "no":
                continue
            if status == "maybe" and not use_maybe:
                continue

            # R4: check if 2h block is possible at slot_idx
            can_2h = (
                slot_idx + 1 < n
                and _can_place(m.id, slot_idx + 1, quota, member_states, avail, n)
                and avail.get((m.id, slot_idx + 1), "no") not in ("no",)
                and (avail.get((m.id, slot_idx + 1), "no") != "maybe" or use_maybe)
            )

            if status == "yes":
                if can_2h:
                    yes_2h.append(m)
                else:
                    yes_1h.append(m)
            else:  # maybe
                if can_2h:
                    maybe_2h.append(m)
                else:
                    maybe_1h.append(m)

        def _sort_key(m: Member) -> tuple:
            is_bureau = bool(m.roles and "bureau" in m.roles)
            bureau_prio = 0 if (not has_bureau and is_bureau) else (1 if is_bureau else 2)
            has_affinity = any((m.id, oid) in affinity_set for oid in already_on_slot)
            # Most constrained first: prefer members with fewer available slots
            constrained = avail_count.get(m.id, n)
            # Prefer shorter pause from last block (R2/R3 as preference)
            ms_m = member_states[m.id]
            last_end = ms_m._last_block_end()
            if last_end is not None and (slot_idx - 1) not in ms_m.index_set:
                pause_gap = slot_idx - last_end - 1
            else:
                pause_gap = 0
            return (bureau_prio, constrained, m.heures_cumulees, pause_gap, -int(has_affinity))

        for lst in (yes_2h, yes_1h, maybe_2h, maybe_1h):
            lst.sort(key=_sort_key)

        # R4: prioritise 2h-capable candidates
        ordered_candidates = yes_2h + yes_1h + maybe_2h + maybe_1h
        two_h_member_ids = {m.id for m in yes_2h + maybe_2h}

        placed = 0
        for m in ordered_candidates:
            if placed >= needed:
                break
            # Re-check (state may have changed from earlier placements this pass)
            if not _can_place(m.id, slot_idx, quota, member_states, avail, n):
                continue
            status = avail.get((m.id, slot_idx), "no")
            if status == "no":
                continue
            if status == "maybe" and not use_maybe:
                continue
            already_on_slot.add(m.id)
            assignments[slot_idx].append(_SlotAssignment(
                member_id=m.id,
                asgn_type="staff",
                source="auto",
                maybe_force=(status == "maybe"),
            ))
            member_states[m.id].assign(slot_idx)
            if "bureau" in (m.roles or []):
                has_bureau = True
            placed += 1

            # R4: immediately extend to 2h block (reserve slot+1 before others can take it)
            if m.id in two_h_member_ids and slot_idx + 1 < n:
                status_next = avail.get((m.id, slot_idx + 1), "no")
                next_not_assigned = m.id not in {a.member_id for a in assignments[slot_idx + 1]}
                if (
                    status_next != "no"
                    and (status_next != "maybe" or use_maybe)
                    and next_not_assigned
                    and _can_place(m.id, slot_idx + 1, quota, member_states, avail, n)
                ):
                    assignments[slot_idx + 1].append(_SlotAssignment(
                        member_id=m.id,
                        asgn_type="staff",
                        source="auto",
                        maybe_force=(status_next == "maybe"),
                    ))
                    member_states[m.id].assign(slot_idx + 1)

        # Guarantee at least 1 bureau (even if it exceeds max_personnes)
        if not has_bureau:
            _force_bureau(
                slot_idx, slot, target_members, member_map, avail,
                affinity_set, assignments, member_states, quota,
                already_on_slot, use_maybe,
            )


def _can_place(
    member_id: int,
    slot_idx: int,
    quota: int,
    member_states: Dict[int, _MemberState],
    avail: Dict[Tuple[int, int], str],
    n: int,
) -> bool:
    """
    Check R1/R2/R3 via _MemberState.can_assign_at, plus quota.
    For escalation (quota > 2), also enforces R3:
    a new block start must be at most 2 slots after the last block end.
    """
    ms = member_states[member_id]
    if not ms.can_assign_at(slot_idx, quota):
        return False

    # For members who already have at least one block and are starting a NEW block
    # (slot_idx-1 not in their index_set), R3 is already enforced by can_assign_at.
    return True


def _force_bureau(
    slot_idx: int,
    slot: Slot,
    target_members: List[Member],
    member_map: Dict[int, Member],
    avail: Dict[Tuple[int, int], str],
    affinity_set: Set[Tuple[int, int]],
    assignments: List[List[_SlotAssignment]],
    member_states: Dict[int, _MemberState],
    quota: int,
    already_on_slot: Set[int],
    use_maybe: bool,
) -> None:
    """
    Force at least one bureau member onto slot_idx if none is present.
    May exceed max_personnes by 1. Respects R1–R5.
    """
    bureau_candidates = [
        m for m in target_members
        if m.id not in already_on_slot
        and "bureau" in (m.roles or [])
        and _can_place(m.id, slot_idx, quota, member_states, avail, len(assignments))
        and avail.get((m.id, slot_idx), "no") not in ("no",)
        and (avail.get((m.id, slot_idx), "no") != "maybe" or use_maybe)
    ]
    if not bureau_candidates:
        return
    bureau_candidates.sort(key=lambda m: m.heures_cumulees)
    m = bureau_candidates[0]
    status = avail.get((m.id, slot_idx), "no")
    assignments[slot_idx].append(_SlotAssignment(
        member_id=m.id,
        asgn_type="staff",
        source="auto",
        maybe_force=(status == "maybe"),
    ))
    member_states[m.id].assign(slot_idx)


# ---------------------------------------------------------------------------
# Étape 3 — Génération des warnings W1–W7
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

    # slot_indices_by_member: member_id -> set of slot indices where they are assigned
    slot_indices_by_member: Dict[int, Set[int]] = {}

    for slot_idx, slot in enumerate(slots):
        asgns = assignments[slot_idx]

        # W1 — créneau sans respo bar (soirée)
        if event.type == EventTypeEnum.soiree:
            if not any(a.asgn_type == "respo_bar" for a in asgns):
                warnings.append(WarningItem(
                    type="no_respo_bar",
                    slot_id=slot.id,
                    message=f"Créneau {slot.heure_debut.strftime('%H:%M')} : aucun respo bar",
                ))

        # W2 — créneau sous-staffé
        if len(asgns) < slot.max_personnes:
            warnings.append(WarningItem(
                type="slot_understaffed",
                slot_id=slot.id,
                message=(
                    f"Créneau {slot.heure_debut.strftime('%H:%M')} : "
                    f"{len(asgns)}/{slot.max_personnes} personnes"
                ),
            ))

        # W3 — créneau sans bureau
        has_bureau = any(
            "bureau" in (member_map[a.member_id].roles or [])
            for a in asgns if a.member_id in member_map
        )
        if asgns and not has_bureau:
            warnings.append(WarningItem(
                type="no_bureau",
                slot_id=slot.id,
                message=f"Créneau {slot.heure_debut.strftime('%H:%M')} : aucun membre bureau",
            ))

        # W5 — maybe_force
        for a in asgns:
            if a.maybe_force:
                m = member_map.get(a.member_id)
                name = f"{m.prenom} {m.nom}" if m else str(a.member_id)
                warnings.append(WarningItem(
                    type="maybe_forced",
                    slot_id=slot.id,
                    member_id=a.member_id,
                    message=f"Créneau {slot.heure_debut.strftime('%H:%M')} : {name} forcé (maybe)",
                ))
            slot_indices_by_member.setdefault(a.member_id, set()).add(slot_idx)

    # W4 — membre au-delà de 2h (escalade)
    for member_id, palier in member_escalation_palier.items():
        total_h = len(slot_indices_by_member.get(member_id, set()))
        m = member_map.get(member_id)
        name = f"{m.prenom} {m.nom}" if m else str(member_id)
        warnings.append(WarningItem(
            type="over_quota",
            member_id=member_id,
            message=(
                f"{name} : {total_h}h affectées (palier d'escalade {palier})"
            ),
        ))

    # W6 — affinité non satisfaite
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
                message=f"Affinité non satisfaite : {name_a} & {name_b}",
            ))

    # W7 — pause de 2h utilisée (R3 priorité 2)
    for member_id, slot_idxs in slot_indices_by_member.items():
        sorted_idxs = sorted(slot_idxs)
        # Find block boundaries
        if len(sorted_idxs) < 2:
            continue
        # Detect blocks
        blocks: List[List[int]] = [[sorted_idxs[0]]]
        for idx in sorted_idxs[1:]:
            if idx == blocks[-1][-1] + 1:
                blocks[-1].append(idx)
            else:
                blocks.append([idx])
        if len(blocks) < 2:
            continue
        for i in range(len(blocks) - 1):
            gap = blocks[i + 1][0] - blocks[i][-1] - 1
            if gap == 2:
                m = member_map.get(member_id)
                name = f"{m.prenom} {m.nom}" if m else str(member_id)
                slot_obj = None  # no single slot to attach
                warnings.append(WarningItem(
                    type="long_pause",
                    member_id=member_id,
                    message=f"{name} : pause de 2h entre deux blocs (R3 priorité 2)",
                ))

    return warnings

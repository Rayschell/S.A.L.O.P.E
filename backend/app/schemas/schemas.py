"""Pydantic schemas for request/response validation."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator

from ..models.models import (
    AssignmentSourceEnum,
    AssignmentTypeEnum,
    AvailabilityStatusEnum,
    EventStatutEnum,
    EventTypeEnum,
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Member
# ---------------------------------------------------------------------------


class MemberBase(BaseModel):
    nom: str
    prenom: str
    email: Optional[EmailStr] = None
    roles: List[str] = ["staff"]
    shifts_respo_bar_cumules: int = 0

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: List[str]) -> List[str]:
        allowed = {"staff", "bureau"}
        for role in v:
            if role not in allowed:
                raise ValueError(f"Invalid role '{role}'. Must be one of {allowed}")
        return v


class MemberCreate(MemberBase):
    password: Optional[str] = None


class MemberUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    email: Optional[EmailStr] = None
    roles: Optional[List[str]] = None
    shifts_respo_bar_cumules: Optional[int] = None
    password: Optional[str] = None


class MemberRead(MemberBase):
    id: int

    model_config = {"from_attributes": True}


class MemberReadFull(MemberRead):
    aliases: List[AliasRead] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Alias
# ---------------------------------------------------------------------------


class AliasRead(BaseModel):
    id: int
    valeur: str

    model_config = {"from_attributes": True}


# Rebuild forward reference
MemberReadFull.model_rebuild()


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------


class EventCreate(BaseModel):
    nom: str
    date: datetime
    type: EventTypeEnum


class EventUpdate(BaseModel):
    nom: Optional[str] = None
    date: Optional[datetime] = None
    type: Optional[EventTypeEnum] = None
    statut: Optional[EventStatutEnum] = None


class SlotRead(BaseModel):
    id: int
    evenement_id: int
    heure_debut: datetime
    heure_fin: datetime
    heure_relative: int
    max_personnes: int

    model_config = {"from_attributes": True}


class EventRead(BaseModel):
    id: int
    nom: str
    date: datetime
    type: EventTypeEnum
    statut: EventStatutEnum

    model_config = {"from_attributes": True}


class EventReadDetail(EventRead):
    slots: List[SlotRead] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Slot
# ---------------------------------------------------------------------------


class SlotUpdate(BaseModel):
    max_personnes: int


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


class AvailabilityRead(BaseModel):
    id: int
    evenement_id: int
    membre_id: int
    creneau_id: int
    statut: AvailabilityStatusEnum

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------


class CsvImportResult(BaseModel):
    imported_count: int
    pending: List[PendingNameResolution] = []


class PendingNameResolution(BaseModel):
    csv_name: str
    suggestions: List[NameSuggestion] = []


class NameSuggestion(BaseModel):
    member_id: int
    display_name: str
    score: float


class ResolveEntry(BaseModel):
    csv_name: str
    member_id: Optional[int] = None  # None = create new member
    create_new: bool = False


class ResolvePendingRequest(BaseModel):
    resolutions: List[ResolveEntry]
    # Pass back the pending CSV data so the server can save availabilities
    pending_data: List[PendingRowData]


class PendingRowData(BaseModel):
    csv_name: str
    availabilities: List[PendingAvailability]


class PendingAvailability(BaseModel):
    slot_label: str  # "2026-04-23 (17:00 - 18:00)"
    statut: AvailabilityStatusEnum


# Rebuild forward references
CsvImportResult.model_rebuild()


# ---------------------------------------------------------------------------
# Respo bar
# ---------------------------------------------------------------------------


class RespoBarEntry(BaseModel):
    membre_id: int
    ordre: int


class RespoBarList(BaseModel):
    respos: List[RespoBarEntry]


class RespoBarRead(BaseModel):
    id: int
    evenement_id: int
    membre_id: int
    ordre: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Affinity
# ---------------------------------------------------------------------------


class AffinityCreate(BaseModel):
    membre_a_id: int
    membre_b_id: int


class AffinityRead(BaseModel):
    id: int
    evenement_id: int
    membre_a_id: int
    membre_b_id: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------


class AssignmentRead(BaseModel):
    id: int
    creneau_id: int
    membre_id: int
    type: AssignmentTypeEnum
    source: AssignmentSourceEnum
    maybe_force: bool

    model_config = {"from_attributes": True}


class AssignmentCreate(BaseModel):
    creneau_id: int
    membre_id: int
    type: AssignmentTypeEnum = AssignmentTypeEnum.staff
    source: AssignmentSourceEnum = AssignmentSourceEnum.manuel


class AssignmentUpdate(BaseModel):
    type: Optional[AssignmentTypeEnum] = None
    maybe_force: Optional[bool] = None


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


class WarningItem(BaseModel):
    type: str
    slot_id: Optional[int] = None
    member_id: Optional[int] = None
    message: str


class GenerateResponse(BaseModel):
    warnings: List[WarningItem]
    assignments: List[AssignmentRead]


# ---------------------------------------------------------------------------
# Member stats
# ---------------------------------------------------------------------------


class MemberStatsEntry(BaseModel):
    heure_relative: int
    fois_disponible: int
    fois_staffe: int

    model_config = {"from_attributes": True}


BIEN_MEMBRE_SEUIL_HEURES = 10.0


class MemberStatsRead(BaseModel):
    afterwork: List[MemberStatsEntry] = []
    soiree: List[MemberStatsEntry] = []
    afterwork_slot_labels: dict = {}  # heure_relative -> "HH:MM"
    soiree_slot_labels: dict = {}
    total_heures_afterwork: float = 0.0
    total_heures_soiree: float = 0.0
    total_heures_cumule: float = 0.0
    bien_membre: bool = False


# ---------------------------------------------------------------------------
# Member timeline
# ---------------------------------------------------------------------------


class TimelineSlot(BaseModel):
    heure_debut: datetime
    heure_fin: datetime

    model_config = {"from_attributes": True}


class TimelineEvent(BaseModel):
    event_id: int
    nom: str
    date: datetime
    type: str
    slots: List[TimelineSlot]
    total_heures: float


# ---------------------------------------------------------------------------
# Historical import (image grid format)
# ---------------------------------------------------------------------------


class HistoricalSlot(BaseModel):
    heure_debut: str   # "HH:MM"
    heure_fin: str     # "HH:MM"


class HistoricalAssignment(BaseModel):
    slot_index: int
    type_affectation: str  # "staff" | "respo_bar"


class HistoricalMemberRow(BaseModel):
    csv_name: str
    member_id: Optional[int] = None   # auto-resolved; None = unresolved
    assignments: List[HistoricalAssignment]


class HistoricalUnresolved(BaseModel):
    csv_name: str
    suggestions: List[NameSuggestion] = []


class HistoricalPreviewResponse(BaseModel):
    slots: List[HistoricalSlot]
    members: List[HistoricalMemberRow]
    unresolved: List[HistoricalUnresolved]


class HistoricalResolveEntry(BaseModel):
    csv_name: str
    member_id: Optional[int] = None   # None + create_new=True → create
    create_new: bool = False


class HistoricalImportRequest(BaseModel):
    event_nom: str
    event_date: str         # YYYY-MM-DD
    event_type: EventTypeEnum
    slots: List[HistoricalSlot]
    members: List[HistoricalMemberRow]
    resolutions: List[HistoricalResolveEntry] = []


class HistoricalImportResult(BaseModel):
    event_id: int
    assignments_created: int

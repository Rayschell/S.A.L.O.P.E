"""Pydantic schemas for request/response validation."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

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


class AliasCreate(BaseModel):
    valeur: str


class MergeRequest(BaseModel):
    source_member_id: int


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
    excluded_member_ids: List[int] = []
    last_warnings: Optional[List[dict]] = None

    model_config = {"from_attributes": True}


class ExclusionsUpdate(BaseModel):
    member_ids: List[int] = []


class EventDuplicateRequest(BaseModel):
    nom: Optional[str] = None  # défaut : "<nom source> (copie)"
    date: datetime


# ---------------------------------------------------------------------------
# Slot
# ---------------------------------------------------------------------------


class SlotUpdate(BaseModel):
    max_personnes: int


class SlotCreate(BaseModel):
    heure_debut: datetime
    heure_fin: datetime

    @field_validator("heure_fin")
    @classmethod
    def validate_fin(cls, v: datetime, info) -> datetime:
        debut = info.data.get("heure_debut")
        if debut is not None and v <= debut:
            raise ValueError("heure_fin doit être postérieure à heure_debut")
        return v


class SlotsBulkCreate(BaseModel):
    slots: List[SlotCreate] = Field(min_length=1, max_length=100)
    max_personnes: int = Field(default=3, ge=1, le=99)


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


class GenerateRequest(BaseModel):
    excluded_member_ids: List[int] = []


class GenerateResponse(BaseModel):
    warnings: List[WarningItem]
    assignments: List[AssignmentRead]


class ProposalAssignment(BaseModel):
    creneau_id: int
    membre_id: int
    type: AssignmentTypeEnum
    source: AssignmentSourceEnum
    maybe_force: bool = False


class ProposalItem(BaseModel):
    index: int
    score: int
    warnings: List[WarningItem]
    assignments: List[ProposalAssignment]


class GenerateProposalsRequest(BaseModel):
    excluded_member_ids: List[int] = []
    count: int = 3  # clampé à [2, 3] dans le routeur


class GenerateProposalsResponse(BaseModel):
    proposals: List[ProposalItem]


class ApplyProposalRequest(BaseModel):
    assignments: List[ProposalAssignment]
    warnings: List[WarningItem] = []
    excluded_member_ids: List[int] = []


# ---------------------------------------------------------------------------
# Saison (mandat de bureau)
# ---------------------------------------------------------------------------


class SaisonCreate(BaseModel):
    nom: str
    date_debut: date
    date_fin: Optional[date] = None  # None = saison en cours (pas de fin)

    @field_validator("date_fin")
    @classmethod
    def validate_dates(cls, v: Optional[date], info) -> Optional[date]:
        debut = info.data.get("date_debut")
        if v is not None and debut is not None and v <= debut:
            raise ValueError("date_fin doit être postérieure à date_debut")
        return v


class SaisonUpdate(BaseModel):
    nom: Optional[str] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None


class SaisonRead(BaseModel):
    id: int
    nom: str
    date_debut: date
    date_fin: Optional[date] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Formulaire public de disponibilités
# ---------------------------------------------------------------------------


class PublicSlotOut(BaseModel):
    id: int
    heure_debut: datetime
    heure_fin: datetime

    model_config = {"from_attributes": True}


class PublicPollInfo(BaseModel):
    event_nom: str
    event_date: datetime
    event_type: EventTypeEnum
    ouvert: bool
    raison_fermeture: Optional[str] = None  # "closed" | "deadline"
    slots: List[PublicSlotOut]


class PublicReponse(BaseModel):
    creneau_id: int
    statut: AvailabilityStatusEnum


class PublicSubmissionIn(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    reponses: List[PublicReponse] = Field(min_length=1, max_length=100)

    @field_validator("nom")
    @classmethod
    def strip_nom(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nom vide")
        return v


class PublicSubmissionResult(BaseModel):
    status: str  # "matched" | "pending"


class PublicLinkOut(BaseModel):
    public_token: Optional[str] = None
    inscriptions_ouvertes: bool
    inscriptions_deadline: Optional[datetime] = None
    pending_count: int
    slots_count: int


class PublicLinkUpdate(BaseModel):
    # État complet à chaque PUT (deadline absente = deadline effacée)
    inscriptions_ouvertes: bool
    inscriptions_deadline: Optional[datetime] = None


class PendingSubmissionOut(BaseModel):
    id: int
    csv_name: str
    created_at: datetime
    updated_at: datetime
    suggestions: List[NameSuggestion]
    availabilities: List[PublicReponse]


class PublicResolveEntry(BaseModel):
    csv_name: str
    member_id: Optional[int] = None
    create_new: bool = False
    availabilities: List[PublicReponse]


class PublicResolveRequest(BaseModel):
    resolutions: List[PublicResolveEntry]


# ---------------------------------------------------------------------------
# Member stats
# ---------------------------------------------------------------------------


class MemberOverviewItem(BaseModel):
    id: int
    nom: str
    prenom: str
    roles: List[str]
    heures_afterwork: float
    heures_soiree: float
    heures_total: float
    shifts_respo_bar_cumules: int
    bien_membre: bool


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

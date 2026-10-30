"""SQLAlchemy ORM models."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship

from ..database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EventTypeEnum(str, enum.Enum):
    afterwork = "afterwork"
    soiree = "soiree"


class EventStatutEnum(str, enum.Enum):
    brouillon = "brouillon"
    publie = "publie"


class AvailabilityStatusEnum(str, enum.Enum):
    yes = "yes"
    no = "no"
    maybe = "maybe"


class AssignmentTypeEnum(str, enum.Enum):
    staff = "staff"
    respo_bar = "respo_bar"


class AssignmentSourceEnum(str, enum.Enum):
    auto = "auto"
    manuel = "manuel"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    prenom = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    roles = Column(ARRAY(String), nullable=False, default=list)
    shifts_respo_bar_cumules = Column(Integer, nullable=False, default=0)

    aliases = relationship(
        "MemberAlias", back_populates="member", cascade="all, delete-orphan"
    )
    availabilities = relationship("Availability", back_populates="member")
    assignments = relationship("Assignment", back_populates="member")
    stats = relationship(
        "StatsMemberHeureRelative", back_populates="member", cascade="all, delete-orphan"
    )


class MemberAlias(Base):
    """Variant spellings of a member's name as seen in Strawpoll exports."""

    __tablename__ = "member_aliases"

    id = Column(Integer, primary_key=True, index=True)
    membre_id = Column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    valeur = Column(String, nullable=False)

    member = relationship("Member", back_populates="aliases")

    __table_args__ = (UniqueConstraint("valeur", name="uq_member_alias_valeur"),)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    type = Column(Enum(EventTypeEnum), nullable=False)
    statut = Column(
        Enum(EventStatutEnum), nullable=False, default=EventStatutEnum.brouillon
    )
    excluded_member_ids = Column(
        ARRAY(Integer), nullable=False, default=list, server_default="{}"
    )
    last_warnings = Column(JSONB, nullable=True)
    # Formulaire public de disponibilités (lien /dispo/{token})
    public_token = Column(String, unique=True, nullable=True, index=True)
    inscriptions_ouvertes = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    inscriptions_deadline = Column(DateTime, nullable=True)
    # Logo de l'export PNG — NULL = logo LATEB original
    logo_id = Column(
        Integer, ForeignKey("logos.id", ondelete="SET NULL"), nullable=True
    )

    slots = relationship(
        "Slot", back_populates="event", cascade="all, delete-orphan"
    )
    availabilities = relationship(
        "Availability", back_populates="event", cascade="all, delete-orphan"
    )
    respos_bar = relationship(
        "ResponsableBar", back_populates="event", cascade="all, delete-orphan"
    )
    affinity_constraints = relationship(
        "AffinityConstraint", back_populates="event", cascade="all, delete-orphan"
    )
    pending_submissions = relationship(
        "PendingSubmission", back_populates="event", cascade="all, delete-orphan"
    )


class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True, index=True)
    evenement_id = Column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    heure_debut = Column(DateTime, nullable=False)
    heure_fin = Column(DateTime, nullable=False)
    heure_relative = Column(Integer, nullable=False, default=0)
    max_personnes = Column(Integer, nullable=False, default=3)

    event = relationship("Event", back_populates="slots")
    availabilities = relationship(
        "Availability", back_populates="slot", cascade="all, delete-orphan"
    )
    assignments = relationship(
        "Assignment", back_populates="slot", cascade="all, delete-orphan"
    )


class Availability(Base):
    __tablename__ = "availabilities"

    id = Column(Integer, primary_key=True, index=True)
    evenement_id = Column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    membre_id = Column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    creneau_id = Column(
        Integer, ForeignKey("slots.id", ondelete="CASCADE"), nullable=False
    )
    statut = Column(Enum(AvailabilityStatusEnum), nullable=False)

    event = relationship("Event", back_populates="availabilities")
    member = relationship("Member", back_populates="availabilities")
    slot = relationship("Slot", back_populates="availabilities")

    __table_args__ = (
        UniqueConstraint(
            "evenement_id",
            "membre_id",
            "creneau_id",
            name="uq_availability",
        ),
    )


class ResponsableBar(Base):
    __tablename__ = "responsables_bar"

    id = Column(Integer, primary_key=True, index=True)
    evenement_id = Column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    membre_id = Column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    ordre = Column(Integer, nullable=False, default=0)

    event = relationship("Event", back_populates="respos_bar")
    member = relationship("Member")

    __table_args__ = (
        UniqueConstraint("evenement_id", "membre_id", name="uq_respo_bar"),
    )


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    creneau_id = Column(
        Integer, ForeignKey("slots.id", ondelete="CASCADE"), nullable=False
    )
    membre_id = Column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    type = Column(
        Enum(AssignmentTypeEnum),
        nullable=False,
        default=AssignmentTypeEnum.staff,
    )
    source = Column(
        Enum(AssignmentSourceEnum),
        nullable=False,
        default=AssignmentSourceEnum.auto,
    )
    maybe_force = Column(Boolean, nullable=False, default=False)

    slot = relationship("Slot", back_populates="assignments")
    member = relationship("Member", back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("creneau_id", "membre_id", name="uq_assignment"),
    )


class AffinityConstraint(Base):
    __tablename__ = "affinity_constraints"

    id = Column(Integer, primary_key=True, index=True)
    evenement_id = Column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    membre_a_id = Column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    membre_b_id = Column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )

    event = relationship("Event", back_populates="affinity_constraints")
    membre_a = relationship("Member", foreign_keys=[membre_a_id])
    membre_b = relationship("Member", foreign_keys=[membre_b_id])

    __table_args__ = (
        UniqueConstraint(
            "evenement_id", "membre_a_id", "membre_b_id", name="uq_affinity"
        ),
    )


class PendingSubmission(Base):
    """Soumission du formulaire public dont le nom n'a pas matché un membre.

    Conservée avec le nom brut jusqu'à résolution par le bureau (choisir un
    membre / créer / ignorer). `reponses` = [{"creneau_id": int, "statut": str}].
    """

    __tablename__ = "pending_submissions"

    id = Column(Integer, primary_key=True, index=True)
    evenement_id = Column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    nom_saisi = Column(String, nullable=False)
    nom_normalise = Column(String, nullable=False)
    reponses = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    event = relationship("Event", back_populates="pending_submissions")

    __table_args__ = (
        UniqueConstraint(
            "evenement_id", "nom_normalise", name="uq_pending_submission_event_nom"
        ),
    )


class Logo(Base):
    """Logo importé (ex : spécial Halloween), choisissable par événement pour l'export PNG.

    `contenu` est toujours un PNG RGBA normalisé (bords transparents rognés).
    """

    __tablename__ = "logos"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    contenu = Column(LargeBinary, nullable=False)
    # Thème de l'export dérivé des couleurs du logo (sinon thème LATEB)
    utiliser_couleurs = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class Saison(Base):
    """Mandat de bureau (~avril → avril) servant de fenêtre de filtrage des stats."""

    __tablename__ = "saisons"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    date_debut = Column(Date, nullable=False)
    date_fin = Column(Date, nullable=True)  # NULL = saison en cours

    __table_args__ = (
        CheckConstraint(
            "date_fin IS NULL OR date_fin > date_debut", name="ck_saison_dates"
        ),
    )


class StatsMemberHeureRelative(Base):
    """Per-member, per-event-type, per-relative-hour statistics."""

    __tablename__ = "stats_member_heure_relative"

    id = Column(Integer, primary_key=True, index=True)
    membre_id = Column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    type_evenement = Column(Enum(EventTypeEnum), nullable=False)
    heure_relative = Column(Integer, nullable=False)
    fois_disponible = Column(Integer, nullable=False, default=0)
    fois_staffe = Column(Integer, nullable=False, default=0)

    member = relationship("Member", back_populates="stats")

    __table_args__ = (
        UniqueConstraint(
            "membre_id", "type_evenement", "heure_relative",
            name="uq_stats_member_heure",
        ),
    )


# ---------------------------------------------------------------------------
# OAuth 2.1 — serveur d'autorisation du MCP (/api/mcp)
# ---------------------------------------------------------------------------


class OAuthClient(Base):
    """Client MCP enregistré dynamiquement (RFC 7591), toujours public."""

    __tablename__ = "oauth_clients"

    client_id = Column(String, primary_key=True)
    client_name = Column(String, nullable=True)
    redirect_uris = Column(ARRAY(String), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class OAuthAuthorizationCode(Base):
    """Code d'autorisation PKCE, usage unique, stocké hashé."""

    __tablename__ = "oauth_authorization_codes"

    id = Column(Integer, primary_key=True)
    code_hash = Column(String, nullable=False, unique=True, index=True)
    client_id = Column(
        String, ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False
    )
    membre_id = Column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    redirect_uri = Column(String, nullable=False)
    code_challenge = Column(String, nullable=False)
    resource = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)


class OAuthToken(Base):
    """Access ou refresh token MCP opaque, stocké hashé.

    `family_id` regroupe les tokens issus d'une même autorisation : la
    réutilisation d'un refresh déjà consommé révoque toute la famille.
    """

    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    type = Column(String, nullable=False)  # "access" | "refresh"
    client_id = Column(
        String, ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False
    )
    membre_id = Column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    family_id = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

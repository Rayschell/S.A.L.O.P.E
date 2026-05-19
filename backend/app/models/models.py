"""SQLAlchemy ORM models."""
from __future__ import annotations

import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
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

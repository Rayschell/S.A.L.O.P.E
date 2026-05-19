"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Créer les types ENUM dans la transaction Alembic via DO blocks
    # (évite le problème de commit hors-transaction avec t.create())
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eventtypeenum AS ENUM ('afterwork', 'soiree');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eventstatutenum AS ENUM ('brouillon', 'publie');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE availabilitystatusenum AS ENUM ('yes', 'no', 'maybe');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE assignmenttypeenum AS ENUM ('staff', 'respo_bar');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE assignmentsourceenum AS ENUM ('auto', 'manuel');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("prenom", sa.String(), nullable=False),
        sa.Column("email", sa.String(), unique=True, nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("roles", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("heures_cumulees", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("shifts_respo_bar_cumules", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_members_id", "members", ["id"])
    op.create_index("ix_members_email", "members", ["email"], unique=True)

    op.create_table(
        "member_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("membre_id", sa.Integer(), sa.ForeignKey("members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("valeur", sa.String(), nullable=False),
        sa.UniqueConstraint("valeur", name="uq_member_alias_valeur"),
    )
    op.create_index("ix_member_aliases_id", "member_aliases", ["id"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("type", postgresql.ENUM("afterwork", "soiree", name="eventtypeenum", create_type=False), nullable=False),
        sa.Column("statut", postgresql.ENUM("brouillon", "publie", name="eventstatutenum", create_type=False), nullable=False, server_default="brouillon"),
    )
    op.create_index("ix_events_id", "events", ["id"])

    op.create_table(
        "slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evenement_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("heure_debut", sa.DateTime(), nullable=False),
        sa.Column("heure_fin", sa.DateTime(), nullable=False),
        sa.Column("max_personnes", sa.Integer(), nullable=False, server_default="3"),
    )
    op.create_index("ix_slots_id", "slots", ["id"])

    op.create_table(
        "availabilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evenement_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("membre_id", sa.Integer(), sa.ForeignKey("members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creneau_id", sa.Integer(), sa.ForeignKey("slots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("statut", postgresql.ENUM("yes", "no", "maybe", name="availabilitystatusenum", create_type=False), nullable=False),
        sa.UniqueConstraint("evenement_id", "membre_id", "creneau_id", name="uq_availability"),
    )
    op.create_index("ix_availabilities_id", "availabilities", ["id"])

    op.create_table(
        "responsables_bar",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evenement_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("membre_id", sa.Integer(), sa.ForeignKey("members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordre", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("evenement_id", "membre_id", name="uq_respo_bar"),
    )
    op.create_index("ix_responsables_bar_id", "responsables_bar", ["id"])

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("creneau_id", sa.Integer(), sa.ForeignKey("slots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("membre_id", sa.Integer(), sa.ForeignKey("members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", postgresql.ENUM("staff", "respo_bar", name="assignmenttypeenum", create_type=False), nullable=False, server_default="staff"),
        sa.Column("source", postgresql.ENUM("auto", "manuel", name="assignmentsourceenum", create_type=False), nullable=False, server_default="auto"),
        sa.Column("maybe_force", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("creneau_id", "membre_id", name="uq_assignment"),
    )
    op.create_index("ix_assignments_id", "assignments", ["id"])

    op.create_table(
        "affinity_constraints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evenement_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("membre_a_id", sa.Integer(), sa.ForeignKey("members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("membre_b_id", sa.Integer(), sa.ForeignKey("members.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("evenement_id", "membre_a_id", "membre_b_id", name="uq_affinity"),
    )
    op.create_index("ix_affinity_constraints_id", "affinity_constraints", ["id"])


def downgrade() -> None:
    op.drop_table("affinity_constraints")
    op.drop_table("assignments")
    op.drop_table("responsables_bar")
    op.drop_table("availabilities")
    op.drop_table("slots")
    op.drop_table("events")
    op.drop_table("member_aliases")
    op.drop_table("members")

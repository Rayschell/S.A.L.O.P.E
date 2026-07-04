"""Formulaire public de disponibilités : lien par token + soumissions en attente.

Revision ID: 008
Revises: 007
Create Date: 2026-07-04 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("public_token", sa.String(), nullable=True))
    op.create_index(
        "ix_events_public_token", "events", ["public_token"], unique=True
    )
    op.add_column(
        "events",
        sa.Column(
            "inscriptions_ouvertes",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "events", sa.Column("inscriptions_deadline", sa.DateTime(), nullable=True)
    )

    op.create_table(
        "pending_submissions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "evenement_id",
            sa.Integer(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nom_saisi", sa.String(), nullable=False),
        sa.Column("nom_normalise", sa.String(), nullable=False),
        sa.Column("reponses", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "evenement_id", "nom_normalise", name="uq_pending_submission_event_nom"
        ),
    )


def downgrade() -> None:
    op.drop_table("pending_submissions")
    op.drop_column("events", "inscriptions_deadline")
    op.drop_column("events", "inscriptions_ouvertes")
    op.drop_index("ix_events_public_token", table_name="events")
    op.drop_column("events", "public_token")

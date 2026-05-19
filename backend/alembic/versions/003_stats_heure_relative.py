"""Replace per-type hour counters with stats_member_heure_relative table

Revision ID: 003
Revises: 002
Create Date: 2026-05-19 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop per-type hour counters added in 002
    op.drop_column("members", "heures_afterwork")
    op.drop_column("members", "heures_soiree")
    op.drop_column("members", "nb_events_afterwork")
    op.drop_column("members", "nb_events_soiree")

    # Add heure_relative to slots
    op.add_column(
        "slots",
        sa.Column("heure_relative", sa.Integer(), nullable=False, server_default="0"),
    )

    # Create stats table
    op.create_table(
        "stats_member_heure_relative",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "membre_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type_evenement",
            postgresql.ENUM("afterwork", "soiree", name="eventtypeenum", create_type=False),
            nullable=False,
        ),
        sa.Column("heure_relative", sa.Integer(), nullable=False),
        sa.Column("fois_disponible", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fois_staffe", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "membre_id", "type_evenement", "heure_relative",
            name="uq_stats_member_heure",
        ),
    )
    op.create_index("ix_stats_member_heure_relative_id", "stats_member_heure_relative", ["id"])


def downgrade() -> None:
    op.drop_index("ix_stats_member_heure_relative_id", "stats_member_heure_relative")
    op.drop_table("stats_member_heure_relative")
    op.drop_column("slots", "heure_relative")
    op.add_column(
        "members",
        sa.Column("heures_afterwork", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "members",
        sa.Column("heures_soiree", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "members",
        sa.Column("nb_events_afterwork", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "members",
        sa.Column("nb_events_soiree", sa.Integer(), nullable=False, server_default="0"),
    )

"""Split heures_cumulees into per-type hour tracking

Revision ID: 002
Revises: 001
Create Date: 2026-05-19 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old single counter
    op.drop_column("members", "heures_cumulees")

    # Add per-type hour counters
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


def downgrade() -> None:
    op.drop_column("members", "heures_afterwork")
    op.drop_column("members", "heures_soiree")
    op.drop_column("members", "nb_events_afterwork")
    op.drop_column("members", "nb_events_soiree")
    op.add_column(
        "members",
        sa.Column("heures_cumulees", sa.Float(), nullable=False, server_default="0.0"),
    )

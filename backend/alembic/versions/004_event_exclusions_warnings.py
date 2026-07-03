"""Persist member exclusions and last generation warnings on events

Revision ID: 004
Revises: 003
Create Date: 2026-07-02 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "excluded_member_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "events",
        sa.Column("last_warnings", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("events", "last_warnings")
    op.drop_column("events", "excluded_member_ids")

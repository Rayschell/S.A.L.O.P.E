"""Logos d'export PNG choisissables par événement.

Revision ID: 009
Revises: 008
Create Date: 2026-10-28 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "logos",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("contenu", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.add_column(
        "events",
        sa.Column(
            "logo_id",
            sa.Integer(),
            sa.ForeignKey("logos.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("events", "logo_id")
    op.drop_table("logos")

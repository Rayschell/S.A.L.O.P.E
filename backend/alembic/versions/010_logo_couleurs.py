"""Option « utiliser les couleurs du logo » pour le thème de l'export.

Revision ID: 010
Revises: 009
Create Date: 2026-10-28 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "logos",
        sa.Column(
            "utiliser_couleurs", sa.Boolean(), nullable=False, server_default="true"
        ),
    )


def downgrade() -> None:
    op.drop_column("logos", "utiliser_couleurs")

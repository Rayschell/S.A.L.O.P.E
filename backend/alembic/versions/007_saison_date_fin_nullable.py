"""Saison en cours : date_fin devient nullable (NULL = pas de fin).

Revision ID: 007
Revises: 006
Create Date: 2026-07-03 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("saisons", "date_fin", existing_type=sa.Date(), nullable=True)
    op.drop_constraint("ck_saison_dates", "saisons", type_="check")
    op.create_check_constraint(
        "ck_saison_dates", "saisons", "date_fin IS NULL OR date_fin > date_debut"
    )


def downgrade() -> None:
    op.drop_constraint("ck_saison_dates", "saisons", type_="check")
    op.execute("UPDATE saisons SET date_fin = date_debut + INTERVAL '1 year' WHERE date_fin IS NULL")
    op.alter_column("saisons", "date_fin", existing_type=sa.Date(), nullable=False)
    op.create_check_constraint("ck_saison_dates", "saisons", "date_fin > date_debut")

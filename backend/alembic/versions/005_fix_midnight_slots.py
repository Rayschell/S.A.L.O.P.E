"""Fix slots crossing midnight: heure_fin was stored on the same day as
heure_debut (e.g. 23:00 -> 00:00 gave a negative duration).

Revision ID: 005
Revises: 004
Create Date: 2026-07-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE slots SET heure_fin = heure_fin + INTERVAL '1 day' "
        "WHERE heure_fin <= heure_debut"
    )


def downgrade() -> None:
    # Irreversible data fix — nothing sensible to undo.
    pass

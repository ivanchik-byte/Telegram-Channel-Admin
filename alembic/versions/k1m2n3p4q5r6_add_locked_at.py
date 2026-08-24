"""add locked_at for stale ai_processing reaper

Revision ID: k1m2n3p4q5r6
Revises: a8b9c0d1e2f3
Create Date: 2026-08-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k1m2n3p4q5r6'
down_revision: Union[str, None] = 'a8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'processed_posts',
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('processed_posts', 'locked_at')

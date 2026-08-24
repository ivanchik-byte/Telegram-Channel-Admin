"""Add 'accumulated' status to chk_status constraint

Revision ID: a8b9c0d1e2f3
Revises: f6a7b8c9d0e1
Create Date: 2026-08-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_STATUSES = (
    "'seen', 'queued', 'ai_processing', 'processed', 'failed', "
    "'moderating', 'published', 'rejected', 'filtered_ad', 'duplicate_content'"
)
NEW_STATUSES = OLD_STATUSES + ", 'accumulated'"


def upgrade() -> None:
    with op.batch_alter_table('processed_posts') as batch_op:
        batch_op.drop_constraint('chk_status', type_='check')
        batch_op.create_check_constraint(
            'chk_status',
            f"status IN ({NEW_STATUSES})"
        )


def downgrade() -> None:
    # Move rows out of 'accumulated' before restoring the old constraint
    op.execute("UPDATE processed_posts SET status = 'queued' WHERE status = 'accumulated'")
    with op.batch_alter_table('processed_posts') as batch_op:
        batch_op.drop_constraint('chk_status', type_='check')
        batch_op.create_check_constraint(
            'chk_status',
            f"status IN ({OLD_STATUSES})"
        )

"""Expand status column from VARCHAR(20) to VARCHAR(50)

Revision ID: b2c3d4e5f6a7
Revises: 7e65b908e8e2
Create Date: 2026-07-12 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = '7e65b908e8e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'processed_posts',
        'status',
        existing_type=sa.String(length=20),
        type_=sa.String(length=50),
        existing_nullable=False
    )


def downgrade() -> None:
    op.alter_column(
        'processed_posts',
        'status',
        existing_type=sa.String(length=50),
        type_=sa.String(length=20),
        existing_nullable=False
    )

"""add queue_limit column to bot_settings

Revision ID: d4e5f6a7b8c9
Revises: 0c7e681b8806
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = '0c7e681b8806'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bot_settings', sa.Column('queue_limit', sa.Integer(), nullable=False, server_default='5'))


def downgrade() -> None:
    op.drop_column('bot_settings', 'queue_limit')

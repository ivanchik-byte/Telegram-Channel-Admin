"""add ui_lang and post_lang columns to bot_settings

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bot_settings', sa.Column('ui_lang', sa.String(length=10), nullable=False, server_default='ru'))
    op.add_column('bot_settings', sa.Column('post_lang', sa.String(length=10), nullable=False, server_default='ru'))


def downgrade() -> None:
    op.drop_column('bot_settings', 'post_lang')
    op.drop_column('bot_settings', 'ui_lang')

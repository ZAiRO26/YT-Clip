"""add_project_custom_prompt

Revision ID: 9b3c4d5e6f70
Revises: 8a2b3c4d5e6f
Create Date: 2026-10-10 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b3c4d5e6f70'
down_revision: Union[str, None] = '8a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('custom_prompt', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'custom_prompt')

"""add_project_default_music_track

Revision ID: 6f1a892cb310
Revises: 5e32881da290
Create Date: 2026-09-03 02:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f1a892cb310'
down_revision: Union[str, None] = '5e32881da290'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('default_music_track', sa.Text(), server_default=sa.text("'none'"), nullable=False))


def downgrade() -> None:
    op.drop_column('projects', 'default_music_track')

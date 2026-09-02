"""add_project_styling_defaults

Revision ID: 5e32881da290
Revises: 4c21671da280
Create Date: 2026-09-02 22:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5e32881da290'
down_revision: Union[str, None] = '4c21671da280'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('crop_mode', sa.Text(), server_default=sa.text("'face_track'"), nullable=False))
    op.add_column('projects', sa.Column('default_effects', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column('projects', sa.Column('default_voice_id', sa.Text(), server_default=sa.text("'af_bella'"), nullable=False))


def downgrade() -> None:
    op.drop_column('projects', 'default_voice_id')
    op.drop_column('projects', 'default_effects')
    op.drop_column('projects', 'crop_mode')

"""add_project_time_window_and_focus

Revision ID: 7a1b2c3d4e5f
Revises: 6f1a892cb310
Create Date: 2026-09-03 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a1b2c3d4e5f'
down_revision: Union[str, None] = '6f1a892cb310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('time_range_start', sa.Float(), nullable=True))
    op.add_column('projects', sa.Column('time_range_end', sa.Float(), nullable=True))
    op.add_column('projects', sa.Column(
        'temporal_distribution',
        sa.Text(),
        server_default=sa.text("'even_spread'"),
        nullable=False,
    ))
    op.add_column('projects', sa.Column(
        'content_focus',
        sa.Text(),
        server_default=sa.text("'balanced'"),
        nullable=False,
    ))
    op.create_check_constraint(
        'ck_projects_temporal_distribution',
        'projects',
        "temporal_distribution IN ('even_spread', 'focus_window', 'top_moments')",
    )
    op.create_check_constraint(
        'ck_projects_content_focus',
        'projects',
        "content_focus IN ('balanced', 'contestant_primary', 'judges_primary')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_projects_content_focus', 'projects', type_='check')
    op.drop_constraint('ck_projects_temporal_distribution', 'projects', type_='check')
    op.drop_column('projects', 'content_focus')
    op.drop_column('projects', 'temporal_distribution')
    op.drop_column('projects', 'time_range_end')
    op.drop_column('projects', 'time_range_start')

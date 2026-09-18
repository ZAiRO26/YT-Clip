"""add_stacked_speaker_crop_mode

Revision ID: 8a2b3c4d5e6f
Revises: 70e87509f319
Create Date: 2026-09-06 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a2b3c4d5e6f'
down_revision: Union[str, None] = '70e87509f319'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        'ck_projects_crop_mode',
        'projects',
        "crop_mode IN ('face_track', 'blur_background', 'center', 'stacked_speaker')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_projects_crop_mode', 'projects', type_='check')

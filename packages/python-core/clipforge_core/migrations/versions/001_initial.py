"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Schema matches Base.metadata from clipforge_core.models
    pass


def downgrade() -> None:
    pass

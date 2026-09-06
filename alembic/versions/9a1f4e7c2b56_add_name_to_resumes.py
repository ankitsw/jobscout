"""add name to resumes

Revision ID: 9a1f4e7c2b56
Revises: 7b3e0c1a9d24
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9a1f4e7c2b56'
down_revision: Union[str, Sequence[str], None] = '7b3e0c1a9d24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default is required: resumes already has rows in production.
    op.add_column('resumes', sa.Column('name', sa.Text(), nullable=False, server_default=''))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('resumes', 'name')

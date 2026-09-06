"""add workplace_type to jobs

Revision ID: f2c7a658e590
Revises: 5592f4bc8ede
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f2c7a658e590'
down_revision: Union[str, Sequence[str], None] = '5592f4bc8ede'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default is required: jobs already has rows in production.
    op.add_column('jobs', sa.Column('workplace_type', sa.Text(), nullable=False, server_default=''))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('jobs', 'workplace_type')

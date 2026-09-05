"""add job_type to jobs

Revision ID: 5592f4bc8ede
Revises: 8b1885354f01
Create Date: 2026-09-05 22:24:26.107851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5592f4bc8ede'
down_revision: Union[str, Sequence[str], None] = '8b1885354f01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default is required: jobs already has rows in production.
    op.add_column('jobs', sa.Column('job_type', sa.Text(), nullable=False, server_default=''))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('jobs', 'job_type')

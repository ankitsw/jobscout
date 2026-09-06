"""add generated_cvs table

Revision ID: 7b3e0c1a9d24
Revises: f2c7a658e590
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7b3e0c1a9d24'
down_revision: Union[str, Sequence[str], None] = 'f2c7a658e590'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'generated_cvs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('resume_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'generated_cv_resume_job_unique_idx', 'generated_cvs',
        ['resume_id', 'job_id'], unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('generated_cv_resume_job_unique_idx', table_name='generated_cvs')
    op.drop_table('generated_cvs')

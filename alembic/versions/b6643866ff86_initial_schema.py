"""initial schema

Revision ID: b6643866ff86
Revises: 
Create Date: 2026-09-04 10:39:54.535161

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'b6643866ff86'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "resumes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("experience_required", sa.String(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("easy_apply", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("emailed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("flagged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "fts", TSVECTOR(),
            sa.Computed("to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))", persisted=True),
            nullable=True,
        ),
    )
    op.create_index("jobs_url_unique", "jobs", ["url"], unique=True)
    op.create_index("jobs_fts_idx", "jobs", ["fts"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("jobs_fts_idx", table_name="jobs")
    op.drop_index("jobs_url_unique", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("resumes")

"""add story directory table

Revision ID: 20260415_000005
Revises: 20260414_000004
Create Date: 2026-04-15 00:00:05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260415_000005"
down_revision: Union[str, Sequence[str], None] = "20260414_000004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "story_directories" not in existing_tables:
        op.create_table(
            "story_directories",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("story_planning_id", sa.String(length=36), nullable=True),
            sa.Column("directory_title", sa.String(length=200), nullable=False, server_default="全书章节目录"),
            sa.Column("directory_summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("directory_status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("chapter_items", sa.JSON(), nullable=False),
            sa.Column("last_update_source", sa.String(length=50), nullable=False, server_default="manual"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("directory_status in ('draft', 'confirmed')", name="ck_story_directories_status"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["story_planning_id"], ["story_plannings.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", name="uq_story_directories_project"),
        )

    refreshed_tables = set(sa.inspect(bind).get_table_names())
    if "story_directories" in refreshed_tables:
        existing_indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("story_directories")}
        index_name = op.f("ix_story_directories_project_id")
        if index_name not in existing_indexes:
            op.create_index(index_name, "story_directories", ["project_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "story_directories" in existing_tables:
        index_name = op.f("ix_story_directories_project_id")
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("story_directories")}
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="story_directories")
        op.drop_table("story_directories")

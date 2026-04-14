"""add story planning table

Revision ID: 20260414_000004
Revises: 20260414_000003
Create Date: 2026-04-14 00:00:04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260414_000004"
down_revision: Union[str, Sequence[str], None] = "20260414_000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "story_plannings" not in existing_tables:
        op.create_table(
            "story_plannings",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("worldview", sa.Text(), nullable=False, server_default=""),
            sa.Column("main_outline", sa.Text(), nullable=False, server_default=""),
            sa.Column("volume_plan", sa.Text(), nullable=False, server_default=""),
            sa.Column("core_seed_summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("planning_status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("last_update_source", sa.String(length=50), nullable=False, server_default="manual"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("planning_status in ('draft', 'confirmed')", name="ck_story_plannings_status"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", name="uq_story_plannings_project"),
        )

    index_name = op.f("ix_story_plannings_project_id")
    refreshed_tables = set(sa.inspect(bind).get_table_names())
    if "story_plannings" in refreshed_tables:
        existing_indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("story_plannings")}
        if index_name not in existing_indexes:
            op.create_index(index_name, "story_plannings", ["project_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "story_plannings" in existing_tables:
        index_name = op.f("ix_story_plannings_project_id")
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("story_plannings")}
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="story_plannings")
        op.drop_table("story_plannings")

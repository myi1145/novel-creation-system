"""add structured card candidates table

Revision ID: 20260415_000006
Revises: 20260415_000005
Create Date: 2026-04-15 00:00:06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260415_000006"
down_revision: Union[str, Sequence[str], None] = "20260415_000005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "structured_card_candidates" not in existing_tables:
        op.create_table(
            "structured_card_candidates",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("source_type", sa.String(length=50), nullable=False, server_default="story_planning_directory"),
            sa.Column("source_id", sa.String(length=36), nullable=False),
            sa.Column("card_type", sa.String(length=30), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("created_card_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "card_type in ('character', 'terminology', 'faction', 'location')",
                name="ck_structured_card_candidates_card_type",
            ),
            sa.CheckConstraint("status in ('pending', 'confirmed', 'skipped')", name="ck_structured_card_candidates_status"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    refreshed = sa.inspect(bind)
    existing_indexes = {idx["name"] for idx in refreshed.get_indexes("structured_card_candidates")}
    index_specs = [
        ("ix_structured_card_candidates_project_id", ["project_id"]),
        ("ix_structured_card_candidates_project_status", ["project_id", "status"]),
        ("ix_structured_card_candidates_project_card_type", ["project_id", "card_type"]),
    ]
    for name, columns in index_specs:
        if name not in existing_indexes:
            op.create_index(name, "structured_card_candidates", columns, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "structured_card_candidates" in existing_tables:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("structured_card_candidates")}
        for index_name in [
            "ix_structured_card_candidates_project_card_type",
            "ix_structured_card_candidates_project_status",
            "ix_structured_card_candidates_project_id",
        ]:
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name="structured_card_candidates")
        op.drop_table("structured_card_candidates")

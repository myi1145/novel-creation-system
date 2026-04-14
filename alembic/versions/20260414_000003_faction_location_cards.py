"""add faction and location structured cards

Revision ID: 20260414_000003
Revises: 20260414_000002
Create Date: 2026-04-14 00:00:03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260414_000003"
down_revision: Union[str, Sequence[str], None] = "20260414_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "structured_faction_cards" not in existing_tables:
        op.create_table(
            "structured_faction_cards",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("aliases", sa.JSON(), nullable=False),
            sa.Column("faction_type", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("core_members", sa.JSON(), nullable=False),
            sa.Column("territory", sa.Text(), nullable=False),
            sa.Column("stance", sa.Text(), nullable=False),
            sa.Column("goals", sa.Text(), nullable=False),
            sa.Column("relationship_notes", sa.Text(), nullable=False),
            sa.Column("current_status", sa.Text(), nullable=False),
            sa.Column("first_appearance_chapter", sa.Integer(), nullable=True),
            sa.Column("last_update_source", sa.String(length=50), nullable=False),
            sa.Column("is_canon", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    faction_index_name = op.f("ix_structured_faction_cards_project_id")
    faction_indexes = {idx["name"] for idx in inspector.get_indexes("structured_faction_cards")} if "structured_faction_cards" in set(sa.inspect(bind).get_table_names()) else set()
    if "structured_faction_cards" in set(sa.inspect(bind).get_table_names()) and faction_index_name not in faction_indexes:
        op.create_index(faction_index_name, "structured_faction_cards", ["project_id"], unique=False)

    if "structured_location_cards" not in existing_tables:
        op.create_table(
            "structured_location_cards",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("aliases", sa.JSON(), nullable=False),
            sa.Column("location_type", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("region", sa.Text(), nullable=False),
            sa.Column("key_features", sa.JSON(), nullable=False),
            sa.Column("related_factions", sa.JSON(), nullable=False),
            sa.Column("narrative_role", sa.Text(), nullable=False),
            sa.Column("current_status", sa.Text(), nullable=False),
            sa.Column("first_appearance_chapter", sa.Integer(), nullable=True),
            sa.Column("last_update_source", sa.String(length=50), nullable=False),
            sa.Column("is_canon", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    location_index_name = op.f("ix_structured_location_cards_project_id")
    location_indexes = {idx["name"] for idx in inspector.get_indexes("structured_location_cards")} if "structured_location_cards" in set(sa.inspect(bind).get_table_names()) else set()
    if "structured_location_cards" in set(sa.inspect(bind).get_table_names()) and location_index_name not in location_indexes:
        op.create_index(location_index_name, "structured_location_cards", ["project_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "structured_location_cards" in existing_tables:
        idx_name = op.f("ix_structured_location_cards_project_id")
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("structured_location_cards")}
        if idx_name in existing_indexes:
            op.drop_index(idx_name, table_name="structured_location_cards")
        op.drop_table("structured_location_cards")

    if "structured_faction_cards" in existing_tables:
        idx_name = op.f("ix_structured_faction_cards_project_id")
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("structured_faction_cards")}
        if idx_name in existing_indexes:
            op.drop_index(idx_name, table_name="structured_faction_cards")
        op.drop_table("structured_faction_cards")

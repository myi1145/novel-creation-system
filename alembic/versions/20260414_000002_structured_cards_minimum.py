"""add structured cards minimum tables

Revision ID: 20260414_000002
Revises: 20260403_000001
Create Date: 2026-04-14 00:00:02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260414_000002"
down_revision: Union[str, Sequence[str], None] = "20260403_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "structured_character_cards" not in existing_tables:
        op.create_table(
            "structured_character_cards",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("aliases", sa.JSON(), nullable=False),
            sa.Column("role_position", sa.Text(), nullable=False),
            sa.Column("profile", sa.Text(), nullable=False),
            sa.Column("personality_keywords", sa.JSON(), nullable=False),
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

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("structured_character_cards")} if "structured_character_cards" in set(sa.inspect(bind).get_table_names()) else set()
    index_name = op.f("ix_structured_character_cards_project_id")
    if "structured_character_cards" in set(sa.inspect(bind).get_table_names()) and index_name not in existing_indexes:
        op.create_index(index_name, "structured_character_cards", ["project_id"], unique=False)

    if "terminology_cards" not in set(sa.inspect(bind).get_table_names()):
        op.create_table(
            "terminology_cards",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("term", sa.String(length=120), nullable=False),
            sa.Column("term_type", sa.String(length=120), nullable=False),
            sa.Column("definition", sa.Text(), nullable=False),
            sa.Column("usage_rules", sa.Text(), nullable=False),
            sa.Column("examples", sa.JSON(), nullable=False),
            sa.Column("first_appearance_chapter", sa.Integer(), nullable=True),
            sa.Column("last_update_source", sa.String(length=50), nullable=False),
            sa.Column("is_canon", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    terminology_indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("terminology_cards")} if "terminology_cards" in set(sa.inspect(bind).get_table_names()) else set()
    terminology_index_name = op.f("ix_terminology_cards_project_id")
    if "terminology_cards" in set(sa.inspect(bind).get_table_names()) and terminology_index_name not in terminology_indexes:
        op.create_index(terminology_index_name, "terminology_cards", ["project_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "terminology_cards" in existing_tables:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("terminology_cards")}
        idx_name = op.f("ix_terminology_cards_project_id")
        if idx_name in existing_indexes:
            op.drop_index(idx_name, table_name="terminology_cards")
        op.drop_table("terminology_cards")

    if "structured_character_cards" in existing_tables:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("structured_character_cards")}
        idx_name = op.f("ix_structured_character_cards_project_id")
        if idx_name in existing_indexes:
            op.drop_index(idx_name, table_name="structured_character_cards")
        op.drop_table("structured_character_cards")

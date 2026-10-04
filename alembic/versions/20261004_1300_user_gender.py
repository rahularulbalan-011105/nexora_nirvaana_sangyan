"""add optional user gender (avatar selection)

Revision ID: 3b9d2c1e4f70
Revises: 7812fa6667da
Create Date: 2026-10-04 13:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "3b9d2c1e4f70"
down_revision = "7812fa6667da"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("gender", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("gender")

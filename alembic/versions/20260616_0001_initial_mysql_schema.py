"""initial mysql schema

Revision ID: 20260616_0001
Revises:
Create Date: 2026-06-16
"""

from alembic import op

from app.db.base import Base
import app.db.models  # noqa: F401 - register all models


revision = "20260616_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

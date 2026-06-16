"""add item raw region fields

Revision ID: 20260616_0001
Revises:
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20260616_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("item", sa.Column("region_text", sa.String(length=200), nullable=True))
    op.add_column("item", sa.Column("region_sgg", sa.String(length=100), nullable=True))
    op.add_column("item", sa.Column("region_emd", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("item", "region_emd")
    op.drop_column("item", "region_sgg")
    op.drop_column("item", "region_text")

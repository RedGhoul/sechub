"""backfill progress cursor

Revision ID: a1b2c3d4e5f6
Revises: 99b58e1fb222
Create Date: 2026-06-05 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '99b58e1fb222'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'backfill_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('quarter', sa.Integer(), nullable=False),
        sa.Column('forms', sa.String(length=255), nullable=False),
        sa.Column('filings_seen', sa.Integer(), nullable=False),
        sa.Column('filings_ingested', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('year', 'quarter', name='uq_backfill_year_quarter'),
    )


def downgrade() -> None:
    op.drop_table('backfill_progress')

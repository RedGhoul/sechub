"""security issuer_cik

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-06 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('security', sa.Column('issuer_cik', sa.String(length=10), nullable=True))
    op.create_index(op.f('ix_security_issuer_cik'), 'security', ['issuer_cik'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_security_issuer_cik'), table_name='security')
    op.drop_column('security', 'issuer_cik')

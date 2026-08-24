"""add claim evidence fields

Revision ID: c2a7d5b9e4f3
Revises: b1e9f8c4a2d1
Create Date: 2026-08-14 00:10:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c2a7d5b9e4f3'
down_revision = 'b1e9f8c4a2d1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('claims', sa.Column('authorization_present', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('claims', sa.Column('documentation_present', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('claims', sa.Column('coding_matches', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('claims', sa.Column('last_followup_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('claims', 'last_followup_at')
    op.drop_column('claims', 'coding_matches')
    op.drop_column('claims', 'documentation_present')
    op.drop_column('claims', 'authorization_present')

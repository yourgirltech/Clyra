"""add payer config and issue fields

Revision ID: b1e9f8c4a2d1
Revises: bab5246eaeb6
Create Date: 2026-08-14 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b1e9f8c4a2d1'
down_revision = 'bab5246eaeb6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('payers', sa.Column('authorization_required', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('payers', sa.Column('documentation_required', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('payers', sa.Column('follow_up_threshold_days', sa.Integer(), nullable=False, server_default='30'))

    op.add_column('claim_issues', sa.Column('issue_type', sa.String(length=64), nullable=False, server_default=''))
    op.add_column('claim_issues', sa.Column('severity', sa.String(length=16), nullable=False, server_default='low'))
    op.add_column('claim_issues', sa.Column('evidence', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('claim_issues', 'evidence')
    op.drop_column('claim_issues', 'severity')
    op.drop_column('claim_issues', 'issue_type')

    op.drop_column('payers', 'follow_up_threshold_days')
    op.drop_column('payers', 'documentation_required')
    op.drop_column('payers', 'authorization_required')

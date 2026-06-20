"""003_add_actual_outcome_cols

Add actual_duration_mins, actual_closure, actual_officer_count to triage_log
for post-event learning system.

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'triage_log',
        sa.Column('actual_duration_mins', sa.Float(), nullable=True)
    )
    op.add_column(
        'triage_log',
        sa.Column('actual_closure', sa.Boolean(), nullable=True)
    )
    op.add_column(
        'triage_log',
        sa.Column('actual_officer_count', sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('triage_log', 'actual_officer_count')
    op.drop_column('triage_log', 'actual_closure')
    op.drop_column('triage_log', 'actual_duration_mins')
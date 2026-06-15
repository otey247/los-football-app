"""Add ScheduledReport and UsageEvent models

Revision ID: b7c8d9e0f1a2
Revises: b2c3d4e5f6a7
Create Date: 2026-06-15 06:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'b7c8d9e0f1a2'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scheduledreport',
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('league_id', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('stat_keys', sa.Text(), nullable=False),
        sa.Column('recipient_email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('frequency', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'usageevent',
        sa.Column('event_type', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('target', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('path', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_usageevent_event_type'), 'usageevent', ['event_type'], unique=False)
    op.create_index(op.f('ix_usageevent_target'), 'usageevent', ['target'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_usageevent_target'), table_name='usageevent')
    op.drop_index(op.f('ix_usageevent_event_type'), table_name='usageevent')
    op.drop_table('usageevent')
    op.drop_table('scheduledreport')

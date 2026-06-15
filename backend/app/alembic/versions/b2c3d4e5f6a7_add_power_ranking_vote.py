"""Add PowerRankingVote model

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'powerrankingvote',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('league_id', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('voter_id', sa.Uuid(), nullable=False),
        sa.Column('roster_id', sa.Integer(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['voter_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_powerrankingvote_league_id'), 'powerrankingvote', ['league_id'], unique=False
    )
    op.create_index(
        op.f('ix_powerrankingvote_week'), 'powerrankingvote', ['week'], unique=False
    )


def downgrade():
    op.drop_index(op.f('ix_powerrankingvote_week'), table_name='powerrankingvote')
    op.drop_index(op.f('ix_powerrankingvote_league_id'), table_name='powerrankingvote')
    op.drop_table('powerrankingvote')

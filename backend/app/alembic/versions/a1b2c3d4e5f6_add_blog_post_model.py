"""Add BlogPost model

Revision ID: a1b2c3d4e5f6
Revises: fe56fa70289e
Create Date: 2026-04-26 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'fe56fa70289e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'blogpost',
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('slug', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('excerpt', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column('published', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('author_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_blogpost_slug'), 'blogpost', ['slug'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_blogpost_slug'), table_name='blogpost')
    op.drop_table('blogpost')

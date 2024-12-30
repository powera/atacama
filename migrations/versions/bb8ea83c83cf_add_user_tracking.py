"""add user tracking

Revision ID: bb8ea83c83cf
Revises: b9e29fbf2815
Create Date: 2024-12-30 19:20:00.647137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb8ea83c83cf'
down_revision: Union[str, None] = 'b9e29fbf2815'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    # Create new emails table
    with op.batch_alter_table('emails') as batch_op:
        batch_op.add_column(sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id')))
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

def downgrade():
    with op.batch_alter_table('emails') as batch_op:
        batch_op.drop_column('author_id')
    op.drop_table('users')

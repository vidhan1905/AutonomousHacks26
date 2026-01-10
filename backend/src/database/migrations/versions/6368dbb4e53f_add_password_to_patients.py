"""Add password to patients

Revision ID: 6368dbb4e53f
Revises: 7c67e78a2064
Create Date: 2025-01-27 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6368dbb4e53f'
down_revision: Union[str, None] = '7c67e78a2064'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add password column to patients table (if it doesn't exist)
    # Check if column already exists to make migration idempotent
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('patients')]
    
    if 'password' not in columns:
        op.add_column('patients', sa.Column('password', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove password column from patients table
    op.drop_column('patients', 'password')

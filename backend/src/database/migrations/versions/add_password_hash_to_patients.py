"""add password_hash to patients

Revision ID: add_password_hash_patients
Revises: 7c67e78a2064
Create Date: 2025-01-27 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_password_hash_patients'
down_revision: Union[str, None] = '7c67e78a2064'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add password_hash column to patients table (nullable for existing records)
    op.add_column('patients', sa.Column('password_hash', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove password_hash column from patients table
    op.drop_column('patients', 'password_hash')

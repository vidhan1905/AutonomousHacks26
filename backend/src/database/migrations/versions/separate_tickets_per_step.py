"""separate_tickets_per_step

Revision ID: separate_tickets_001
Revises: df37f667edc1
Create Date: 2026-01-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'separate_tickets_001'
down_revision: Union[str, Sequence[str], None] = 'df37f667edc1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to support separate tickets per step."""
    # Drop unique constraint on chain_id (if it exists)
    try:
        op.drop_constraint('sequential_review_tickets_chain_id_key', 'sequential_review_tickets', type_='unique')
    except Exception:
        # Constraint might not exist or have different name
        pass
    
    # Add new columns
    op.add_column('sequential_review_tickets', sa.Column('step_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('sequential_review_tickets', sa.Column('step_index', sa.Integer(), nullable=True))
    op.add_column('sequential_review_tickets', sa.Column('can_start', sa.Boolean(), nullable=False, server_default='false'))
    
    # Migrate existing data: copy current_step_id to step_id
    op.execute("""
        UPDATE sequential_review_tickets
        SET step_id = current_step_id
        WHERE current_step_id IS NOT NULL
    """)
    
    # Set step_index based on step's index in chain
    op.execute("""
        UPDATE sequential_review_tickets srt
        SET step_index = srs.step_index
        FROM sequential_review_steps srs
        WHERE srt.step_id = srs.step_id
    """)
    
    # Set can_start = True for tickets where step_index matches chain's current_step_index
    op.execute("""
        UPDATE sequential_review_tickets srt
        SET can_start = true
        FROM sequential_review_chains src
        WHERE srt.chain_id = src.chain_id
        AND srt.step_index = src.current_step_index
    """)
    
    # Make step_id non-nullable and add unique constraint
    # First, delete any tickets without step_id (orphaned tickets)
    op.execute("""
        DELETE FROM sequential_review_tickets
        WHERE step_id IS NULL
    """)
    
    op.alter_column('sequential_review_tickets', 'step_id', nullable=False)
    op.create_unique_constraint('uq_sequential_review_ticket_step', 'sequential_review_tickets', ['step_id'])
    
    # Make step_index non-nullable
    # Set default for any remaining null step_index values
    op.execute("""
        UPDATE sequential_review_tickets
        SET step_index = 0
        WHERE step_index IS NULL
    """)
    op.alter_column('sequential_review_tickets', 'step_index', nullable=False)
    
    # Drop old current_step_id column and its index
    try:
        op.drop_index('ix_sequential_review_ticket_current_step', table_name='sequential_review_tickets')
    except Exception:
        pass
    op.drop_column('sequential_review_tickets', 'current_step_id')
    
    # Create new indexes
    op.create_index('ix_sequential_review_ticket_step', 'sequential_review_tickets', ['step_id'])
    op.create_index('ix_sequential_review_ticket_step_index', 'sequential_review_tickets', ['chain_id', 'step_index'])
    op.create_index('ix_sequential_review_ticket_can_start', 'sequential_review_tickets', ['can_start'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop new indexes
    op.drop_index('ix_sequential_review_ticket_can_start', table_name='sequential_review_tickets')
    op.drop_index('ix_sequential_review_ticket_step_index', table_name='sequential_review_tickets')
    op.drop_index('ix_sequential_review_ticket_step', table_name='sequential_review_tickets')
    
    # Add back current_step_id column
    op.add_column('sequential_review_tickets', sa.Column('current_step_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Migrate data back: copy step_id to current_step_id
    op.execute("""
        UPDATE sequential_review_tickets
        SET current_step_id = step_id
        WHERE step_id IS NOT NULL
    """)
    
    # Recreate old index
    op.create_index('ix_sequential_review_ticket_current_step', 'sequential_review_tickets', ['current_step_id'])
    
    # Drop new columns
    op.drop_column('sequential_review_tickets', 'can_start')
    op.drop_column('sequential_review_tickets', 'step_index')
    op.drop_constraint('uq_sequential_review_ticket_step', 'sequential_review_tickets', type_='unique')
    op.drop_column('sequential_review_tickets', 'step_id')
    
    # Restore unique constraint on chain_id
    op.create_unique_constraint('sequential_review_tickets_chain_id_key', 'sequential_review_tickets', ['chain_id'])

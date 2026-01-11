"""add_sequential_review_tables

Revision ID: df37f667edc1
Revises: add_password_hash_patients
Create Date: 2026-01-11 04:04:52.019830

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'df37f667edc1'
down_revision: Union[str, Sequence[str], None] = 'add_password_hash_patients'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create sequential_review_chains table
    op.create_table(
        'sequential_review_chains',
        sa.Column('chain_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.conversation_id'), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.patient_id'), nullable=False),
        sa.Column('case_complexity_score', sa.Integer(), nullable=True),
        sa.Column('complexity_reason', sa.Text(), nullable=True),
        sa.Column('required_doctors_count', sa.Integer(), nullable=False),
        sa.Column('current_step_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
    )
    
    # Create indexes for sequential_review_chains
    op.create_index('ix_sequential_review_chain_status', 'sequential_review_chains', ['status'])
    op.create_index('ix_sequential_review_chain_current_step', 'sequential_review_chains', ['current_step_index'])
    op.create_index('ix_sequential_review_chain_conversation', 'sequential_review_chains', ['conversation_id'])
    op.create_index('ix_sequential_review_chain_patient', 'sequential_review_chains', ['patient_id'])
    
    # Create sequential_review_steps table
    op.create_table(
        'sequential_review_steps',
        sa.Column('step_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('chain_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sequential_review_chains.chain_id'), nullable=False),
        sa.Column('step_index', sa.Integer(), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('service_persons.service_person_id'), nullable=False),
        sa.Column('ticket_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tickets.ticket_id'), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('review_summary', sa.Text(), nullable=True),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('accumulated_context', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )
    
    # Create indexes and constraints for sequential_review_steps
    op.create_index('ix_sequential_review_step_chain_index', 'sequential_review_steps', ['chain_id', 'step_index'])
    op.create_index('ix_sequential_review_step_status', 'sequential_review_steps', ['status'])
    op.create_index('ix_sequential_review_step_ticket', 'sequential_review_steps', ['ticket_id'])
    op.create_index('ix_sequential_review_step_doctor', 'sequential_review_steps', ['doctor_id'])
    op.create_unique_constraint('uq_sequential_review_step_chain_index', 'sequential_review_steps', ['chain_id', 'step_index'])
    
    # Add sequential review fields to tickets table
    op.add_column('tickets', sa.Column('sequential_review_chain_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sequential_review_chains.chain_id'), nullable=True))
    op.add_column('tickets', sa.Column('is_sequential_review', sa.Boolean(), nullable=False, server_default='false'))
    
    # Create indexes for tickets sequential review fields
    op.create_index('ix_tickets_sequential_review_chain', 'tickets', ['sequential_review_chain_id'])
    op.create_index('ix_tickets_is_sequential_review', 'tickets', ['is_sequential_review'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes for tickets sequential review fields
    op.drop_index('ix_tickets_is_sequential_review', table_name='tickets')
    op.drop_index('ix_tickets_sequential_review_chain', table_name='tickets')
    
    # Remove sequential review fields from tickets table
    op.drop_column('tickets', 'is_sequential_review')
    op.drop_column('tickets', 'sequential_review_chain_id')
    
    # Drop sequential_review_steps table (constraints and indexes will be dropped automatically)
    op.drop_table('sequential_review_steps')
    
    # Drop sequential_review_chains table (indexes will be dropped automatically)
    op.drop_table('sequential_review_chains')

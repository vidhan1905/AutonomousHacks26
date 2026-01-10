"""Initial schema

Revision ID: 7c67e78a2064
Revises: 
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7c67e78a2064'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create patients table
    op.create_table(
        'patients',
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('phone_number', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=False),
        sa.Column('gender', sa.String(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('emergency_contact', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('blood_group', sa.String(), nullable=True),
        sa.Column('medical_history', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_patients_phone_number', 'patients', ['phone_number'], unique=True)

    # Create admins table
    op.create_table(
        'admins',
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False, server_default='admin'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index('ix_admins_username', 'admins', ['username'], unique=True)
    op.create_index('ix_admins_email', 'admins', ['email'], unique=True)

    # Create service_persons table
    op.create_table(
        'service_persons',
        sa.Column('service_person_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('service_type', sa.String(), nullable=False),
        sa.Column('specialization', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index('ix_service_persons_username', 'service_persons', ['username'], unique=True)
    op.create_index('ix_service_persons_email', 'service_persons', ['email'], unique=True)

    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.patient_id'), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('started_at', sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column('ended_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('llm_model', sa.String(), nullable=True),
    )

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('message_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.conversation_id'), nullable=False),
        sa.Column('sender_type', sa.String(), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('message_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
    )

    # Create tickets table
    op.create_table(
        'tickets',
        sa.Column('ticket_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.conversation_id'), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.patient_id'), nullable=False),
        sa.Column('service_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='open'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('assigned_to', postgresql.UUID(as_uuid=True), sa.ForeignKey('service_persons.service_person_id'), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('patient_details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('past_history_summary', sa.Text(), nullable=True),
        sa.Column('llm_summary', sa.Text(), nullable=True),
        sa.Column('current_symptoms', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column('assigned_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
    )

    # Create appointments table
    op.create_table(
        'appointments',
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ticket_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tickets.ticket_id'), nullable=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.patient_id'), nullable=False),
        sa.Column('service_person_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('service_persons.service_person_id'), nullable=True),
        sa.Column('appointment_type', sa.String(), nullable=False),
        sa.Column('scheduled_date', sa.TIMESTAMP(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='scheduled'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
    )

    # Create patient_history table
    op.create_table(
        'patient_history',
        sa.Column('history_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.patient_id'), nullable=False),
        sa.Column('visit_date', sa.Date(), nullable=False),
        sa.Column('service_type', sa.String(), nullable=False),
        sa.Column('diagnosis', sa.Text(), nullable=True),
        sa.Column('treatment', sa.Text(), nullable=True),
        sa.Column('prescriptions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('test_results', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
    )

    # Create ticket_updates table
    op.create_table(
        'ticket_updates',
        sa.Column('update_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ticket_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tickets.ticket_id'), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('update_type', sa.String(), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('ticket_updates')
    op.drop_table('patient_history')
    op.drop_table('appointments')
    op.drop_table('tickets')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('service_persons')
    op.drop_table('admins')
    op.drop_table('patients')

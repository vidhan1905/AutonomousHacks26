"""SQLAlchemy models for all database tables."""
from sqlalchemy import Column, String, Integer, Text, Date, Boolean, ForeignKey, TIMESTAMP, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from .connection import Base


class Patient(Base):
    """Patient model."""
    __tablename__ = "patients"

    patient_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    emergency_contact = Column(JSON, nullable=True)
    blood_group = Column(String, nullable=True)
    medical_history = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    conversations = relationship("Conversation", back_populates="patient")
    tickets = relationship("Ticket", back_populates="patient")
    appointments = relationship("Appointment", back_populates="patient")
    history_records = relationship("PatientHistory", back_populates="patient")


class Admin(Base):
    """Admin model."""
    __tablename__ = "admins"

    admin_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="admin")  # "admin", "super_admin"
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())


class ServicePerson(Base):
    """Service person model (doctors, lab technicians, etc.)."""
    __tablename__ = "service_persons"

    service_person_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    service_type = Column(String, nullable=False)  # general_consultation, emergency, cardiology, etc.
    specialization = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    tickets = relationship("Ticket", back_populates="assigned_service_person")
    appointments = relationship("Appointment", back_populates="service_person")


class Conversation(Base):
    """Conversation model."""
    __tablename__ = "conversations"

    conversation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    status = Column(String, nullable=False, default="active")  # "active", "completed", "escalated"
    started_at = Column(TIMESTAMP, server_default=func.now())
    ended_at = Column(TIMESTAMP, nullable=True)
    summary = Column(Text, nullable=True)
    llm_model = Column(String, nullable=True)

    # Relationships
    patient = relationship("Patient", back_populates="conversations")
    # NOTE: messages relationship removed - messages are now handled by PostgresSaver checkpointer
    # All conversation messages are stored in the checkpoints table, not in messages table
    tickets = relationship("Ticket", back_populates="conversation")


# Message model removed - all messages are now handled by PostgresSaver checkpointer
# Messages are automatically persisted in the checkpoints table as part of LangGraph state
# No backward compatibility - use checkpointer.aget() to retrieve messages


class Ticket(Base):
    """Ticket model."""
    __tablename__ = "tickets"

    ticket_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    service_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="open")  # "open", "assigned", "in_progress", "completed", "cancelled"
    priority = Column(Integer, nullable=False, default=3)  # 1-5 scale
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("service_persons.service_person_id"), nullable=True)
    description = Column(Text, nullable=True)
    patient_details = Column(JSON, nullable=True)
    past_history_summary = Column(Text, nullable=True)
    llm_summary = Column(Text, nullable=True)
    current_symptoms = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    assigned_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="tickets")
    patient = relationship("Patient", back_populates="tickets")
    assigned_service_person = relationship("ServicePerson", back_populates="tickets")
    updates = relationship("TicketUpdate", back_populates="ticket")
    appointments = relationship("Appointment", back_populates="ticket")


class Appointment(Base):
    """Appointment model."""
    __tablename__ = "appointments"

    appointment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.ticket_id"), nullable=True)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    service_person_id = Column(UUID(as_uuid=True), ForeignKey("service_persons.service_person_id"), nullable=True)
    appointment_type = Column(String, nullable=False)  # "consultation", "follow_up", "procedure"
    scheduled_date = Column(TIMESTAMP, nullable=False)
    status = Column(String, nullable=False, default="scheduled")  # "scheduled", "completed", "cancelled", "no_show"
    notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    ticket = relationship("Ticket", back_populates="appointments")
    patient = relationship("Patient", back_populates="appointments")
    service_person = relationship("ServicePerson", back_populates="appointments")


class PatientHistory(Base):
    """Patient history model."""
    __tablename__ = "patient_history"

    history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    visit_date = Column(Date, nullable=False)
    service_type = Column(String, nullable=False)
    diagnosis = Column(Text, nullable=True)
    treatment = Column(Text, nullable=True)
    prescriptions = Column(JSON, nullable=True)
    test_results = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    patient = relationship("Patient", back_populates="history_records")


class TicketUpdate(Base):
    """Ticket update/audit trail model."""
    __tablename__ = "ticket_updates"

    update_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.ticket_id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), nullable=False)  # service_person_id or admin_id
    update_type = Column(String, nullable=False)  # "status_change", "assignment", "comment"
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    ticket = relationship("Ticket", back_populates="updates")

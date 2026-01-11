"""SQLAlchemy models for all database tables."""
from sqlalchemy import Column, String, Integer, Text, Date, Boolean, ForeignKey, TIMESTAMP, JSON, Index, UniqueConstraint
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
    password_hash = Column(String, nullable=True)  # Nullable for existing records
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
    history_summaries = relationship("PatientHistorySummary", back_populates="patient")
    case_history_records = relationship("DoctorCaseHistory", back_populates="patient")


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
    
    # New workload tracking fields
    current_workload = Column(Integer, nullable=False, server_default="0")
    max_workload = Column(Integer, nullable=False, server_default="10")
    max_daily_appointments = Column(Integer, nullable=False, server_default="15")
    workload_updated_at = Column(TIMESTAMP, nullable=True)
    is_available = Column(Boolean, nullable=False, server_default="true")

    # Relationships
    # Note: primaryjoin specified to disambiguate between assigned_to and accepted_by
    # Using string-based primaryjoin since Ticket is defined later
    tickets = relationship(
        "Ticket", 
        back_populates="assigned_service_person",
        primaryjoin="ServicePerson.service_person_id == Ticket.assigned_to"
    )
    appointments = relationship("Appointment", back_populates="service_person")
    expertise_records = relationship("DoctorExpertise", back_populates="service_person")
    case_history = relationship("DoctorCaseHistory", back_populates="service_person")
    ticket_assignments = relationship("TicketAssignment", back_populates="service_person")
    
    # Indexes
    __table_args__ = (
        Index("ix_service_persons_current_workload", "current_workload"),
        Index("ix_service_persons_is_available", "is_available"),
        Index("ix_service_persons_max_daily_appointments", "max_daily_appointments"),
        Index("ix_service_persons_service_type_available_workload", "service_type", "is_available", "current_workload"),
    )


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



class Ticket(Base):
    """Ticket model."""
    __tablename__ = "tickets"

    ticket_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    service_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="open")  # "open", "assigned", "in_progress", "completed", "cancelled", "offered"
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
    
    # New assignment workflow fields
    assignment_status = Column(String, nullable=False, server_default="unassigned")  # "unassigned", "offered", "accepted", "rejected_all"
    offered_to_count = Column(Integer, nullable=False, server_default="0")
    accepted_by = Column(UUID(as_uuid=True), ForeignKey("service_persons.service_person_id"), nullable=True)
    accepted_at = Column(TIMESTAMP, nullable=True)
    
    # Sequential review fields
    sequential_review_chain_id = Column(UUID(as_uuid=True), ForeignKey("sequential_review_chains.chain_id"), nullable=True)
    is_sequential_review = Column(Boolean, nullable=False, server_default="false")

    # Relationships
    conversation = relationship("Conversation", back_populates="tickets")
    patient = relationship("Patient", back_populates="tickets")
    assigned_service_person = relationship("ServicePerson", back_populates="tickets", foreign_keys=[assigned_to])
    accepted_service_person = relationship("ServicePerson", foreign_keys=[accepted_by])
    updates = relationship("TicketUpdate", back_populates="ticket")
    appointments = relationship("Appointment", back_populates="ticket")
    assignments = relationship("TicketAssignment", back_populates="ticket")
    case_history_records = relationship("DoctorCaseHistory", back_populates="ticket")
    history_summaries = relationship("PatientHistorySummary", back_populates="ticket")
    
    # Indexes
    __table_args__ = (
        Index("ix_tickets_assignment_status", "assignment_status"),
        Index("ix_tickets_accepted_by", "accepted_by"),
        Index("ix_tickets_sequential_review_chain", "sequential_review_chain_id"),
        Index("ix_tickets_is_sequential_review", "is_sequential_review"),
    )


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


class DoctorExpertise(Base):
    """Doctor expertise model - stores specializations, experience, and qualifications."""
    __tablename__ = "doctor_expertise"

    expertise_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_person_id = Column(UUID(as_uuid=True), ForeignKey("service_persons.service_person_id"), nullable=False)
    specialization_area = Column(String, nullable=False)
    years_of_experience = Column(Integer, nullable=False)
    certifications = Column(JSON, nullable=True)
    education = Column(JSON, nullable=True)
    languages_spoken = Column(JSON, nullable=True)
    is_primary_specialization = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    service_person = relationship("ServicePerson", back_populates="expertise_records")

    # Indexes
    __table_args__ = (
        Index("ix_doctor_expertise_service_person_id", "service_person_id"),
        Index("ix_doctor_expertise_specialization_area", "specialization_area"),
        Index("ix_doctor_expertise_service_person_primary", "service_person_id", "is_primary_specialization"),
    )


class DoctorCaseHistory(Base):
    """Doctor case history model - tracks cases handled by doctors for ranking."""
    __tablename__ = "doctor_case_history"

    case_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_person_id = Column(UUID(as_uuid=True), ForeignKey("service_persons.service_person_id"), nullable=False)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.ticket_id"), nullable=True)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    service_type = Column(String, nullable=False)
    diagnosis_category = Column(String, nullable=True)
    case_complexity = Column(Integer, nullable=False)
    outcome = Column(String, nullable=False)  # "successful", "ongoing", "referred", "cancelled"
    completion_date = Column(Date, nullable=True)
    patient_satisfaction_score = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    service_person = relationship("ServicePerson", back_populates="case_history")
    ticket = relationship("Ticket", back_populates="case_history_records")
    patient = relationship("Patient", back_populates="case_history_records")

    # Indexes
    __table_args__ = (
        Index("ix_doctor_case_history_service_person_id", "service_person_id"),
        Index("ix_doctor_case_history_service_type", "service_type"),
        Index("ix_doctor_case_history_diagnosis_category", "diagnosis_category"),
        Index("ix_doctor_case_history_service_person_type_outcome", "service_person_id", "service_type", "outcome"),
    )


class TicketAssignment(Base):
    """Ticket assignment model - manages multi-doctor ticket assignment workflow."""
    __tablename__ = "ticket_assignments"

    assignment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.ticket_id"), nullable=False)
    service_person_id = Column(UUID(as_uuid=True), ForeignKey("service_persons.service_person_id"), nullable=False)
    rank = Column(Integer, nullable=False)
    status = Column(String, nullable=False)  # "pending", "accepted", "rejected", "expired"
    assigned_at = Column(TIMESTAMP, server_default=func.now())
    responded_at = Column(TIMESTAMP, nullable=True)
    response_notes = Column(Text, nullable=True)
    expires_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    ticket = relationship("Ticket", back_populates="assignments")
    service_person = relationship("ServicePerson", back_populates="ticket_assignments")

    # Indexes and Constraints
    __table_args__ = (
        Index("ix_ticket_assignments_ticket_id", "ticket_id"),
        Index("ix_ticket_assignments_service_person_id", "service_person_id"),
        Index("ix_ticket_assignments_status", "status"),
        Index("ix_ticket_assignments_ticket_status", "ticket_id", "status"),
        UniqueConstraint("ticket_id", "service_person_id", name="uq_ticket_assignments_ticket_service_person"),
        UniqueConstraint("ticket_id", "rank", name="uq_ticket_assignments_ticket_rank"),
    )


class PatientHistorySummary(Base):
    """Patient history summary model - stores versioned medical history summaries."""
    __tablename__ = "patient_history_summaries"

    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    summary_text = Column(Text, nullable=False)
    summary_version = Column(Integer, nullable=False)
    generated_by = Column(String, nullable=False)  # "llm", "doctor", "system"
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.ticket_id"), nullable=True)
    includes_history_until = Column(Date, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    patient = relationship("Patient", back_populates="history_summaries")
    ticket = relationship("Ticket", back_populates="history_summaries")

    # Indexes
    __table_args__ = (
        Index("ix_patient_history_summaries_patient_id", "patient_id"),
        Index("ix_patient_history_summaries_ticket_id", "ticket_id"),
        Index("ix_patient_history_summaries_patient_version", "patient_id", "summary_version"),
    )


class SequentialReviewChain(Base):
    """Sequential multi-doctor case review chain model."""
    __tablename__ = "sequential_review_chains"

    chain_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    case_complexity_score = Column(Integer, nullable=True)  # Float stored as Integer (0-100 scale)
    complexity_reason = Column(Text, nullable=True)
    required_doctors_count = Column(Integer, nullable=False)
    current_step_index = Column(Integer, nullable=False, default=0)  # 0-based index
    status = Column(String, nullable=False, default="pending")  # "pending", "in_progress", "completed", "cancelled"
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    completed_at = Column(TIMESTAMP, nullable=True)

    # Relationships
    conversation = relationship("Conversation", backref="sequential_review_chains")
    patient = relationship("Patient", backref="sequential_review_chains")
    review_steps = relationship("SequentialReviewStep", back_populates="chain", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_sequential_review_chain_status", "status"),
        Index("ix_sequential_review_chain_current_step", "current_step_index"),
        Index("ix_sequential_review_chain_conversation", "conversation_id"),
        Index("ix_sequential_review_chain_patient", "patient_id"),
    )


class SequentialReviewStep(Base):
    """Sequential review step model - one step per doctor in the chain."""
    __tablename__ = "sequential_review_steps"

    step_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chain_id = Column(UUID(as_uuid=True), ForeignKey("sequential_review_chains.chain_id"), nullable=False)
    step_index = Column(Integer, nullable=False)  # Position in sequence (0, 1, 2, 3...)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("service_persons.service_person_id"), nullable=False)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.ticket_id"), nullable=True)  # Separate ticket for this step
    status = Column(String, nullable=False, default="pending")  # "pending", "in_review", "completed", "skipped"
    review_notes = Column(Text, nullable=True)  # Doctor's review notes/insights
    review_summary = Column(Text, nullable=True)  # AI-generated summary of this doctor's review
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    accumulated_context = Column(JSON, nullable=True)  # All previous doctors' notes combined

    # Relationships
    chain = relationship("SequentialReviewChain", back_populates="review_steps")
    doctor = relationship("ServicePerson", backref="sequential_review_steps")
    ticket = relationship("Ticket", backref="sequential_review_steps")

    # Indexes and Constraints
    __table_args__ = (
        Index("ix_sequential_review_step_chain_index", "chain_id", "step_index"),
        Index("ix_sequential_review_step_status", "status"),
        Index("ix_sequential_review_step_ticket", "ticket_id"),
        Index("ix_sequential_review_step_doctor", "doctor_id"),
        UniqueConstraint("chain_id", "step_index", name="uq_sequential_review_step_chain_index"),
    )


class SequentialReviewTicket(Base):
    """Dedicated ticket model for sequential review chains - one ticket per step."""
    __tablename__ = "sequential_review_tickets"
    
    ticket_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chain_id = Column(UUID(as_uuid=True), ForeignKey("sequential_review_chains.chain_id"), nullable=False)  # Removed unique=True to allow multiple tickets per chain
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    
    # Link to specific step (replaces current_step_id)
    step_id = Column(UUID(as_uuid=True), ForeignKey("sequential_review_steps.step_id"), nullable=False, unique=True)
    step_index = Column(Integer, nullable=False)  # Position in sequence (0, 1, 2, 3...)
    can_start = Column(Boolean, nullable=False, default=False)  # Whether this step can be started (previous step completed)
    
    # Status based on current step
    status = Column(String, nullable=False, default="step_pending")  # step_pending, step_accepted, step_in_progress, step_completed, chain_completed, chain_cancelled
    
    # Ticket content (updated as chain progresses)
    description = Column(Text, nullable=True)  # Includes accumulated context
    llm_summary = Column(Text, nullable=True)
    patient_details = Column(JSON, nullable=True)
    past_history_summary = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    chain_completed_at = Column(TIMESTAMP, nullable=True)
    
    # Relationships
    chain = relationship("SequentialReviewChain", backref="sequential_review_tickets")
    step = relationship("SequentialReviewStep", foreign_keys=[step_id], backref="sequential_review_ticket")
    
    # Indexes
    __table_args__ = (
        Index("ix_sequential_review_ticket_chain", "chain_id"),
        Index("ix_sequential_review_ticket_status", "status"),
        Index("ix_sequential_review_ticket_step", "step_id"),
        Index("ix_sequential_review_ticket_step_index", "chain_id", "step_index"),
        Index("ix_sequential_review_ticket_conversation", "conversation_id"),
        Index("ix_sequential_review_ticket_patient", "patient_id"),
        Index("ix_sequential_review_ticket_can_start", "can_start"),
    )

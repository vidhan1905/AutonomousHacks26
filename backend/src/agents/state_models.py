"""Pydantic models for LangGraph agent state management."""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from langchain_core.messages import BaseMessage


class PatientInfo(BaseModel):
    """Patient information collected during conversation."""
    name: Optional[str] = Field(None, description="Patient's full name")
    phone: Optional[str] = Field(None, description="Patient's phone number")
    date_of_birth: Optional[str] = Field(None, description="Patient's date of birth in YYYY-MM-DD format")
    patient_id: Optional[str] = Field(None, description="Patient UUID after verification")
    
    def is_complete(self) -> bool:
        """Check if all required fields are present."""
        return all([self.name, self.phone, self.date_of_birth])
    
    def missing_fields(self) -> List[str]:
        """Get list of missing required fields."""
        missing = []
        if not self.name:
            missing.append("name")
        if not self.phone:
            missing.append("phone")
        if not self.date_of_birth:
            missing.append("date_of_birth")
        return missing


class AppointmentPreferences(BaseModel):
    """Appointment date/time preferences."""
    preferred_date_time: Optional[str] = Field(None, description="ISO format datetime (YYYY-MM-DDTHH:MM:SS)")
    service_type: Optional[str] = Field(None, description="Service type (e.g., 'orthopedics', 'cardiology')")
    
    def is_complete(self) -> bool:
        """Check if appointment preferences are complete."""
        return all([self.preferred_date_time, self.service_type])
    
    def missing_fields(self) -> List[str]:
        """Get list of missing fields."""
        missing = []
        if not self.preferred_date_time:
            missing.append("preferred_date_time")
        if not self.service_type:
            missing.append("service_type")
        return missing


class DoctorRanking(BaseModel):
    """Doctor ranking information."""
    ranked_doctors: Optional[List[Dict[str, Any]]] = Field(None, description="List of ranked doctors")
    ranking_success: Optional[bool] = Field(None, description="Whether ranking was successful")
    ranking_error: Optional[str] = Field(None, description="Error message if ranking failed")


class TicketCreation(BaseModel):
    """Ticket creation information."""
    doctor_tickets: Optional[List[Dict[str, Any]]] = Field(None, description="List of created tickets")
    tickets_created: int = Field(0, description="Number of tickets created")
    tickets_creation_success: Optional[bool] = Field(None, description="Whether ticket creation was successful")
    tickets_creation_error: Optional[str] = Field(None, description="Error message if creation failed")


class HITLState(BaseModel):
    """Human In The Loop (HITL) state for validation."""
    is_waiting_for_input: bool = Field(False, description="Whether waiting for user input")
    pending_questions: List[str] = Field(default_factory=list, description="List of pending questions to ask")
    collected_responses: Dict[str, str] = Field(default_factory=dict, description="Responses collected from user")
    validation_complete: bool = Field(False, description="Whether all validations are complete")
    
    def add_question(self, question: str):
        """Add a question to pending list."""
        if question not in self.pending_questions:
            self.pending_questions.append(question)
        self.is_waiting_for_input = True
    
    def clear_questions(self):
        """Clear all pending questions."""
        self.pending_questions = []
        self.is_waiting_for_input = False


# For LangGraph compatibility, we need to use TypedDict with Annotated for messages
# But we can still use Pydantic models for validation within the state
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class AgentStateDict(TypedDict):
    """Agent state as TypedDict for LangGraph compatibility."""
    # Core identifiers
    conversation_id: str
    patient_id: Optional[str]
    
    # Patient verification state (serialized to dict)
    patient_verified: bool
    patient_info: dict  # PatientInfo as dict
    
    # Conversation state
    messages: Annotated[List[BaseMessage], add_messages]  # LangGraph message reducer
    patient_history: Optional[Dict[str, Any]]
    history_shown: bool
    
    # Workflow state
    next_action: str
    retry_count: Dict[str, int]
    
    # Appointment/Service state (serialized to dict)
    appointment_preferences: dict  # AppointmentPreferences as dict
    
    # Doctor recommendation state (serialized to dict)
    doctors_found: Optional[bool]
    doctors_error: Optional[str]
    available_doctors: Optional[List[Dict[str, Any]]]
    doctor_ranking: dict  # DoctorRanking as dict
    ticket_creation: dict  # TicketCreation as dict
    
    # Completion flags
    ticket_created: bool
    doctor_tickets_created: bool
    
    # HITL state (serialized to dict)
    hitl: dict  # HITLState as dict
    
    # Summary
    summary: Optional[str]


# AgentState for LangGraph - TypedDict
AgentState = AgentStateDict


def requires_user_input(state: AgentState) -> bool:
    """Check if state requires user input before proceeding."""
    hitl = state.get("hitl", {})
    return hitl.get("is_waiting_for_input", False)


def can_proceed_with_verification(state: AgentState) -> bool:
    """Check if we can proceed with patient verification."""
    patient_info = PatientInfo(**state.get("patient_info", {}))
    return patient_info.is_complete() and not state.get("patient_verified", False)


def can_proceed_with_doctor_search(state: AgentState) -> bool:
    """Check if we can proceed with doctor search."""
    if not state.get("patient_verified", False):
        return False
    appointment_prefs = AppointmentPreferences(**state.get("appointment_preferences", {}))
    hitl = HITLState(**state.get("hitl", {}))
    return (
        appointment_prefs.service_type is not None and
        appointment_prefs.preferred_date_time is not None and
        not hitl.is_waiting_for_input
    )


def create_initial_state(conversation_id: str, patient_id: Optional[str] = None) -> AgentState:
    """Create initial state for a new conversation.
    
    CRITICAL: Always start with patient_verified=False
    Verification MUST happen through the verification workflow only.
    The checkpointer will restore verified state if this conversation was already verified.
    """
    patient_info_dict = PatientInfo().model_dump()
    if patient_id:
        patient_info_dict["patient_id"] = patient_id
    
    return AgentState(
        conversation_id=conversation_id,
        patient_id=patient_id,
        patient_verified=False,  # NEVER auto-verify - must go through workflow
        patient_info=patient_info_dict,
        messages=[],
        patient_history=None,
        history_shown=False,
        next_action="extract_patient_info",  # Start with extracting patient info
        retry_count={},
        appointment_preferences=AppointmentPreferences().model_dump(),
        doctors_found=None,
        doctors_error=None,
        available_doctors=None,
        doctor_ranking=DoctorRanking().model_dump(),
        ticket_creation=TicketCreation().model_dump(),
        ticket_created=False,
        doctor_tickets_created=False,
        hitl=HITLState().model_dump(),
        summary=None
    )

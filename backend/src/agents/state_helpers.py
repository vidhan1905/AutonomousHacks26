"""Helper functions to work with AgentState (dict-based) and nested Pydantic models."""
from typing import Dict, Any
from backend.src.agents.state_models import (
    AgentState,
    PatientInfo,
    AppointmentPreferences,
    HITLState,
    DoctorRanking,
    TicketCreation
)


def get_patient_info(state: AgentState) -> PatientInfo:
    """Get PatientInfo model from state."""
    return PatientInfo(**state.get("patient_info", {}))


def set_patient_info(state: AgentState, patient_info: PatientInfo) -> AgentState:
    """Update PatientInfo in state."""
    state["patient_info"] = patient_info.model_dump()
    return state


def get_appointment_preferences(state: AgentState) -> AppointmentPreferences:
    """Get AppointmentPreferences model from state."""
    return AppointmentPreferences(**state.get("appointment_preferences", {}))


def set_appointment_preferences(state: AgentState, prefs: AppointmentPreferences) -> AgentState:
    """Update AppointmentPreferences in state."""
    state["appointment_preferences"] = prefs.model_dump()
    return state


def get_hitl(state: AgentState) -> HITLState:
    """Get HITLState model from state."""
    return HITLState(**state.get("hitl", {}))


def set_hitl(state: AgentState, hitl: HITLState) -> AgentState:
    """Update HITLState in state."""
    state["hitl"] = hitl.model_dump()
    return state


def get_doctor_ranking(state: AgentState) -> DoctorRanking:
    """Get DoctorRanking model from state."""
    return DoctorRanking(**state.get("doctor_ranking", {}))


def set_doctor_ranking(state: AgentState, ranking: DoctorRanking) -> AgentState:
    """Update DoctorRanking in state."""
    state["doctor_ranking"] = ranking.model_dump()
    return state


def get_ticket_creation(state: AgentState) -> TicketCreation:
    """Get TicketCreation model from state."""
    return TicketCreation(**state.get("ticket_creation", {}))


def set_ticket_creation(state: AgentState, tickets: TicketCreation) -> AgentState:
    """Update TicketCreation in state."""
    state["ticket_creation"] = tickets.model_dump()
    return state

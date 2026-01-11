"""Validation logic for state fields before SQL execution (HITL - Human In The Loop)."""
from typing import List, Dict, Any, Optional
from langchain_core.messages import AIMessage
from backend.src.agents.state_models import AgentState, PatientInfo, AppointmentPreferences, HITLState


def validate_patient_info(state: AgentState) -> tuple[bool, List[str]]:
    """
    Validate patient information before verification.
    
    Returns:
        tuple: (is_valid, list_of_missing_fields)
    """
    patient_info_dict = state.get("patient_info", {})
    patient_info = PatientInfo(**patient_info_dict)
    missing = patient_info.missing_fields()
    return len(missing) == 0, missing


def validate_appointment_preferences(state: AgentState) -> tuple[bool, List[str]]:
    """
    Validate appointment preferences before doctor search.
    
    Returns:
        tuple: (is_valid, list_of_missing_fields)
    """
    appointment_prefs_dict = state.get("appointment_preferences", {})
    appointment_prefs = AppointmentPreferences(**appointment_prefs_dict)
    missing = appointment_prefs.missing_fields()
    return len(missing) == 0, missing


def get_patient_info_questions(missing_fields: List[str]) -> List[str]:
    """Generate questions for missing patient information fields."""
    questions = []
    field_questions = {
        "name": "What is your full name?",
        "phone": "What is your phone number?",
        "date_of_birth": "What is your date of birth? (Please provide in YYYY-MM-DD format, e.g., 1990-01-15)"
    }
    
    for field in missing_fields:
        if field in field_questions:
            questions.append(field_questions[field])
    
    return questions


def get_appointment_questions(missing_fields: List[str], service_type: Optional[str] = None) -> List[str]:
    """Generate questions for missing appointment preference fields."""
    questions = []
    
    if "service_type" in missing_fields:
        questions.append(
            "What type of medical service do you need? "
            "(e.g., orthopedics, cardiology, general consultation, etc.)"
        )
    
    if "preferred_date_time" in missing_fields:
        questions.append(
            "When would you like to schedule this appointment? "
            "Please provide a date and time (e.g., 'next Tuesday at 2 PM', 'tomorrow morning', 'January 21st at 3:30 PM')."
        )
    
    return questions


def validate_before_verification(state: AgentState) -> tuple[bool, Optional[AIMessage]]:
    """
    Validate state before patient verification.
    
    Returns:
        tuple: (can_proceed, question_message_if_missing)
    """
    is_valid, missing_fields = validate_patient_info(state)
    
    if is_valid:
        return True, None
    
    # Add questions to HITL state
    questions = get_patient_info_questions(missing_fields)
    hitl_dict = state.get("hitl", {})
    hitl = HITLState(**hitl_dict)
    hitl.clear_questions()
    for question in questions:
        hitl.add_question(question)
    state["hitl"] = hitl.model_dump()
    
    # Create question message
    question_text = "I need some information to verify your identity:\n\n"
    for i, question in enumerate(questions, 1):
        question_text += f"{i}. {question}\n"
    
    question_message = AIMessage(content=question_text)
    return False, question_message


def validate_before_doctor_search(state: AgentState) -> tuple[bool, Optional[AIMessage]]:
    """
    Validate state before doctor search/SQL execution.
    
    Returns:
        tuple: (can_proceed, question_message_if_missing)
    """
    is_valid, missing_fields = validate_appointment_preferences(state)
    
    if is_valid:
        return True, None
    
    # Add questions to HITL state
    appointment_prefs_dict = state.get("appointment_preferences", {})
    appointment_prefs = AppointmentPreferences(**appointment_prefs_dict)
    questions = get_appointment_questions(
        missing_fields,
        appointment_prefs.service_type
    )
    hitl_dict = state.get("hitl", {})
    hitl = HITLState(**hitl_dict)
    hitl.clear_questions()
    for question in questions:
        hitl.add_question(question)
    state["hitl"] = hitl.model_dump()
    
    # Create question message
    question_text = "Before I can search for available doctors, I need a few details:\n\n"
    for i, question in enumerate(questions, 1):
        question_text += f"{i}. {question}\n"
    
    question_message = AIMessage(content=question_text)
    return False, question_message


def validate_before_sql_execution(state: AgentState, operation: str) -> tuple[bool, Optional[AIMessage]]:
    """
    Validate state before any SQL execution based on operation type.
    
    Args:
        state: Current agent state
        operation: Operation type ('verify_patient', 'search_doctors', 'create_ticket', etc.)
    
    Returns:
        tuple: (can_proceed, question_message_if_missing)
    """
    if operation == "verify_patient":
        return validate_before_verification(state)
    elif operation in ["search_doctors", "get_available_doctors"]:
        return validate_before_doctor_search(state)
    elif operation == "create_ticket":
        # Tickets require service_type and description
        appointment_prefs_dict = state.get("appointment_preferences", {})
        appointment_prefs = AppointmentPreferences(**appointment_prefs_dict)
        if not appointment_prefs.service_type:
            hitl_dict = state.get("hitl", {})
            hitl = HITLState(**hitl_dict)
            hitl.clear_questions()
            hitl.add_question("What type of service do you need?")
            state["hitl"] = hitl.model_dump()
            return False, AIMessage(
                content="I need to know what type of service you need before creating a ticket. "
                       "What type of service do you need?"
            )
        return True, None
    else:
        # Default: allow proceeding
        return True, None

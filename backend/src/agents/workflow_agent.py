"""Optimized LangGraph workflow-based agent with explicit nodes.

This replaces the agent-based pattern with a structured workflow pattern:
- Explicit nodes for each step
- LLM nodes only for extraction/understanding/formatting
- Tool nodes for database operations
- Clear, predictable flow
"""
from typing import Annotated, List, Optional, Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from backend.src.config import settings
from backend.src.agents.state_models import (
    AgentState,
    create_initial_state,
    PatientInfo,
    AppointmentPreferences,
    HITLState,
)
from backend.src.agents.state_helpers import (
    get_patient_info,
    set_patient_info,
    get_appointment_preferences,
    set_appointment_preferences,
    get_hitl,
    set_hitl,
    get_doctor_ranking,
    set_doctor_ranking,
    get_ticket_creation,
    set_ticket_creation,
)
from backend.src.agents.tools.extraction_tools import extract_patient_info
from backend.src.agents.tools.patient_tools import (
    verify_patient,
    create_patient,
    get_patient_history,
)
from backend.src.agents.tools.doctor_tools import (
    get_available_doctors_by_type_and_time,
    rank_doctors_with_llm,
    create_multiple_tickets,
)

# Initialize LLM
llm = ChatOpenAI(
    model=settings.openai_model,
    temperature=settings.openai_temperature,
    max_tokens=settings.openai_max_tokens,
    api_key=settings.openai_api_key,
)

# ============================================================================
# WORKFLOW NODES
# ============================================================================


def route_entry_node(state: AgentState) -> AgentState:
    """Entry node: Route to appropriate workflow based on current state.
    
    ROOT FIX: Always extract info from new user messages BEFORE continuing workflow.
    
    Determines where to start:
    - If patient not verified and has new user message → extract_patient_info FIRST
    - If patient verified but history not shown → fetch_history (will continue to show_history automatically)
    - If patient verified and history shown → understand_request (if new user message)
    """
    patient_verified = state.get("patient_verified", False)
    history_shown = state.get("history_shown", False)
    messages = state.get("messages", [])
    next_action = state.get("next_action", "")
    
    # Check if there's a new user message (last message is HumanMessage)
    has_new_user_message = False
    if messages:
        last_message = messages[-1]
        if isinstance(last_message, HumanMessage):
            has_new_user_message = True
    
    # ROOT FIX: If patient not verified and there's a new user message,
    # ALWAYS route to extract_patient_info first to extract any new info
    # This ensures we don't skip extraction when user provides info after "ask_for_missing"
    if not patient_verified and has_new_user_message:
        state["next_action"] = "extract_patient_info"
        print(f"[ROUTE ENTRY] New user message - routing to extract_patient_info first")
        return state
    
    # ROOT FIX: For continuing workflow actions (like "fetch_history" from verify_patient),
    # respect them - but only if they're valid actions and we're not waiting for user input
    valid_continuation_actions = ["fetch_history", "show_history", "verify_patient", "create_patient",
                                  "validate_request", "find_doctors", "rank_doctors", "create_tickets", 
                                  "confirm_booking", "inform_no_doctors"]
    
    # Valid waiting states (these are valid, but we should still route based on new messages)
    valid_waiting_states = ["wait_for_request", "ask_for_request_info", "ask_for_missing"]
    
    if next_action in valid_continuation_actions:
        # Keep the next_action as is (workflow is continuing automatically)
        print(f"[ROUTE ENTRY] Continuing workflow with next_action: {next_action}")
        return state
    elif next_action in valid_waiting_states and has_new_user_message:
        # We were waiting for user input, and now we have it - route to understand_request to process it
        print(f"[ROUTE ENTRY] User responded to {next_action}, routing to understand_request")
        state["next_action"] = "understand_request"
        return state
    elif next_action and next_action not in valid_waiting_states + ["end"]:
        # Invalid action - reset and route based on state
        print(f"[ROUTE ENTRY] Invalid next_action: {next_action}, resetting based on state")
    
    # Route based on state
    if not patient_verified:
        # Patient not verified - if no new message, we're waiting (shouldn't happen, but handle it)
        if has_new_user_message:
            state["next_action"] = "extract_patient_info"
        else:
            state["next_action"] = "end"
    elif patient_verified and not history_shown:
        # Patient verified but history not shown - fetch and show history
        state["next_action"] = "fetch_history"
    elif patient_verified and history_shown and has_new_user_message:
        # Patient verified, history shown, and new user message - understand request
        state["next_action"] = "understand_request"
    else:
        # Default - end (wait for user)
        state["next_action"] = "end"
    
    return state


def extract_patient_info_node(state: AgentState) -> AgentState:
    """Node 1: Extract patient info from user message using LLM.
    
    Extracts name, phone, DOB from the last user message.
    Updates state with extracted information.
    """
    # Skip if already verified
    if state.get("patient_verified", False):
        state["next_action"] = "validate_info"
        return state
    
    messages = state.get("messages", [])
    
    # Get last user message
    last_user_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break
    
    if not last_user_message:
        return state
    
    # Extract patient info using tool
    result = extract_patient_info.invoke({"message": last_user_message})
    
    if result.get("success") and result.get("extracted"):
        extracted = result.get("extracted", {})
        patient_info = get_patient_info(state)
        
        # Update only non-None fields
        if extracted.get("name"):
            patient_info.name = extracted["name"]
        if extracted.get("phone"):
            patient_info.phone = extracted["phone"]
        if extracted.get("date_of_birth"):
            patient_info.date_of_birth = extracted["date_of_birth"]
        
        set_patient_info(state, patient_info)
        print(f"[WORKFLOW] Extracted patient info: {extracted}")
        
        # ROOT FIX: Clear pending_questions if extraction succeeded and all info is now collected
        missing = patient_info.missing_fields()
        if not missing:
            # All info collected - clear questions immediately
            hitl = get_hitl(state)
            hitl.clear_questions()
            hitl.validation_complete = True
            hitl.is_waiting_for_input = False
            set_hitl(state, hitl)
    
    state["next_action"] = "validate_info"
    return state


def validate_patient_info_node(state: AgentState) -> AgentState:
    """Node 2: Validate if all required patient info is collected.
    
    Checks if name, phone, and DOB are present.
    Routes to ask_for_missing if info is missing.
    """
    patient_info = get_patient_info(state)
    missing = patient_info.missing_fields()
    
    if missing:
        # Set validation status
        hitl = get_hitl(state)
        hitl.is_waiting_for_input = True
        hitl.validation_complete = False
        hitl.clear_questions()
        
        # Add questions for missing fields
        questions_map = {
            "name": "What is your full name?",
            "phone": "What is your phone number?",
            "date_of_birth": "What is your date of birth? (Please provide in YYYY-MM-DD format, e.g., 1990-01-15)"
        }
        
        for field in missing:
            if field in questions_map:
                hitl.add_question(questions_map[field])
        
        set_hitl(state, hitl)
        state["next_action"] = "ask_for_missing"
    else:
        # All info collected
        hitl = get_hitl(state)
        hitl.is_waiting_for_input = False
        hitl.validation_complete = True
        hitl.clear_questions()
        set_hitl(state, hitl)
        state["next_action"] = "verify_patient"
    
    return state


def ask_for_missing_info_node(state: AgentState) -> AgentState:
    """Node 3: Ask user for missing patient information using LLM.
    
    Generates a conversational message asking for missing fields.
    """
    hitl = get_hitl(state)
    pending_questions = hitl.pending_questions
    
    if not pending_questions:
        return state
    
    # Get already collected info
    patient_info = get_patient_info(state)
    collected_info = []
    if patient_info.name:
        collected_info.append(f"Name: {patient_info.name}")
    if patient_info.phone:
        collected_info.append(f"Phone: {patient_info.phone}")
    if patient_info.date_of_birth:
        collected_info.append(f"Date of birth: {patient_info.date_of_birth}")
    
    # Build system prompt for LLM
    system_prompt = f"""You are a helpful AI assistant for a hospital call center.

CURRENT STATE:
{"".join(f"- {info}\\n" for info in collected_info) if collected_info else "- No information collected yet"}

REMAINING INFORMATION NEEDED:
{"".join(f"{i}. {q}\\n" for i, q in enumerate(pending_questions, 1))}

INSTRUCTIONS:
1. If information is already collected, acknowledge it warmly
2. Ask ONLY for the remaining information
3. Be conversational and friendly
4. Do NOT repeat information you already have

EXAMPLE (if name is collected):
"Thank you! I have your name as [name]. I still need:
1. Your phone number
2. Your date of birth (YYYY-MM-DD format)

Could you please provide these?"

EXAMPLE (if nothing collected):
"Hello! I'm your AI assistant here to help you. To verify your identity and access your medical records, I'll need a few details:
1. Full name
2. Phone number  
3. Date of birth (YYYY-MM-DD format, e.g., 1990-01-15)

Once you provide these details, I'll be able to assist you with scheduling appointments, creating service tickets, or answering any questions you may have."
"""
    
    # Add system prompt and call LLM
    messages = state.get("messages", [])
    messages_with_system = [AIMessage(content=system_prompt)] + messages
    
    response = llm.invoke(messages_with_system)
    
    # Add LLM response to messages
    messages.append(response)
    state["messages"] = messages
    
    return state


def verify_patient_node(state: AgentState) -> AgentState:
    """Node 4: Verify patient exists in database.
    
    Checks database for existing patient.
    Routes to create_patient if not found.
    """
    patient_info = get_patient_info(state)
    
    # Verify patient
    result = verify_patient.invoke({
        "name": patient_info.name,
        "phone": patient_info.phone,
        "date_of_birth": patient_info.date_of_birth,
    })
    
    if result.get("found"):
        # Patient found - update state
        state["patient_id"] = result["patient_id"]
        state["patient_verified"] = True
        patient_info.patient_id = result["patient_id"]
        set_patient_info(state, patient_info)
        state["next_action"] = "fetch_history"
        print(f"[WORKFLOW] Patient verified: {result['patient_id']}")
    else:
        # Patient not found - create new
        state["next_action"] = "create_patient"
        print(f"[WORKFLOW] Patient not found, will create new")
    
    return state


def create_patient_node(state: AgentState) -> AgentState:
    """Node 5: Create new patient in database if not exists.
    
    Creates patient record and updates state.
    """
    patient_info = get_patient_info(state)
    
    # Create patient
    result = create_patient.invoke({
        "name": patient_info.name,
        "phone": patient_info.phone,
        "date_of_birth": patient_info.date_of_birth,
    })
    
    if result.get("success"):
        state["patient_id"] = result["patient_id"]
        state["patient_verified"] = True
        patient_info.patient_id = result["patient_id"]
        set_patient_info(state, patient_info)
        state["next_action"] = "fetch_history"
        print(f"[WORKFLOW] Patient created: {result['patient_id']}")
    
    return state


def fetch_history_node(state: AgentState) -> AgentState:
    """Node 6: Fetch patient medical history from database.
    
    Retrieves patient history and stores in state.
    ROOT FIX: Always set next_action to show_history after successful fetch.
    Checks for 'history_records' field (not 'history') and 'error' field (not 'status').
    """
    patient_id = state.get("patient_id")
    if not patient_id:
        print(f"[WORKFLOW] No patient_id, cannot fetch history")
        state["next_action"] = "end"
        return state
    
    # Fetch history
    result = get_patient_history.invoke({"patient_id": patient_id})
    
    # ROOT FIX: Check for 'error' field instead of 'status' field
    if result.get("error"):
        # Error fetching history - still show history node (it will say "no history" or error message)
        state["patient_history"] = result
        state["next_action"] = "show_history"
        print(f"[WORKFLOW] History fetch error: {result.get('error')}, proceeding to show_history")
    else:
        # Success - history_records may be empty list if no history found
        state["patient_history"] = result
        state["next_action"] = "show_history"  # CRITICAL: Set next_action to show_history
        history_records = result.get('history_records', [])
        print(f"[WORKFLOW] History fetched: {len(history_records)} records, proceeding to show_history")
    
    return state


def show_history_node(state: AgentState) -> AgentState:
    """Node 7: Format and display patient history using LLM.
    
    Generates a friendly, readable format for patient history.
    ROOT FIX: Uses 'history_records' field (not 'history') from get_patient_history tool.
    """
    patient_history = state.get("patient_history")
    messages = state.get("messages", [])
    
    # ROOT FIX: Check for 'history_records' field (not 'history') and 'error' field
    history_text = "No previous medical history found."
    
    if patient_history:
        if patient_history.get("error"):
            # Error fetching history
            history_text = f"Unable to retrieve medical history: {patient_history.get('error')}"
        elif patient_history.get("history_records"):
            # Success - format history records
            history_records = patient_history["history_records"][:10]  # Last 10 records
            if history_records:
                history_text = "\n".join([
                    f"- {record.get('visit_date', 'Unknown')}: {record.get('service_type', 'Unknown')} - {record.get('diagnosis', 'No diagnosis')}"
                    for record in history_records
                ])
            # else: history_text already set to "No previous medical history found."
    
    # Build system prompt
    system_prompt = f"""You are a helpful AI assistant for a hospital.

The patient has been verified and you've fetched their medical history.

INSTRUCTIONS:
1. Show the patient their medical history in a friendly, readable format
2. Be warm and conversational
3. After showing history, ask: "What help do you need today?"
4. Keep it brief and clear

Patient's Medical History:
{history_text}
"""
    
    # Add system prompt and call LLM
    messages_with_system = [AIMessage(content=system_prompt)] + messages
    response = llm.invoke(messages_with_system)
    
    # Add LLM response
    messages.append(response)
    state["messages"] = messages
    state["history_shown"] = True
    state["next_action"] = "wait_for_request"  # Wait for user to provide their request
    
    return state


def understand_request_node(state: AgentState) -> AgentState:
    """Node 8: Understand user request - extract service type and date/time.
    
    Uses LLM with structured output to extract service type and preferred date/time.
    """
    messages = state.get("messages", [])
    
    # Get last user message
    last_user_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break
    
    if not last_user_message:
        state["next_action"] = "validate_request"
        return state
    
    # Use structured LLM for extraction
    from pydantic import BaseModel, Field
    from langchain_core.prompts import ChatPromptTemplate
    
    class RequestInfo(BaseModel):
        """Extracted request information."""
        service_type: Optional[str] = Field(None, description="Medical service type (e.g., orthopedics, cardiology, lab test, blood test)")
        preferred_date_time: Optional[str] = Field(None, description="Preferred date/time in ISO format (YYYY-MM-DDTHH:MM:SS)")
        issue_description: Optional[str] = Field(None, description="Patient's medical issue/concern in third person format (e.g., 'Patient has cold', 'Patient is experiencing fever'). Extract from user's message and convert first person to third person.")
        explanation: Optional[str] = Field(None, description="Brief explanation of extraction")
    
    # Create structured LLM
    structured_llm = llm.with_structured_output(RequestInfo)
    
    # ROOT FIX: Get existing appointment prefs to provide context to LLM
    appointment_prefs_existing = get_appointment_preferences(state)
    existing_service_type = appointment_prefs_existing.service_type
    existing_date_time = appointment_prefs_existing.preferred_date_time
    
    # ROOT FIX: Get available service types dynamically from database
    from backend.src.agents.tools.doctor_tools import get_available_service_types
    available_service_types = get_available_service_types()
    available_types_text = ", ".join(available_service_types) if available_service_types else "none available"
    
    # Build extraction prompt with context about what's already known
    context_text = ""
    if existing_service_type:
        context_text += f"\nNOTE: User already mentioned service type: {existing_service_type}. Only extract service_type if the new message specifies a DIFFERENT service type."
    if existing_date_time:
        context_text += f"\nNOTE: User already mentioned date/time: {existing_date_time}. Only extract preferred_date_time if the new message specifies a DIFFERENT date/time."
    
    # ROOT FIX: Build system prompt as regular string (not f-string) to avoid ChatPromptTemplate parsing issues
    # Include available service types so LLM only extracts valid ones
    system_prompt_template = """You are an expert at extracting medical service requests from natural language.

CURRENT CONTEXT (what we already know):{context}

AVAILABLE SERVICE TYPES (only extract one of these exact values):
{available_types}

Extract from the user's message:
1. **Service Type**: What medical service do they need? 
   - CRITICAL: Must match EXACTLY one of the available service types listed above
   - Map user's description to the closest available service type
   - Examples: "viral fever" → "general consultation", "sugar checkup" → "lab test", "broken leg" → "orthopedics"
   - If the message only contains date/time and NO service type mention, leave service_type as null
   - If user's request doesn't match any available type, map to the closest one
2. **Preferred Date/Time**: When do they want the appointment?
   - Convert to ISO format: YYYY-MM-DDTHH:MM:SS
   - Use current date context (today is 2026-01-10)
   - If not specified, leave as null
3. **Issue Description**: What is the patient's medical issue/concern?
   - Extract the medical problem/concern from the user's message
   - Convert first person to third person (e.g., "I have cold" → "Patient has cold", "I'm feeling fever" → "Patient is experiencing fever")
   - If the message only contains date/time or service type without describing an issue, leave as null
   - Be concise (1-2 sentences max)
   - Examples: "I have cold" → "Patient has cold", "I'm feeling pain in my leg" → "Patient is experiencing leg pain"

Examples (these are JSON format examples):
- "I broke my leg, need to see a doctor next Tuesday at 2 PM" → service_type: "orthopedics", preferred_date_time: "2026-01-14T14:00:00", issue_description: "Patient broke their leg"
- "I need a blood test" → service_type: "lab test", preferred_date_time: null, issue_description: null
- "I have cold and fever" → service_type: "general consultation", preferred_date_time: null, issue_description: "Patient has cold and fever"
- "Cardiology appointment tomorrow morning" → service_type: "cardiology", preferred_date_time: "2026-01-11T09:00:00", issue_description: null
- "tomorrow at 1 pm" (no service type or issue mentioned) → service_type: null, preferred_date_time: "2026-01-11T13:00:00", issue_description: null
"""
    
    # Format the context into the template
    context_text_formatted = context_text if context_text else "\nNo previous service information collected."
    system_prompt = system_prompt_template.format(
        context=context_text_formatted,
        available_types=available_types_text
    )
    
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{user_message}")
    ])
    
    try:
        # Extract using structured LLM
        chain = extraction_prompt | structured_llm
        extracted = chain.invoke({"user_message": last_user_message})
        
        # ROOT FIX: Validate extracted service_type against available service types
        # If extracted service_type doesn't match exactly, try to find closest match
        extracted_service_type = extracted.service_type
        if extracted_service_type:
            # Normalize for comparison (case-insensitive, strip spaces)
            extracted_normalized = extracted_service_type.lower().strip()
            available_normalized = {st.lower().strip(): st for st in available_service_types}
            
            # Check if extracted matches exactly (normalized)
            if extracted_normalized in available_normalized:
                # Use the exact database value (preserves case and formatting)
                extracted_service_type = available_normalized[extracted_normalized]
            else:
                # Try fuzzy matching - find closest match
                # Simple approach: check if extracted contains or is contained in any available type
                closest_match = None
                for db_type in available_service_types:
                    db_normalized = db_type.lower().strip()
                    if extracted_normalized == db_normalized or \
                       extracted_normalized in db_normalized or \
                       db_normalized in extracted_normalized:
                        closest_match = db_type
                        break
                
                if closest_match:
                    print(f"[WORKFLOW] Mapped extracted service_type '{extracted.service_type}' to available '{closest_match}'")
                    extracted_service_type = closest_match
                else:
                    # No match found - keep original but warn
                    print(f"[WORKFLOW] WARNING: Extracted service_type '{extracted.service_type}' doesn't match any available type. Available: {available_service_types}")
                    # Still use it - let database query handle validation
        
        # Update state - ROOT FIX: Only update fields that are actually extracted (don't overwrite existing with None)
        appointment_prefs = get_appointment_preferences(state)
        
        # Only update service_type if it was actually extracted (not None)
        if extracted_service_type:
            appointment_prefs.service_type = extracted_service_type
        
        # Only update preferred_date_time if it was actually extracted (not None)
        if extracted.preferred_date_time:
            appointment_prefs.preferred_date_time = extracted.preferred_date_time
        
        # ROOT FIX: Store issue_description when extracted (single source of truth)
        if extracted.issue_description:
            appointment_prefs.issue_description = extracted.issue_description.strip().strip('"').strip("'")
        
        set_appointment_preferences(state, appointment_prefs)
        state["next_action"] = "validate_request"
        print(f"[WORKFLOW] Extracted request: service_type={extracted.service_type}, date_time={extracted.preferred_date_time}, issue={extracted.issue_description}")
        print(f"[WORKFLOW] Current appointment_prefs: service_type={appointment_prefs.service_type}, date_time={appointment_prefs.preferred_date_time}, issue={appointment_prefs.issue_description}")
        
        # ROOT FIX: Clear pending_questions if extraction succeeded and all info is now collected
        missing = appointment_prefs.missing_fields()
        if not missing:
            # All info collected - clear questions immediately
            hitl = get_hitl(state)
            hitl.clear_questions()
            hitl.validation_complete = True
            hitl.is_waiting_for_input = False
            set_hitl(state, hitl)
        
    except Exception as e:
        print(f"[WORKFLOW] Error extracting request: {e}")
        state["next_action"] = "validate_request"
    
    return state


def validate_request_node(state: AgentState) -> AgentState:
    """Node 9: Validate if service type and date/time are present.
    
    Checks if required fields are collected.
    Routes to ask_for_request_info if missing.
    """
    appointment_prefs = get_appointment_preferences(state)
    missing = appointment_prefs.missing_fields()
    
    if missing:
        # Set validation status
        hitl = get_hitl(state)
        hitl.is_waiting_for_input = True
        hitl.validation_complete = False
        hitl.clear_questions()
        
        # ROOT FIX: Get available service types dynamically from database
        from backend.src.agents.tools.doctor_tools import get_available_service_types
        available_service_types = get_available_service_types()
        available_types_text = ", ".join(available_service_types) if available_service_types else "none available"
        
        # Add questions for missing fields with available service types
        if "service_type" in missing:
            hitl.add_question(f"What type of medical service do you need? Available services: {available_types_text}")
        if "preferred_date_time" in missing:
            hitl.add_question("When would you like to schedule this appointment? Please provide a date and time (e.g., 'next Tuesday at 2 PM', 'tomorrow morning', 'January 21st at 3:30 PM').")
        
        set_hitl(state, hitl)
        state["next_action"] = "ask_for_request_info"
    else:
        # All info collected
        hitl = get_hitl(state)
        hitl.is_waiting_for_input = False
        hitl.validation_complete = True
        hitl.clear_questions()
        set_hitl(state, hitl)
        state["next_action"] = "find_doctors"
    
    return state


def ask_for_request_info_node(state: AgentState) -> AgentState:
    """Node 10: Ask user for missing request information using LLM.
    
    Generates a conversational message asking for service type or date/time.
    """
    hitl = get_hitl(state)
    pending_questions = hitl.pending_questions
    
    if not pending_questions:
        return state
    
    # Get already collected info
    appointment_prefs = get_appointment_preferences(state)
    collected_info = []
    service_type_collected = False
    if appointment_prefs.service_type:
        collected_info.append(f"Service type: {appointment_prefs.service_type} (ALREADY COLLECTED - DO NOT CHANGE)")
        service_type_collected = True
    if appointment_prefs.preferred_date_time:
        collected_info.append(f"Preferred date/time: {appointment_prefs.preferred_date_time} (ALREADY COLLECTED - DO NOT CHANGE)")
    
    # ROOT FIX: Get available service types dynamically from database
    from backend.src.agents.tools.doctor_tools import get_available_service_types
    available_service_types = get_available_service_types()
    available_types_text = ", ".join(available_service_types) if available_service_types else "none available"
    
    # Build system prompt
    service_type_instruction = ""
    if service_type_collected:
        service_type_instruction = f"\n**CRITICAL**: Service type '{appointment_prefs.service_type}' is already collected. You MUST acknowledge this service type and use it. DO NOT suggest alternative service types (like endocrinology, lab test, etc.). The system has already determined the correct service type."
    
    system_prompt = f"""You are a helpful AI assistant for a hospital.

CURRENT STATE (ALREADY COLLECTED - FINAL VALUES):
{"".join(f"- {info}\\n" for info in collected_info) if collected_info else "- No information collected yet"}
{service_type_instruction}

AVAILABLE SERVICE TYPES: {available_types_text}
(Only mention these if asking for service type - which you should NOT do if service type is already collected above)

REMAINING INFORMATION NEEDED:
{"".join(f"{i}. {q}\\n" for i, q in enumerate(pending_questions, 1))}

CRITICAL INSTRUCTIONS:
1. **RESPECT ALREADY COLLECTED VALUES**: If information is in "CURRENT STATE", it is FINAL. Acknowledge it and use it. DO NOT suggest alternatives or question it.
2. **DO NOT OVERRIDE COLLECTED VALUES**: If "Service type" is already in CURRENT STATE, acknowledge that exact service type. Do NOT suggest other service types - the system has already determined the correct one.
3. **ASK ONLY FOR MISSING INFORMATION**: Only ask for the information listed in "REMAINING INFORMATION NEEDED". Do NOT ask for or suggest changes to information in CURRENT STATE.
4. **When asking for service type** (ONLY if NOT already in CURRENT STATE), mention the available service types
5. Be conversational and friendly
6. Do NOT repeat, question, or suggest alternatives for information you already have
"""
    
    # Call LLM
    messages = state.get("messages", [])
    messages_with_system = [AIMessage(content=system_prompt)] + messages
    response = llm.invoke(messages_with_system)
    
    messages.append(response)
    state["messages"] = messages
    
    return state


def find_doctors_node(state: AgentState) -> AgentState:
    """Node 11: Find available doctors filtered by service_type and is_active.
    
    ROOT FIX: Filters by both is_active AND service_type in database query.
    Returns only active doctors matching the service type.
    Then ranking will select top N from these filtered doctors.
    
    Routes to inform_no_doctors if none found.
    """
    appointment_prefs = get_appointment_preferences(state)
    
    # Get active doctors filtered by service_type
    result = get_available_doctors_by_type_and_time.invoke({
        "service_type": appointment_prefs.service_type,  # Used for filtering
        "preferred_date_time": appointment_prefs.preferred_date_time,
    })
    
    if result.get("status") == "success":
        doctors = result.get("doctors", [])
        state["available_doctors"] = doctors
        
        if not doctors:
            state["doctors_found"] = False
            state["doctors_error"] = f"No active doctors found for service_type: {appointment_prefs.service_type}"
            state["next_action"] = "inform_no_doctors"
        else:
            state["doctors_found"] = True
            state["next_action"] = "rank_doctors"
            print(f"[WORKFLOW] Found {len(doctors)} active doctors for service_type '{appointment_prefs.service_type}' (will be ranked)")
    
    return state


def inform_no_doctors_node(state: AgentState) -> AgentState:
    """Node 12: Inform user no doctors are available using LLM.
    
    Generates a message informing user to contact helpline.
    """
    appointment_prefs = get_appointment_preferences(state)
    service_type = appointment_prefs.service_type
    
    # ROOT FIX: Get available service types to suggest alternatives
    from backend.src.agents.tools.doctor_tools import get_available_service_types
    available_service_types = get_available_service_types()
    available_types_text = ", ".join(available_service_types) if available_service_types else "none available"
    
    system_prompt = f"""You are a helpful AI assistant for a hospital.

Unfortunately, no doctors are currently available for {service_type} at the requested time.

AVAILABLE SERVICE TYPES: {available_types_text}

INSTRUCTIONS:
1. Apologize politely
2. Suggest contacting the hospital helpline for emergency cases
3. Offer alternative service types if appropriate
4. Mention the available service types if relevant
5. Be empathetic and helpful
"""
    
    messages = state.get("messages", [])
    messages_with_system = [AIMessage(content=system_prompt)] + messages
    response = llm.invoke(messages_with_system)
    
    messages.append(response)
    state["messages"] = messages
    state["next_action"] = "end"
    
    return state


def rank_doctors_node(state: AgentState) -> AgentState:
    """Node 13: Rank doctors using LLM based on criteria.
    
    Ranks available doctors based on patient history and request.
    """
    available_doctors = state.get("available_doctors", [])
    patient_history = state.get("patient_history")
    appointment_prefs = get_appointment_preferences(state)
    
    # Get last user message for context
    messages = state.get("messages", [])
    last_user_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break
    
    result = rank_doctors_with_llm.invoke({
        "patient_history": patient_history or {},
        "user_request": last_user_message or "",
        "doctors": available_doctors,
        "service_type": appointment_prefs.service_type,
        "preferred_date_time": appointment_prefs.preferred_date_time,
    })
    
    if result.get("status") in ["success", "fallback"]:
        from backend.src.config import settings
        top_n = getattr(settings, 'top_doctors_count', 5)
        ranked_doctors = result.get("ranked_doctors", [])[:top_n]
        
        doctor_ranking = get_doctor_ranking(state)
        doctor_ranking.ranked_doctors = ranked_doctors
        doctor_ranking.ranking_success = True
        set_doctor_ranking(state, doctor_ranking)
        state["next_action"] = "create_tickets"
        print(f"[WORKFLOW] Ranked {len(ranked_doctors)} doctors")
    
    return state


def create_tickets_node(state: AgentState) -> AgentState:
    """Node 14: Create tickets for top N ranked doctors.
    
    Creates tickets in database for selected doctors.
    ROOT FIX: Provide all required parameters to create_multiple_tickets tool.
    Includes full patient details, improved description, and AI case summary.
    """
    doctor_ranking = get_doctor_ranking(state)
    ranked_doctors = doctor_ranking.ranked_doctors or []
    
    if not ranked_doctors:
        return state
    
    patient_id = state.get("patient_id")
    conversation_id = state.get("conversation_id")
    patient_history = state.get("patient_history", {})
    appointment_prefs = get_appointment_preferences(state)
    patient_info = get_patient_info(state)
    
    # Get last user message for context (used in llm_summary)
    messages = state.get("messages", [])
    last_user_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break
    
    # ROOT FIX: Use stored issue_description from appointment_prefs (extracted in understand_request_node)
    # No keyword-based extraction - single source of truth
    issue_description = appointment_prefs.issue_description or "Patient needs medical consultation"
    
    # Build description showing the actual issue/reason
    description = issue_description
    if appointment_prefs.service_type:
        description += f"\n\nService Type: {appointment_prefs.service_type}"
    if appointment_prefs.preferred_date_time:
        description += f"\nPreferred Date/Time: {appointment_prefs.preferred_date_time}"
    
    if patient_history and not patient_history.get("error"):
        # Use patient_history as primary source (has all fields from database)
        patient_details = {
            "name": patient_history.get("name") or patient_info.name,
            "phone": patient_history.get("phone") or patient_info.phone,
            "date_of_birth": patient_history.get("date_of_birth") or patient_info.date_of_birth,
            "patient_id": str(patient_id) if patient_id else None,
            "gender": patient_history.get("gender"),
            "blood_group": patient_history.get("blood_group"),
            "emergency_contact": patient_history.get("emergency_contact"),
            "medical_history": patient_history.get("medical_history", {}),
        }
    else:
        # Fallback to patient_info if history not available (shouldn't happen in normal flow)
        patient_details = {
            "name": patient_info.name,
            "phone": patient_info.phone,
            "date_of_birth": patient_info.date_of_birth,
            "patient_id": str(patient_id) if patient_id else None,
            "gender": None,
            "blood_group": None,
            "emergency_contact": None,
            "medical_history": {},
        }
    
    # Build past_history_summary from patient_history
    # ROOT FIX: Uses 'history_records' field (not 'history') from get_patient_history tool
    past_history_summary = "No previous medical history found."
    if patient_history and patient_history.get("history_records"):
        history_records = patient_history["history_records"][:10]  # Last 10 records
        if history_records:
            history_lines = []
            for record in history_records:
                visit_date = record.get('visit_date', 'Unknown')
                service_type = record.get('service_type', 'Unknown')
                diagnosis = record.get('diagnosis', 'No diagnosis')
                history_lines.append(f"- {visit_date}: {service_type} - {diagnosis}")
            if history_lines:
                past_history_summary = "\n".join(history_lines)
    
    # Generate AI case summary
    case_summary_prompt = f"""You are a medical assistant. Create a concise, professional summary of this patient case for doctors.

Patient: {patient_info.name}
Issue: {issue_description}
Service Type: {appointment_prefs.service_type or 'Not specified'}
Preferred Date/Time: {appointment_prefs.preferred_date_time or 'Not specified'}

Medical History:
{past_history_summary}

Create a brief summary (2-3 sentences) that:
1. Describes the patient's current issue/concern
2. Mentions relevant medical history if applicable
3. Is clear and professional for medical staff

Summary:"""
    
    try:
        case_summary_response = llm.invoke([AIMessage(content=case_summary_prompt)])
        case_summary = case_summary_response.content if hasattr(case_summary_response, 'content') else str(case_summary_response)
    except Exception as e:
        print(f"[WORKFLOW] Error generating case summary: {e}")
        case_summary = f"Patient {patient_info.name} requested {appointment_prefs.service_type}. {issue_description}"
    
    # Build LLM summary from context (includes case_summary for ticket storage)
    # Case summary will be prepended to llm_summary so it's available when fetching tickets
    llm_summary = f"CASE SUMMARY:\n{case_summary}\n\n"
    llm_summary += f"Patient {patient_info.name} requested {appointment_prefs.service_type}"
    if appointment_prefs.preferred_date_time:
        llm_summary += f" for {appointment_prefs.preferred_date_time}"
    if last_user_message:
        llm_summary += f". Patient's request: {last_user_message}"
    
    # Call tool with all required parameters
    result = create_multiple_tickets.invoke({
        "patient_id": str(patient_id) if patient_id else "",
        "conversation_id": str(conversation_id) if conversation_id else "",
        "ranked_doctors": ranked_doctors,
        "service_type": appointment_prefs.service_type or "general consultation",
        "description": description,
        "patient_details": patient_details,
        "past_history_summary": past_history_summary,
        "llm_summary": llm_summary,
        "priority": 3,  # Default priority
    })
    
    if result.get("status") == "success":
        tickets = result.get("tickets", [])
        ticket_creation = get_ticket_creation(state)
        ticket_creation.doctor_tickets = tickets
        ticket_creation.tickets_created = result.get("tickets_created", len(tickets))
        ticket_creation.tickets_creation_success = True
        ticket_creation.case_summary = case_summary  # Store AI case summary in state
        set_ticket_creation(state, ticket_creation)
        state["doctor_tickets_created"] = True
        state["ticket_created"] = True
        state["next_action"] = "confirm_booking"
        print(f"[WORKFLOW] Created {len(tickets)} tickets with case summary")
    
    return state


def confirm_booking_node(state: AgentState) -> AgentState:
    """Node 15: Confirm booking to user using LLM.
    
    Generates a confirmation message with doctor recommendations and ticket IDs.
    """
    doctor_ranking = get_doctor_ranking(state)
    ranked_doctors = doctor_ranking.ranked_doctors or []
    ticket_creation = get_ticket_creation(state)
    doctor_tickets = ticket_creation.doctor_tickets or []
    appointment_prefs = get_appointment_preferences(state)
    
    # Build doctor list
    ticket_map = {t["doctor_id"]: t["ticket_id"] for t in doctor_tickets}
    doctors_text = "\n".join([
        f"{i+1}. Dr. {doc.get('name', 'Unknown')} - {doc.get('service_type', 'Unknown')} (Rank: {doc.get('rank', 'N/A')}) - Ticket ID: {ticket_map.get(doc.get('doctor_id'))}"
        for i, doc in enumerate(ranked_doctors[:5])
    ])
    
    system_prompt = f"""You are a helpful AI assistant for a hospital.

You have successfully created tickets and booked appointments for the patient.

DOCTOR RECOMMENDATIONS:
{doctors_text}

Service Type: {appointment_prefs.service_type}
Preferred Date/Time: {appointment_prefs.preferred_date_time or 'Not specified'}
Total Tickets Created: {len(doctor_tickets)}

INSTRUCTIONS:
1. Congratulate the patient on successful booking
2. List the recommended doctors in a friendly format
3. Mention that tickets have been created and assigned
4. Let them know doctors will review their case
5. Offer to help with anything else
6. Be warm and professional
"""
    
    messages = state.get("messages", [])
    messages_with_system = [AIMessage(content=system_prompt)] + messages
    response = llm.invoke(messages_with_system)
    
    messages.append(response)
    state["messages"] = messages
    state["next_action"] = "end"
    
    return state


# ============================================================================
# ROUTING LOGIC
# ============================================================================


def route_entry(state: AgentState) -> Literal["extract_patient_info", "fetch_history", "understand_request", "end"]:
    """Route entry point based on state."""
    next_action = state.get("next_action", "")
    
    if next_action == "extract_patient_info":
        return "extract_patient_info"
    elif next_action == "fetch_history":
        return "fetch_history"
    elif next_action == "understand_request":
        return "understand_request"
    else:
        return "end"


def route_after_extract(state: AgentState) -> Literal["validate_info", "end"]:
    """Route after extracting patient info."""
    # Always validate after extraction
    if state.get("next_action") == "validate_info":
        return "validate_info"
    return "end"


def route_after_validate(state: AgentState) -> Literal["ask_for_missing", "verify_patient", "end"]:
    """Route after validating patient info."""
    hitl = get_hitl(state)
    
    if hitl.is_waiting_for_input:
        return "ask_for_missing"
    elif state.get("next_action") == "verify_patient":
        return "verify_patient"
    else:
        return "end"


def route_after_verify(state: AgentState) -> Literal["create_patient", "fetch_history", "end"]:
    """Route after verifying patient."""
    next_action = state.get("next_action")
    
    if next_action == "create_patient":
        return "create_patient"
    elif next_action == "fetch_history":
        return "fetch_history"
    else:
        return "end"


def route_after_create(state: AgentState) -> Literal["fetch_history", "end"]:
    """Route after creating patient."""
    if state.get("next_action") == "fetch_history":
        return "fetch_history"
    return "end"


def route_after_history(state: AgentState) -> Literal["show_history", "end"]:
    """Route after fetching history - always show history if fetched."""
    # ROOT FIX: After fetching history, always show it immediately
    # Check if history was successfully fetched
    if state.get("patient_history") or state.get("next_action") == "show_history":
        return "show_history"
    # If history wasn't fetched (error), end
    return "end"


def route_after_show(state: AgentState) -> Literal["understand_request", "end"]:
    """Route after showing history."""
    # After showing history, always end (wait for user request)
    # Next user message will trigger understand_request through route_entry
    return "end"


def route_after_understand(state: AgentState) -> Literal["validate_request", "end"]:
    """Route after understanding request."""
    return "validate_request"


def route_after_request_validate(state: AgentState) -> Literal["ask_for_request_info", "find_doctors", "end"]:
    """Route after validating request."""
    hitl = get_hitl(state)
    
    if hitl.is_waiting_for_input:
        return "ask_for_request_info"
    elif state.get("next_action") == "find_doctors":
        return "find_doctors"
    else:
        return "end"


def route_after_find(state: AgentState) -> Literal["inform_no_doctors", "rank_doctors", "end"]:
    """Route after finding doctors."""
    next_action = state.get("next_action")
    
    if next_action == "inform_no_doctors":
        return "inform_no_doctors"
    elif next_action == "rank_doctors":
        return "rank_doctors"
    else:
        return "end"


def route_after_rank(state: AgentState) -> Literal["create_tickets", "end"]:
    """Route after ranking doctors."""
    if state.get("next_action") == "create_tickets":
        return "create_tickets"
    return "end"


def route_after_tickets(state: AgentState) -> Literal["confirm_booking", "end"]:
    """Route after creating tickets."""
    if state.get("next_action") == "confirm_booking":
        return "confirm_booking"
    return "end"


# ============================================================================
# GRAPH CREATION
# ============================================================================


def create_graph(checkpointer: Optional[AsyncPostgresSaver] = None):
    """Create the optimized workflow-based LangGraph."""
    workflow = StateGraph(AgentState)
    
    # Add all workflow nodes
    workflow.add_node("route_entry", route_entry_node)
    workflow.add_node("extract_patient_info", extract_patient_info_node)
    workflow.add_node("validate_info", validate_patient_info_node)
    workflow.add_node("ask_for_missing", ask_for_missing_info_node)
    workflow.add_node("verify_patient", verify_patient_node)
    workflow.add_node("create_patient", create_patient_node)
    workflow.add_node("fetch_history", fetch_history_node)
    workflow.add_node("show_history", show_history_node)
    workflow.add_node("understand_request", understand_request_node)
    workflow.add_node("validate_request", validate_request_node)
    workflow.add_node("ask_for_request_info", ask_for_request_info_node)
    workflow.add_node("find_doctors", find_doctors_node)
    workflow.add_node("inform_no_doctors", inform_no_doctors_node)
    workflow.add_node("rank_doctors", rank_doctors_node)
    workflow.add_node("create_tickets", create_tickets_node)
    workflow.add_node("confirm_booking", confirm_booking_node)
    
    # Set entry point
    workflow.set_entry_point("route_entry")
    
    # Route from entry
    workflow.add_conditional_edges(
        "route_entry",
        route_entry,
        {
            "extract_patient_info": "extract_patient_info",
            "fetch_history": "fetch_history",
            "understand_request": "understand_request",
            "end": END
        }
    )
    
    # Add edges with conditional routing (extract_patient_info)
    workflow.add_conditional_edges(
        "extract_patient_info",
        route_after_extract,
        {"validate_info": "validate_info", "end": END}
    )
    
    workflow.add_conditional_edges(
        "validate_info",
        route_after_validate,
        {"ask_for_missing": "ask_for_missing", "verify_patient": "verify_patient", "fetch_history": "fetch_history", "end": END}
    )
    
    workflow.add_edge("ask_for_missing", END)  # Wait for user
    
    workflow.add_conditional_edges(
        "verify_patient",
        route_after_verify,
        {"create_patient": "create_patient", "fetch_history": "fetch_history", "end": END}
    )
    
    workflow.add_conditional_edges(
        "create_patient",
        route_after_create,
        {"fetch_history": "fetch_history", "end": END}
    )
    
    workflow.add_conditional_edges(
        "fetch_history",
        route_after_history,
        {"show_history": "show_history", "understand_request": "understand_request", "end": END}
    )
    
    workflow.add_edge("show_history", END)  # Always end after showing history (wait for user)
    
    workflow.add_conditional_edges(
        "understand_request",
        route_after_understand,
        {"validate_request": "validate_request", "end": END}
    )
    
    workflow.add_conditional_edges(
        "validate_request",
        route_after_request_validate,
        {"ask_for_request_info": "ask_for_request_info", "find_doctors": "find_doctors", "end": END}
    )
    
    workflow.add_edge("ask_for_request_info", END)  # Wait for user
    
    workflow.add_conditional_edges(
        "find_doctors",
        route_after_find,
        {"inform_no_doctors": "inform_no_doctors", "rank_doctors": "rank_doctors", "end": END}
    )
    
    workflow.add_edge("inform_no_doctors", END)  # Done
    
    workflow.add_conditional_edges(
        "rank_doctors",
        route_after_rank,
        {"create_tickets": "create_tickets", "end": END}
    )
    
    workflow.add_conditional_edges(
        "create_tickets",
        route_after_tickets,
        {"confirm_booking": "confirm_booking", "end": END}
    )
    
    workflow.add_edge("confirm_booking", END)  # Done
    
    # Compile with checkpointer
    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    else:
        return workflow.compile()


async def get_graph():
    """Get or create graph instance with checkpointer."""
    from backend.src.agents.checkpointer import get_checkpointer
    checkpointer = await get_checkpointer()
    return create_graph(checkpointer=checkpointer)

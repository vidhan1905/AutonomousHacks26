"""Optimized LangGraph conversation agent with Pydantic state models and PostgresSaver checkpointer."""
from typing import Annotated, List, Optional, Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import uuid
import json

from backend.src.config import settings
from backend.src.agents.state_models import (
    AgentState,
    create_initial_state,
    requires_user_input,
    can_proceed_with_verification,
    can_proceed_with_doctor_search
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
    set_ticket_creation
)
from backend.src.agents.checkpointer import get_checkpointer
from backend.src.agents.validation import (
    validate_before_verification,
    validate_before_doctor_search,
    validate_before_sql_execution
)
from backend.src.agents.tools.patient_tools import (
    verify_patient,
    create_patient,
    update_patient_info,
    get_patient_history,
    validate_required_fields
)
from backend.src.agents.tools.ticket_tools import create_ticket, update_ticket_status
from backend.src.agents.tools.appointment_tools import schedule_appointment
from backend.src.agents.tools.extraction_tools import extract_patient_info, extract_patient_request, generate_patient_case_summary
from backend.src.agents.tools.doctor_tools import (
    get_service_persons_by_type,
    get_available_doctors_by_type_and_time,
    rank_doctors_with_llm,
    create_multiple_tickets
)


class AgentState(TypedDict):
    """State schema for the conversation agent."""
    conversation_id: str
    patient_id: Optional[str]
    patient_verified: bool
    messages: Annotated[List[BaseMessage], add_messages]
    collected_info: dict
    required_fields_missing: List[str]
    retry_count: dict
    patient_history: Optional[dict]
    summary: Optional[str]
    ticket_created: bool
    next_action: str
    history_shown: bool
    service_type_determined: Optional[str]
    ranked_doctors: Optional[List[dict]]
    doctor_tickets_created: bool
    waiting_for_appointment_datetime: bool
    appointment_datetime: Optional[str]
    user_request: Optional[str]


# Initialize LLM
llm = ChatOpenAI(
    model=settings.openai_model,
    temperature=settings.openai_temperature,
    max_tokens=settings.openai_max_tokens,
    api_key=settings.openai_api_key
)

# Define all tools
all_tools = [
    extract_patient_info,
    verify_patient,
    create_patient,
    update_patient_info,
    get_patient_history,
    validate_required_fields,
    create_ticket,
    schedule_appointment,
    update_ticket_status,
    get_service_persons_by_type,
    get_available_doctors_by_type_and_time,
    rank_doctors_with_llm,
    create_multiple_tickets
]

# Tools available ONLY for unverified patients (no SQL access)
unverified_tools = [
    extract_patient_info,
    validate_required_fields
]

# Tools available for verified patients (all tools)
verified_tools = all_tools

# Create tool nodes
tool_node_all = ToolNode(all_tools)
tool_node_unverified = ToolNode(unverified_tools)


def should_continue(state: AgentState) -> Literal["tools", "verify_patient", "end"]:
    """Determine next step based on state with HITL validation.
    
    ROOT CAUSE FIX: Allow agent to call tools first before routing to collect_info.
    The agent should be able to extract information before we ask for missing fields.
    """
    messages = state.get("messages", [])
    if not messages:
        return "end"
    
    last_message = messages[-1]
    patient_verified = state.get("patient_verified", False)
    
    # Check HITL state - if waiting for input, end and wait
    if requires_user_input(state):
        return "end"
    
    # ROOT CAUSE FIX: If LLM wants to call tools, allow it first (before checking if info is complete)
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        tool_names = [tc.get("name") for tc in last_message.tool_calls if isinstance(tc, dict)]
        
        # If patient is not verified, only allow extraction/validation tools
        if not patient_verified:
            allowed_tools = ["extract_patient_info", "validate_required_fields"]
            forbidden_tools = ["verify_patient", "get_patient_history", "create_patient", 
                             "update_patient_info", "create_ticket", "schedule_appointment",
                             "get_available_doctors_by_type_and_time", "rank_doctors_with_llm",
                             "create_multiple_tickets", "get_service_persons_by_type"]
            
            # Check if any tool call is forbidden
            for tool_name in tool_names:
                if tool_name in forbidden_tools:
                    # Block this tool call - add error message and end
                    error_msg = AIMessage(
                        content="I cannot access the database until you provide your verification details. "
                               "Please provide your name, phone number, and date of birth first."
                    )
                    messages = state.get("messages", [])
                    messages.append(error_msg)
                    state["messages"] = messages
                    return "end"
            
            # Check if all tool calls are allowed
            if all(tool_name in allowed_tools for tool_name in tool_names):
                # Allowed tools - let them execute
                return "tools"
            else:
                # Some tools not allowed
                error_msg = AIMessage(
                    content="I cannot access the database until you provide your verification details. "
                           "Please provide your name, phone number, and date of birth first."
                )
                messages = state.get("messages", [])
                messages.append(error_msg)
                state["messages"] = messages
                return "end"
        else:
            # Patient verified - check validation before SQL tools
            for tool_name in tool_names:
                if tool_name in ["verify_patient", "search_doctors", "get_available_doctors_by_type_and_time", "create_ticket"]:
                    can_proceed, question_msg = validate_before_sql_execution(state, tool_name)
                    if not can_proceed and question_msg:
                        # Add question to messages and return end (wait for user)
                        messages = state.get("messages", [])
                        messages.append(question_msg)
                        state["messages"] = messages
                        return "end"
            # All validations passed or no SQL tools - allow tools
            return "tools"
    
    # No tool calls - check if we need to collect info or can proceed
    if not patient_verified:
        if can_proceed_with_verification(state):
            # All info collected, proceed to verification
            return "verify_patient"
        else:
            # Missing info - but DON'T route to collect_info here
            # Instead, let the agent handle it through normal flow
            # The agent will ask for missing info based on system prompt
            return "end"
    
    # Patient is verified - allow normal flow
    # Check if last message is a ToolMessage
    from langchain_core.messages import ToolMessage
    if isinstance(last_message, ToolMessage):
        # Check if create_multiple_tickets was just called successfully
        tool_name = str(last_message.name) if hasattr(last_message, "name") else ""
        if "create_multiple_tickets" in tool_name:
            return "end"
        
        # Check if doctor tickets are already created
        if state.get("doctor_tickets_created", False):
            return "end"
        
        return "agent"
    
    # If ticket is created, we're done
    if state.get("ticket_created", False) or state.get("doctor_tickets_created", False):
        return "end"
    
    # LLM gave a response without tool calls - end and wait for user input
    if hasattr(last_message, 'content') and last_message.content and str(last_message.content).strip():
        return "end"
    
    return "end"


def conditional_tool_node(state: AgentState) -> AgentState:
    """Conditionally route to appropriate tool node based on verification status."""
    patient_verified = state.get("patient_verified", False)
    
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            tool_name = str(msg.name) if hasattr(msg, "name") else ""
            
            # Check for get_service_persons_by_type result
            if "get_service_persons_by_type" in tool_name:
                try:
                    content = msg.content
                    if isinstance(content, str):
                        try:
                            result = json.loads(content)
                        except:
                            result = {}
                    else:
                        result = content
                    
                    if isinstance(result, dict) and result.get("status") == "success":
                        doctors_list = result.get("doctors", [])
                        # Store doctors list for ranking
                        state["available_doctors"] = doctors_list
                        # Extract and store service_type
                        if result.get("service_type"):
                            service_type_determined = result["service_type"]
                        
                        # Validation: Check if doctors were found
                        if not doctors_list or len(doctors_list) == 0:
                            state["doctors_found"] = False
                            state["doctors_error"] = f"No doctors found for service type: {service_type_determined}"
                        else:
                            state["doctors_found"] = True
                            state["doctors_error"] = None
                    elif isinstance(result, dict) and result.get("status") == "error":
                        state["doctors_found"] = False
                        state["doctors_error"] = result.get("error", "Unknown error fetching doctors")
                except Exception as e:
                    print(f"Error processing get_service_persons_by_type result: {e}")
                    state["doctors_found"] = False
                    state["doctors_error"] = str(e)
            
            # Also extract service_type from tool call arguments
            if hasattr(msg, "tool_call_id"):
                # Find the corresponding AIMessage with tool_calls
                for ai_msg in reversed(messages):
                    if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
                        for tool_call in ai_msg.tool_calls:
                            if tool_call.get("name") == "get_service_persons_by_type":
                                args = tool_call.get("args", {})
                                if "service_type" in args:
                                    service_type_determined = args["service_type"]
                                break
            
            # Check for rank_doctors_with_llm result
            if "rank_doctors_with_llm" in tool_name:
                try:
                    content = msg.content
                    if isinstance(content, str):
                        try:
                            result = json.loads(content)
                        except:
                            result = {}
                    else:
                        result = content
                    
                    if isinstance(result, dict) and result.get("status") in ["success", "fallback"]:
                        ranked_doctors = result.get("ranked_doctors", [])
                        
                        # Validation: Ensure we have ranked doctors (up to 5)
                        if not ranked_doctors or len(ranked_doctors) == 0:
                            state["ranking_success"] = False
                            state["ranking_error"] = "No doctors were ranked"
                        else:
                            # Ensure we have at most 5 doctors
                            ranked_doctors = ranked_doctors[:5]
                            state["ranking_success"] = True
                            state["ranking_error"] = None
                            # Store the validated ranked doctors
                            state["ranked_doctors"] = ranked_doctors
                    elif isinstance(result, dict) and result.get("status") == "error":
                        state["ranking_success"] = False
                        state["ranking_error"] = result.get("error", "Unknown error ranking doctors")
                except Exception as e:
                    print(f"Error processing rank_doctors_with_llm result: {e}")
                    state["ranking_success"] = False
                    state["ranking_error"] = str(e)
            
            # Check for create_multiple_tickets result
            if "create_multiple_tickets" in tool_name:
                try:
                    content = msg.content
                    print(f"DEBUG: create_multiple_tickets result - content type: {type(content)}, preview: {str(content)[:200]}")
                    
                    # Parse content - could be dict or JSON string
                    if isinstance(content, str):
                        try:
                            result = json.loads(content)
                        except json.JSONDecodeError:
                            # Try to extract info from string using regex
                            import re
                            result = {}
                            # Look for status
                            status_match = re.search(r'"status"\s*:\s*"([^"]+)"', content)
                            if status_match:
                                result["status"] = status_match.group(1)
                            # Look for tickets_created count
                            tickets_match = re.search(r'"tickets_created"\s*:\s*(\d+)', content)
                            if tickets_match:
                                result["tickets_created"] = int(tickets_match.group(1))
                            # Try to extract tickets array
                            tickets_array_match = re.search(r'"tickets"\s*:\s*\[(.*?)\]', content, re.DOTALL)
                            if tickets_array_match:
                                try:
                                    tickets_str = "[" + tickets_array_match.group(1) + "]"
                                    tickets_list = json.loads(tickets_str)
                                    result["tickets"] = tickets_list
                                except:
                                    pass
                    else:
                        result = content if isinstance(content, dict) else {}
                    
                    print(f"DEBUG: Parsed result status: {result.get('status') if isinstance(result, dict) else 'not a dict'}")
                    print(f"DEBUG: Tickets count: {result.get('tickets_created') if isinstance(result, dict) else 'N/A'}")
                    
                    if isinstance(result, dict) and result.get("status") == "success":
                        tickets_created = result.get("tickets", [])
                        tickets_count = result.get("tickets_created", len(tickets_created))
                        
                        print(f"DEBUG: Success! Tickets created: {tickets_count}")
                        
                        # Validation: Check if tickets were actually created
                        if tickets_count > 0:
                            state["doctor_tickets_created"] = True
                            state["ticket_created"] = True
                            state["doctor_tickets"] = tickets_created
                            state["tickets_creation_success"] = True
                            print(f"DEBUG: Set tickets_creation_success=True")
                        else:
                            print(f"DEBUG: Warning - status=success but tickets_count=0")
                            state["tickets_creation_success"] = False
                            state["tickets_creation_error"] = "No tickets were created despite success status"
                    elif isinstance(result, dict) and result.get("status") == "error":
                        error_msg = result.get("error", "Unknown error creating tickets")
                        print(f"DEBUG: Error status: {error_msg}")
                        state["tickets_creation_success"] = False
                        state["tickets_creation_error"] = error_msg
                    else:
                        # Unknown format - check if we can infer success from content
                        print(f"DEBUG: Unknown result format, attempting to infer success")
                        content_str = str(content).lower()
                        if "success" in content_str and ("tickets_created" in content_str or "ticket" in content_str):
                            # Likely success but format is different
                            import re
                            tickets_match = re.search(r'tickets_created["\s:]*(\d+)', str(content))
                            if tickets_match:
                                tickets_count = int(tickets_match.group(1))
                                if tickets_count > 0:
                                    print(f"DEBUG: Inferred success from content, tickets_count={tickets_count}")
                                    state["doctor_tickets_created"] = True
                                    state["ticket_created"] = True
                                    state["tickets_creation_success"] = True
                                else:
                                    print(f"DEBUG: Inferred success but tickets_count=0")
                                    state["tickets_creation_success"] = False
                                    state["tickets_creation_error"] = "Could not parse ticket creation result"
                        else:
                            print(f"DEBUG: Cannot infer success, leaving state unchanged")
                            # Don't set error - let LLM handle it based on actual ticket existence
                except Exception as e:
                    print(f"ERROR processing create_multiple_tickets result: {e}")
                    import traceback
                    traceback.print_exc()
                    # Only set error if we're sure it failed
                    # Don't assume failure - tickets might have been created

    # Check for ticket creation or appointment scheduling
    ticket_created = state.get("ticket_created", False)
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            # Check if this is from create_ticket or schedule_appointment
            tool_name = str(msg.name) if hasattr(msg, "name") else ""
            if "create_ticket" in tool_name or "schedule_appointment" in tool_name:
                try:
                    content = msg.content
                    if isinstance(content, str):
                        try:
                            result = json.loads(content)
                        except:
                            result = {}
                    else:
                        result = content
                    
                    # If ticket/appointment was created successfully
                    if isinstance(result, dict) and (result.get("status") == "created" or result.get("ticket_id") or result.get("appointment_id")):
                        ticket_created = True
                except Exception as e:
                    print(f"Error processing ticket/appointment result: {e}")

    updated_state = {**state}
    if collected_info:
        updated_state["collected_info"] = collected_info
    if patient_verified:
        # Use full tool node for verified patients
        return tool_node_all.invoke(state)
    else:
        # Use limited tool node for unverified patients (only extraction/validation)
        return tool_node_unverified.invoke(state)


def verify_patient_node(state: AgentState) -> AgentState:
    """Node for verifying patient with validation check."""
    # Double-check validation before verification
    can_proceed, question_msg = validate_before_verification(state)
    
    if not can_proceed:
        if question_msg:
            messages = state.get("messages", [])
            messages.append(question_msg)
            state["messages"] = messages
        return state
    
    # Get patient info from state
    patient_info = get_patient_info(state)
    
    # Validate required fields
    validation = validate_required_fields.invoke({
        "collected_info": {
            "name": patient_info.name,
            "phone": patient_info.phone,
            "date_of_birth": patient_info.date_of_birth
        }
    })
    
    if not validation.get("all_present", False):
        missing = validation.get("missing_fields", [])
        questions = [f"What is your {field}?" for field in missing]
        hitl = get_hitl(state)
        hitl.clear_questions()
        for q in questions:
            hitl.add_question(q)
        set_hitl(state, hitl)
        messages = state.get("messages", [])
        messages.append(AIMessage(
            content=f"I still need: {', '.join(missing)}. Please provide these details."
        ))
        state["messages"] = messages
        return state
    
    # Call verify_patient tool
    result = verify_patient.invoke({
        "name": patient_info.name,
        "phone": patient_info.phone,
        "date_of_birth": patient_info.date_of_birth
    })
    
    if result.get("found", False):
        state["patient_id"] = result["patient_id"]
        state["patient_verified"] = True
        patient_info.patient_id = result["patient_id"]
        set_patient_info(state, patient_info)
        state["next_action"] = "fetch_history"
        hitl = get_hitl(state)
        hitl.clear_questions()
        set_hitl(state, hitl)
    else:
        state["patient_verified"] = False
        state["next_action"] = "create_patient"
    
    return state


def extract_datetime_from_message(message: str) -> Optional[str]:
    """Extract date and time from user message using LLM, based on current IST time."""
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from pydantic import BaseModel, Field
    from datetime import datetime
    import pytz
    
    # Get current time in IST (Indian Standard Time)
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    current_time_str = now_ist.strftime("%Y-%m-%d %H:%M:%S %Z")
    current_date_str = now_ist.strftime("%A, %B %d, %Y")  # e.g., "Friday, January 10, 2026"
    current_weekday = now_ist.strftime("%A")  # e.g., "Friday"
    
    # Create LLM with structured output
    class DateTimeExtraction(BaseModel):
        """Model for datetime extraction."""
        datetime_iso: Optional[str] = Field(None, description="Extracted datetime in ISO format (YYYY-MM-DDTHH:MM:SS) or None if cannot extract")
        confidence: str = Field(description="Confidence level: high, medium, or low")
        reasoning: str = Field(description="Brief reasoning for the extraction")
    
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.1,
    ).with_structured_output(DateTimeExtraction)
    
    # Create prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a datetime extraction assistant. Your task is to extract a specific date and time from the user's message and convert it to ISO format (YYYY-MM-DDTHH:MM:SS) based on the current IST time.

Current IST Time: {current_time}
Current Date: {current_date}
Today is: {current_weekday}

Rules:
1. Extract the date and time from the user's message
2. Convert relative dates (e.g., "tomorrow", "next week", "next Tuesday", "next week on Tuesday") to absolute dates based on current IST time
3. If time is not specified, default to 10:00:00 (10 AM IST)
4. Return datetime in ISO format: YYYY-MM-DDTHH:MM:SS (e.g., "2025-01-15T10:00:00")
5. All times should be interpreted in IST (Indian Standard Time) context
6. If you cannot extract a valid datetime, return None for datetime_iso

Examples:
- "tomorrow at 10 AM" → Calculate tomorrow's date + 10:00:00
- "next week on Tuesday at 11:00 AM" → Calculate next Tuesday's date + 11:00:00
- "2025-01-15 at 2:00 PM" → "2025-01-15T14:00:00"
- "next Monday at 3:00 PM" → Calculate next Monday's date + 15:00:00
- "tommorow 10 AM" (typo) → Calculate tomorrow's date + 10:00:00

IMPORTANT: Calculate dates relative to the current IST time provided above."""),
        ("human", "User message: {user_message}\n\nExtract the datetime and return it in ISO format based on the current IST time provided above.")
    ])
    
    try:
        chain = prompt | llm
        result = chain.invoke({
            "current_time": current_time_str,
            "current_date": current_date_str,
            "current_weekday": current_weekday,
            "user_message": message
        })
        
        if result.datetime_iso:
            print(f"DEBUG: LLM extracted datetime: {result.datetime_iso} (confidence: {result.confidence}, reasoning: {result.reasoning})")
            return result.datetime_iso
        else:
            print(f"DEBUG: LLM could not extract datetime (reasoning: {result.reasoning})")
            return None
            
    except Exception as e:
        print(f"DEBUG: Error in LLM-based datetime extraction: {e}")
        import traceback
        traceback.print_exc()
        return None


def call_model(state: AgentState) -> AgentState:
    """Call the LLM with current state and HITL validation."""
    messages = state.get("messages", [])
    
    # Check if we're waiting for user input (HITL)
    if requires_user_input(state):
        # Don't call LLM, just return state (waiting for user response)
        return state
    
    # Build system prompt based on state
    patient_verified = state.get("patient_verified", False)
    patient_id = state.get("patient_id")
    
    # CRITICAL: Conditionally bind tools based on verification status
    # If patient is NOT verified, ONLY allow extraction/validation tools (NO SQL)
    if not patient_verified:
        # Use LLM with ONLY extraction/validation tools - NO SQL tools
        llm_with_tools = llm.bind_tools(unverified_tools)
    else:
        # Patient verified - allow all tools
        llm_with_tools = llm.bind_tools(verified_tools)
    
    if patient_verified and patient_id:
        # Patient verified workflow
        history_shown = state.get("history_shown", False)
        patient_history = state.get("patient_history")
        doctor_tickets_created = state.get("doctor_tickets_created", False)
        
        # STEP 1: Show history if not shown yet
        if not history_shown:
            if not patient_history:
                system_prompt = f"""You are a helpful AI assistant for a hospital. The patient has been verified.

1. Call get_patient_history(patient_id="{patient_id}")
2. After getting history, show it to the patient in a friendly format
3. Ask: "What help do you need today?"
4. END - wait for user response

Patient ID: {patient_id}
Conversation ID: {state.get("conversation_id")}
"""
            else:
                # History fetched, show it
                # ROOT FIX: Use 'history_records' field (not 'history') from get_patient_history tool
                history_records = patient_history.get("history_records", [])
                if patient_history.get("status") == "schema_error":
                    history_summary = f"Unable to retrieve medical history due to schema issue: {patient_history.get('error', 'Unknown error')}"
                elif history_records:
                    history_summary = "\n".join([
                        f"- {record.get('visit_date', 'Unknown')}: {record.get('service_type', 'Unknown')} - {record.get('diagnosis', 'No diagnosis')}"
                        for record in history_records[:10]
                    ])
                else:
                    history_summary = "No previous medical history found."
                
                system_prompt = f"""You are a helpful AI assistant for a hospital. The patient has been verified and you've fetched their medical history.

1. Show the patient their medical history in a friendly, readable format
2. After showing history, ask: "What help do you need today?"
3. END - wait for user response

Patient's Medical History:
{history_summary}

Patient ID: {patient_id}
"""
                state["history_shown"] = True
        
        # STEP 2: User provided request - do doctor recommendation workflow
        elif history_shown and not doctor_tickets_created:
            # Check if tickets were actually created successfully (even if state says False due to timing)
            doctor_tickets = state.get("doctor_tickets", [])
            
            # Also check tool messages for ticket creation results
            from langchain_core.messages import ToolMessage
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, ToolMessage) and "create_multiple_tickets" in str(getattr(msg, "name", "")):
                    content = msg.content
                    # Try to parse and check if tickets were created
                    if isinstance(content, str):
                        import re
                        # Look for tickets_created count in the content
                        tickets_match = re.search(r'"tickets_created"\s*:\s*(\d+)', content)
                        if tickets_match:
                            tickets_count = int(tickets_match.group(1))
                            if tickets_count > 0:
                                print(f"DEBUG: Found tickets_created={tickets_count} in tool message, marking as success")
                                doctor_tickets_created = True
                                state["doctor_tickets_created"] = True
                                state["tickets_creation_success"] = True
                                break
                    elif isinstance(content, dict):
                        tickets_count = content.get("tickets_created", 0)
                        if tickets_count > 0:
                            print(f"DEBUG: Found tickets_created={tickets_count} in tool message dict, marking as success")
                            doctor_tickets_created = True
                            state["doctor_tickets_created"] = True
                            state["tickets_creation_success"] = True
                            break
            
            if doctor_tickets and len(doctor_tickets) > 0:
                # Tickets were created successfully - don't treat as error
                doctor_tickets_created = True
                state["doctor_tickets_created"] = True
                state["tickets_creation_success"] = True
                print(f"DEBUG: Found {len(doctor_tickets)} doctor_tickets in state, marking as success")
            # Get last user message
            last_user_message = None
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    last_user_message = msg.content
                    break
            
            # Check if we're waiting for appointment datetime
            waiting_for_datetime = state.get("waiting_for_appointment_datetime", False)
            appointment_datetime = state.get("appointment_datetime")
            user_request = state.get("user_request")
            
            # If we don't have datetime yet, ask for it FIRST
            if not waiting_for_datetime and not appointment_datetime:
                # Store the user request
                user_request = last_user_message
                # Ask for date/time
                system_prompt = f"""You are a helpful AI assistant for a hospital. The patient has been verified and you've shown their history.

The patient said: "{last_user_message or 'No request'}"

IMPORTANT: Before proceeding with doctor recommendations, you MUST ask the patient for their preferred appointment date and time.

Your response should be:
"I understand you need help with: {last_user_message or 'your request'}. To help you find the best available doctors, I'll need to know when you'd like to schedule your appointment. 

Please provide your preferred date and time. For example:
- "tomorrow at 10:00 AM"
- "next week on Tuesday at 11:00 AM"
- "2025-01-15 at 2:00 PM"
- "next Monday at 3:00 PM"

What date and time would work best for you?"

Do NOT call any tools yet. Just ask for the date/time and END."""
                
                messages = state["messages"]
                if not hasattr(messages[-1], "content") or "helpful AI assistant" not in str(messages[-1].content):
                    messages = [AIMessage(content=system_prompt)] + messages
                response = llm_with_tools.invoke(messages)
                return {
                    **state,
                    "messages": [response],
                    "waiting_for_appointment_datetime": True,
                    "user_request": user_request
                }
            
            # If we're waiting for datetime, try to extract it from the message
            if waiting_for_datetime and not appointment_datetime:
                extracted_datetime = extract_datetime_from_message(last_user_message)
                if not extracted_datetime:
                    # Date/time not found, ask again
                    system_prompt = """I need to know when you'd like to schedule the appointment. Please provide a date and time. 

For example:
- "tomorrow at 10:00 AM"
- "next week on Tuesday at 11:00 AM"
- "2025-01-15 at 2:00 PM"
- "next Monday at 3:00 PM"

What date and time would work best for you?"""
                    response = AIMessage(content=system_prompt)
                    return {
                        **state,
                        "messages": [response],
                        "waiting_for_appointment_datetime": True
                    }
                else:
                    # Date/time found! Store it and proceed with doctor recommendation
                    appointment_datetime = extracted_datetime
                    state = {
                        **state,
                        "appointment_datetime": appointment_datetime,
                        "waiting_for_appointment_datetime": False
                    }
                    # Continue to doctor recommendation workflow below
            
            # Now proceed with doctor recommendation (we have datetime)
            # Check for error states from previous tool calls
            doctors_found = state.get("doctors_found", None)
            doctors_error = state.get("doctors_error")
            ranking_success = state.get("ranking_success", None)
            ranking_error = state.get("ranking_error")
            tickets_creation_success = state.get("tickets_creation_success", None)
            tickets_creation_error = state.get("tickets_creation_error")
            
            # All validations passed, proceed with doctor recommendation workflow
            from backend.src.config import settings
            top_n = getattr(settings, 'top_doctors_count', 5)
            
            # Handle error case: Ranking failed
            if ranking_success is False and doctors_found is True:
                system_prompt = f"""You are a helpful AI assistant for a hospital. Doctors were found but ranking failed.

The patient said: "{last_user_message or 'No request'}"

ERROR: Doctor ranking failed: {ranking_error or 'Unknown error'}

You should inform the patient that there was a technical issue ranking doctors, but you can still help them. 
Suggest they contact the hospital directly or try again later.

Be helpful and apologize for the inconvenience. END after informing the patient.

Patient ID: {patient_id}
"""
                messages = state["messages"]
                if not hasattr(messages[-1], "content") or "helpful AI assistant" not in str(messages[-1].content):
                    messages = [AIMessage(content=system_prompt)] + messages
                response = llm_with_tools.invoke(messages)
                return {
                    **state,
                    "messages": [response]
                }
            
            # Handle error case: Ticket creation failed
            # Only treat as error if tickets_creation_success is explicitly False AND we have an error
            # If tickets were created successfully (even if fewer than 5), that's success, not error
            # Also check if doctor_tickets exist - if they do, tickets were created successfully
            doctor_tickets = state.get("doctor_tickets", [])
            
            # Double-check tool messages to verify tickets were actually created
            from langchain_core.messages import ToolMessage
            tickets_actually_created = False
            if not doctor_tickets or len(doctor_tickets) == 0:
                for msg in reversed(state.get("messages", [])):
                    if isinstance(msg, ToolMessage) and "create_multiple_tickets" in str(getattr(msg, "name", "")):
                        content = msg.content
                        if isinstance(content, str):
                            import re
                            tickets_match = re.search(r'"tickets_created"\s*:\s*(\d+)', content)
                            if tickets_match and int(tickets_match.group(1)) > 0:
                                tickets_actually_created = True
                                print(f"DEBUG: Verified tickets were created from tool message")
                                break
                        elif isinstance(content, dict) and content.get("tickets_created", 0) > 0:
                            tickets_actually_created = True
                            print(f"DEBUG: Verified tickets were created from tool message dict")
                            break
            
            # Only show error if tickets were NOT created AND we have an error
            if tickets_creation_success is False and tickets_creation_error and (not doctor_tickets or len(doctor_tickets) == 0) and not tickets_actually_created:
                system_prompt = f"""You are a helpful AI assistant for a hospital. Doctors were ranked but ticket creation failed.

The patient said: "{last_user_message or 'No request'}"

ERROR: Failed to create tickets: {tickets_creation_error or 'Unknown error'}

You should inform the patient that there was a technical issue creating their appointment tickets.
Suggest they contact the hospital directly or try again later.

Be helpful and apologize for the inconvenience. END after informing the patient.

Patient ID: {patient_id}
"""
                messages = state["messages"]
                if not hasattr(messages[-1], "content") or "helpful AI assistant" not in str(messages[-1].content):
                    messages = [AIMessage(content=system_prompt)] + messages
                response = llm_with_tools.invoke(messages)
                return {
                    **state,
                    "messages": [response]
                }
            
            # Fetch full patient data from database to include blood_group, age, gender
            from backend.src.database.connection import async_session_maker
            from backend.src.database.models import Patient
            from sqlalchemy import select
            from datetime import datetime
            import asyncio
            import concurrent.futures
            
            # Helper async function to fetch patient data
            async def _fetch_patient_data_async(patient_id_str: str, session_maker):
                async with session_maker() as session:
                    result = await session.execute(
                        select(Patient).where(Patient.patient_id == uuid.UUID(patient_id_str))
                    )
                    return result.scalar_one_or_none()
            
            # Run async function safely from sync context
            patient_data = None
            try:
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        from backend.src.database.connection import create_async_session_maker
                        fresh_session_maker = create_async_session_maker()
                        return new_loop.run_until_complete(_fetch_patient_data_async(patient_id, fresh_session_maker))
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_in_thread)
                    patient_data = future.result(timeout=10)
            except Exception as e:
                print(f"Warning: Could not fetch patient data: {e}")
            
            # Format patient details with useful info for doctors
            patient_details = {
                "name": collected_info.get("name", "Unknown"),
                "phone": collected_info.get("phone"),
                "patient_id": patient_id
            }
            
            # Add additional useful details if available
            if patient_data:
                if patient_data.blood_group:
                    patient_details["blood_group"] = patient_data.blood_group
                if patient_data.gender:
                    patient_details["gender"] = patient_data.gender
                if patient_data.date_of_birth:
                    # Calculate age
                    age = (datetime.now().date() - patient_data.date_of_birth).days // 365
                    patient_details["age"] = age
                    patient_details["date_of_birth"] = str(patient_data.date_of_birth)
            
            # Format history summary
            history_records = patient_history.get("history", []) if patient_history else []
            past_history_summary = "\n".join([
                f"{record.get('visit_date', 'Unknown')}: {record.get('service_type', 'Unknown')} - {record.get('diagnosis', 'No diagnosis')}"
                for record in history_records[:10]
            ]) if history_records else "No previous history"
            
            # Get the original medical request (not the date/time response)
            # Priority: 1) user_request from state (stored when asking for date/time), 2) look back in conversation for medical request
            original_medical_request = user_request
            if not original_medical_request:
                # Look back through conversation messages to find the original medical request
                # Skip date/time related messages and find the actual medical need
                for msg in reversed(messages):
                    if isinstance(msg, HumanMessage):
                        content = msg.content.lower()
                        # Skip messages that are just date/time responses
                        time_indicators = ["tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "next week", "at ", "pm", "am", ":", "preferred appointment"]
                        if not any(indicator in content for indicator in time_indicators):
                            # This looks like a medical request, not a date/time
                            original_medical_request = msg.content
                            print(f"DEBUG: Found original medical request in conversation: '{original_medical_request}'")
                            break
                # If still not found, use last_user_message as fallback
                if not original_medical_request:
                    original_medical_request = last_user_message or ""
            
            # Determine priority from original medical request
            user_request_for_priority = original_medical_request or ""
            user_request_lower = user_request_for_priority.lower()
            priority = 5 if any(word in user_request_lower for word in ["urgent", "emergency", "immediate", "broken", "severe", "accident"]) else 3
            
            # Extract clean patient request description using LLM - use the ORIGINAL medical request
            clean_description = "Patient request"  # Default fallback
            print(f"DEBUG: Extracting patient request from original medical request: '{original_medical_request}'")
            try:
                # Use .invoke() to call the LangChain tool
                extraction_result = extract_patient_request.invoke({"message": original_medical_request})
                print(f"DEBUG: Extraction result: {extraction_result}")
                if isinstance(extraction_result, dict) and extraction_result.get("success"):
                    clean_description = extraction_result.get("description", "Patient request")
                    print(f"DEBUG: Using extracted description: '{clean_description}'")
                elif hasattr(extraction_result, "description"):
                    clean_description = extraction_result.description
                    print(f"DEBUG: Using extracted description (attr): '{clean_description}'")
            except Exception as e:
                print(f"Warning: Could not extract patient request with LLM: {e}")
                import traceback
                traceback.print_exc()
                # Fallback: simple cleanup without LLM
                clean_description = user_request_for_priority.split("(")[0].strip() if "(" in user_request_for_priority else user_request_for_priority.strip()
                # Remove common time phrases (case insensitive)
                time_phrases = ["tomorrow", "next week", "next monday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "at 7:00 PM", "at 7:00 pm", "at 10:00 AM", "at 10:00 am", "Preferred appointment time", "preferred appointment"]
                for phrase in time_phrases:
                    clean_description = clean_description.replace(phrase, "").replace(phrase.capitalize(), "").strip()
                # Clean up extra spaces, commas, and "at"
                clean_description = clean_description.replace(", ,", ",").replace("  ", " ").replace(" at ", " ").strip()
                if not clean_description:
                    clean_description = "Patient request"
                print(f"DEBUG: Using fallback description: '{clean_description}'")
            
            # Generate patient case summary for llm_summary - use the ORIGINAL medical request
            patient_case_summary = "Patient case details"  # Default fallback
            try:
                # Use .invoke() to call the LangChain tool
                case_summary_result = generate_patient_case_summary.invoke({
                    "user_request": original_medical_request or user_request_for_priority,
                    "patient_history": patient_history,
                    "patient_details": patient_details
                })
                if isinstance(case_summary_result, dict) and case_summary_result.get("success"):
                    patient_case_summary = case_summary_result.get("case_summary", "Patient case details")
                elif hasattr(case_summary_result, "case_summary"):
                    patient_case_summary = case_summary_result.case_summary
            except Exception as e:
                print(f"Warning: Could not generate patient case summary with LLM: {e}")
                import traceback
                traceback.print_exc()
                # Fallback: create simple summary
                patient_case_summary = f"Patient request: {clean_description}"
                if patient_details:
                    if patient_details.get("age"):
                        patient_case_summary += f"\nAge: {patient_details['age']} years"
                    if patient_details.get("blood_group"):
                        patient_case_summary += f"\nBlood Group: {patient_details['blood_group']}"
            
            system_prompt = f"""You are a helpful AI assistant for a hospital. The patient has been verified and you've shown their history.

The patient said: "{user_request or last_user_message or 'No request'}"
Appointment Date/Time: {appointment_datetime or 'Not provided'}

CRITICAL WORKFLOW - You MUST call all 3 tools in this EXACT order, then END:

STEP 1: Determine service_type from the request:
   - "broken leg/hand/arm", "fracture", "bone", "orthopedic", "accident" → "orthopedics"
   - "heart", "chest pain", "cardiac" → "cardiology"
   - "headache", "neurological", "brain" → "neurology"
   - "blood test", "lab work" → "blood_test"
   - "emergency", "urgent" → "emergency"
   - "mental", "depression", "anxiety" → "mental_health"
   - "skin", "rash" → "dermatology"
   - "child", "pediatric" → "pediatrics"
   - "women", "gynecological" → "gynecology"
   - "surgery" → "surgery_consultation"
   - "physical therapy" → "physical_therapy"
   - "pain" → "pain_management"
   - "imaging", "scan", "x-ray", "MRI" → "imaging"
   - "lab test" → "lab_test"
   - Default: "general_consultation"

STEP 2: You MUST call get_service_persons_by_type FIRST:
   - Call: get_service_persons_by_type(service_type=[determined_type])
   - This will ONLY return doctors where is_active=True (available doctors)
   - Wait for the result before proceeding
   - If the result shows status="error" or count=0 or empty doctors list, inform the user politely that no doctors are currently available for this service type and END gracefully

STEP 3: You MUST call rank_doctors_with_llm SECOND:
   - Use the doctors list from get_service_persons_by_type result (these are already filtered to is_active=True)
   - IMPORTANT: All doctors in the list are already available (is_active=True), so prioritize based on:
     * Specialization match with patient history
     * Service type alignment
     * Patient's current symptoms/needs
     * Relevance to the medical condition
   - Call: rank_doctors_with_llm(
       patient_history=[patient_history from state],
       user_request="{user_request or last_user_message or 'No request'}",
       doctors=[list from step 2 result],
       service_type=[determined type]
     )
   - Wait for the result - you will get ranked_doctors (up to 5 doctors, or fewer if not enough available)
   - If ranking fails (status="error"), inform the user and END gracefully

STEP 4: You MUST call create_multiple_tickets THIRD:
   - CRITICAL: You MUST extract the ranked_doctors list from the rank_doctors_with_llm tool result
   - The rank_doctors_with_llm result is a ToolMessage with content like: {{"status": "success", "ranked_doctors": [{{"doctor_id": "...", "name": "...", "rank": 1, "reason": "..."}}, ...]}}
   - Extract the "ranked_doctors" array from that result and pass it directly to create_multiple_tickets
   - Call: create_multiple_tickets(
       patient_id="{patient_id}",
       conversation_id="{state.get('conversation_id', '')}",
       ranked_doctors=[EXTRACT THE ranked_doctors ARRAY FROM rank_doctors_with_llm RESULT - this is a list of dicts, each with doctor_id, name, rank, reason],
       service_type=[determined type],
       description="{clean_description}",
       patient_details={json.dumps(patient_details)},
       past_history_summary="{past_history_summary[:500]}",
       llm_summary="{patient_case_summary}",
       priority={priority}
     )
   - CRITICAL: You MUST use EXACTLY this description: "{clean_description}" - DO NOT modify it or use any other text
   - CRITICAL: You MUST use EXACTLY this llm_summary: "{patient_case_summary}" - DO NOT modify it or add doctor ranking info
   - IMPORTANT: ranked_doctors MUST be the actual list from the tool result, not a string or empty list
   - Each doctor in ranked_doctors must be a dict with: doctor_id (string), name (string), rank (integer), reason (string)
   - This will create tickets for ALL ranked doctors (up to 5, or fewer if not enough available)
   - If ticket creation fails (status="error"), inform the user and END gracefully

STEP 5: After create_multiple_tickets completes, check the result CAREFULLY:
   - The tool ALWAYS returns a dict with "status" and "tickets_created" fields
   - If status="success" AND tickets_created > 0: Tickets were created successfully! Format your response showing:
     * All ranked doctors with their ranks, names, reasons, and ticket IDs
     * IMPORTANT: It's perfectly normal to have fewer than 5 doctors (e.g., 2, 3, or 4 doctors). This is NOT an error - it just means fewer doctors are available for this service type.
     * Confirm that tickets have been created successfully for the preferred appointment time: {appointment_datetime or 'Not specified'}
     * Be positive and helpful - tell the patient their appointment tickets have been created successfully
   - CRITICAL RULE: If tickets_created > 0 (even if status is unclear or missing), treat it as SUCCESS and inform the patient positively
   - ONLY report an error if BOTH conditions are true: status="error" AND tickets_created=0
   - If you see tickets_created=2 (or any number > 0), that means tickets were successfully created - tell the patient success!

STEP 3: You MUST call create_multiple_tickets THIRD:
   - Use the ranked_doctors from step 2 result
   - Call: create_multiple_tickets(...)

MANDATORY REQUIREMENTS:
- You MUST call get_service_persons_by_type FIRST, then rank_doctors_with_llm, then create_multiple_tickets
- Do NOT skip any of these 3 tool calls
- Do NOT call tools in a different order
- Do NOT call create_multiple_tickets without first calling rank_doctors_with_llm
- create_multiple_tickets MUST receive the ranked_doctors from rank_doctors_with_llm result
- After create_multiple_tickets succeeds (status="success"), END immediately and show success message
- Remember: get_service_persons_by_type already filters to is_active=True doctors only
- IMPORTANT: Having fewer than 5 doctors (e.g., 2 or 3) is perfectly normal and should be treated as SUCCESS, not an error

Patient ID: {patient_id}
"""
        else:
            # Normal verified patient flow
            system_prompt = f"""You are a helpful AI assistant for a hospital. The patient has already been verified.

Patient ID: {patient_id}
Conversation ID: {state.get("conversation_id")}
Focus on understanding their current needs and helping them."""
    else:
        # Patient not verified - need to collect info first
        # ROOT CAUSE FIX: Get current patient info from state to show what's already collected
        patient_info = get_patient_info(state)
        collected_name = patient_info.name
        collected_phone = patient_info.phone
        collected_dob = patient_info.date_of_birth
        
        # Build list of what's already collected and what's missing
        collected_fields = []
        missing_fields = []
        
        # Also check if the last user message is a greeting and we haven't asked for verification yet
        last_user_message = None
        if human_messages:
            last_user_message = human_messages[-1].content.lower() if hasattr(human_messages[-1], 'content') else ""
        
        # Check if verification was already requested
        verification_requested = any(
            isinstance(msg, AIMessage) and (
                "verify your identity" in msg.content.lower() or
                "provide me with your" in msg.content.lower() or
                ("full name" in msg.content.lower() and "phone number" in msg.content.lower())
            )
            for msg in messages
        )
        
        # If it's the first message OR user sent a greeting and verification wasn't requested yet
        greeting_keywords = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "greetings"]
        is_greeting = last_user_message and any(greeting in last_user_message for greeting in greeting_keywords)
        
        if is_first_message or (is_greeting and not verification_requested):
            # FIRST MESSAGE OR GREETING: Must ask for verification details immediately
            # Return a direct hardcoded message - don't let LLM generate it
            # This ensures consistency and prevents LLM from ignoring instructions
            verification_request = AIMessage(content="""Hello! I'm your AI assistant here to help you. To verify your identity and access your medical records, I'll need a few details. Could you please provide me with your:

1. Full name
2. Phone number  
3. Date of birth (in YYYY-MM-DD format, e.g., 1955-02-28)

Once you provide these details, I'll be able to assist you with scheduling appointments, creating service tickets, or answering any questions you may have.""")

            print(f"DEBUG: Returning hardcoded verification request for first message or greeting")
            return {
                **state,
                "messages": [verification_request]
            }
        else:
            # Some info collected - ask for remaining
            collected_text = "\n".join(f"- {field}" for field in collected_fields)
            missing_text = "\n".join(f"{i+1}. {field}" for i, field in enumerate(missing_fields))
            
            system_prompt = f"""You are a helpful AI assistant for a hospital call center.

CRITICAL RULES - YOU MUST FOLLOW THESE:
1. You CANNOT access any database or call any SQL tools until the patient is verified
2. You MUST ALWAYS call extract_patient_info tool when user provides ANY new information
3. You CANNOT call verify_patient, get_patient_history, or any other database tools yet

CURRENT STATE - Information Already Collected:
{collected_text}

REMAINING INFORMATION NEEDED:
{missing_text}

WORKFLOW:
1. Acknowledge what information you already have (be conversational, e.g., "I have your name as [name]. Thank you!")
2. Ask ONLY for the remaining information needed (do NOT repeat what you already have)
3. If the user provides ANY new information in their message, you MUST call extract_patient_info(message="[user's message]") tool FIRST
4. After calling the tool, acknowledge what you received and ask for what's still missing
5. Once you have all three pieces (name, phone, DOB), the system will automatically proceed to verification

EXAMPLE RESPONSE:
"Thank you! I have your name as [name]. I still need:
1. Your phone number
2. Your date of birth (YYYY-MM-DD format)

Could you please provide these?"

IMPORTANT: 
- Do NOT ask for information you already have
- ALWAYS call extract_patient_info tool if user provides new information
- Be conversational and friendly"""
    
    # Add system prompt to messages
    messages = [AIMessage(content=system_prompt)] + messages
    
    # Call LLM
    response = llm_with_tools.invoke(messages)
    
    # Update state with response
    current_messages = state.get("messages", [])
    current_messages.append(response)
    state["messages"] = current_messages
    
    return state


def process_tool_results(state: AgentState) -> AgentState:
    """Process tool results and update state from tool outputs."""
    from langchain_core.messages import ToolMessage
    import json

    messages = state.get("messages", [])
    
    # Process tool messages and update state
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            tool_name = str(msg.name) if hasattr(msg, "name") else ""
            
            # Process extract_patient_info result - ROOT CAUSE FIX
            if "extract_patient_info" in tool_name:
                try:
                    content = msg.content
                    result = json.loads(content) if isinstance(content, str) else content
                    if isinstance(result, dict) and result.get("success"):
                        extracted = result.get("extracted", {})
                        if extracted:
                            # Get current patient info from state
                            patient_info = get_patient_info(state)
                            # Update only non-None fields (merge with existing)
                            if extracted.get("name"):
                                patient_info.name = extracted["name"]
                            if extracted.get("phone"):
                                patient_info.phone = extracted["phone"]
                            if extracted.get("date_of_birth"):
                                patient_info.date_of_birth = extracted["date_of_birth"]
                            # Save updated patient info back to state
                            set_patient_info(state, patient_info)
                            print(f"[STATE UPDATE] Extracted patient info: {extracted}")
                except Exception as e:
                    print(f"Error processing extract_patient_info result: {e}")
            
            # Process verify_patient result
            elif "verify_patient" in tool_name:
                try:
                    content = msg.content
                    result = json.loads(content) if isinstance(content, str) else content
                    if isinstance(result, dict) and result.get("found"):
                        state["patient_verified"] = True
                        state["patient_id"] = result["patient_id"]
                        patient_info = get_patient_info(state)
                        patient_info.patient_id = result["patient_id"]
                        set_patient_info(state, patient_info)
                except Exception as e:
                    print(f"Error processing verify_patient result: {e}")
            
            # Process get_patient_history result
            elif "get_patient_history" in tool_name:
                try:
                    content = msg.content
                    result = json.loads(content) if isinstance(content, str) else content
                    if isinstance(result, dict) and result.get("status") == "success":
                        state["patient_history"] = result
                except Exception as e:
                    print(f"Error processing get_patient_history result: {e}")
            
            # Process get_available_doctors_by_type_and_time result
            elif "get_available_doctors_by_type_and_time" in tool_name:
                try:
                    content = msg.content
                    result = json.loads(content) if isinstance(content, str) else content
                    result_status = result.get("status", "error")
                    
                    if result_status == "schema_error":
                        # Schema error - log and set error state
                        error_msg = result.get("error", "Unknown schema error")
                        diagnostic = result.get("diagnostic", "Schema validation failed")
                        print(f"[SCHEMA ERROR] {error_msg}")
                        print(f"[SCHEMA ERROR] Diagnostic: {diagnostic}")
                        state["doctors_found"] = False
                        state["doctors_error"] = f"SCHEMA ERROR: {diagnostic}. Details: {error_msg}"
                    elif result_status == "success":
                        state["available_doctors"] = result.get("doctors", [])
                        appointment_prefs = get_appointment_preferences(state)
                        if result.get("service_type"):
                            appointment_prefs.service_type = result["service_type"]
                        if result.get("preferred_date_time"):
                            appointment_prefs.preferred_date_time = result["preferred_date_time"]
                            hitl = get_hitl(state)
                            hitl.clear_questions()
                            set_hitl(state, hitl)
                        set_appointment_preferences(state, appointment_prefs)
                        
                        doctors_list = result.get("doctors", [])
                        diagnostic = result.get("diagnostic")
                        if not doctors_list or len(doctors_list) == 0:
                            state["doctors_found"] = False
                            # Use diagnostic information if available
                            if diagnostic and isinstance(diagnostic, dict):
                                reason = diagnostic.get("reason", f"No doctors found for service type: {result.get('service_type')}")
                                state["doctors_error"] = reason
                                print(f"[DIAGNOSTIC] No doctors found: {reason}")
                            else:
                                state["doctors_error"] = f"No doctors found for service type: {result.get('service_type')}"
                        else:
                            state["doctors_found"] = True
                    else:
                        # Error status
                        error_msg = result.get("error", "Unknown error")
                        print(f"[ERROR] Error fetching doctors: {error_msg}")
                        state["doctors_found"] = False
                        state["doctors_error"] = f"Error fetching doctors: {error_msg}"
                except Exception as e:
                    import traceback
                    error_msg = f"Error processing get_available_doctors_by_type_and_time result: {e}\n{traceback.format_exc()}"
                    print(f"[ERROR] {error_msg}")
                    state["doctors_found"] = False
                    state["doctors_error"] = error_msg
            
            # Process rank_doctors_with_llm result
            elif "rank_doctors_with_llm" in tool_name:
                try:
                    content = msg.content
                    result = json.loads(content) if isinstance(content, str) else content
                    if isinstance(result, dict) and result.get("status") in ["success", "fallback"]:
                        from backend.src.config import settings
                        top_n = getattr(settings, 'top_doctors_count', 5)
                        ranked_doctors = result.get("ranked_doctors", [])[:top_n]
                        
                        doctor_ranking = get_doctor_ranking(state)
                        doctor_ranking.ranked_doctors = ranked_doctors
                        doctor_ranking.ranking_success = True
                        set_doctor_ranking(state, doctor_ranking)
                    else:
                        doctor_ranking = get_doctor_ranking(state)
                        doctor_ranking.ranking_success = False
                        doctor_ranking.ranking_error = result.get("error", "Unknown error")
                        set_doctor_ranking(state, doctor_ranking)
                except Exception as e:
                    print(f"Error processing rank_doctors_with_llm result: {e}")
                    doctor_ranking = get_doctor_ranking(state)
                    doctor_ranking.ranking_success = False
                    set_doctor_ranking(state, doctor_ranking)
            
            # Process create_multiple_tickets result
            elif "create_multiple_tickets" in tool_name:
                try:
                    content = msg.content
                    result = json.loads(content) if isinstance(content, str) else content
                    if isinstance(result, dict) and result.get("status") == "success":
                        tickets = result.get("tickets", [])
                        ticket_creation = get_ticket_creation(state)
                        ticket_creation.doctor_tickets = tickets
                        ticket_creation.tickets_created = result.get("tickets_created", len(tickets))
                        ticket_creation.tickets_creation_success = True
                        set_ticket_creation(state, ticket_creation)
                        state["doctor_tickets_created"] = True
                        state["ticket_created"] = True
                        hitl = get_hitl(state)
                        hitl.clear_questions()
                        set_hitl(state, hitl)
                except Exception as e:
                    print(f"Error processing create_multiple_tickets result: {e}")
                    ticket_creation = get_ticket_creation(state)
                    ticket_creation.tickets_creation_success = False
                    set_ticket_creation(state, ticket_creation)
    
    return state


def create_graph(checkpointer: Optional[AsyncPostgresSaver] = None):
    """Create the LangGraph StateGraph with checkpointer."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    # ROOT CAUSE FIX: Remove collect_info node - agent handles extraction through tools
    workflow.add_node("verify_patient", verify_patient_node)
    workflow.add_node("agent", call_model)
    # Use conditional tool node based on verification status
    workflow.add_node("tools", conditional_tool_node)
    workflow.add_node("process_results", process_tool_results)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Add edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "verify_patient": "verify_patient",
            "end": END
        }
    )
    
    workflow.add_edge("tools", "process_results")
    workflow.add_edge("process_results", "agent")
    workflow.add_edge("verify_patient", "agent")
    
    # Compile with checkpointer
    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    else:
        return workflow.compile()


async def get_graph():
    """Get or create graph instance with checkpointer."""
    checkpointer = await get_checkpointer()
    return create_graph(checkpointer=checkpointer)

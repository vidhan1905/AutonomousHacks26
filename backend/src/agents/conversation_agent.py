"""LangGraph conversation agent for automated patient conversations."""
from typing import TypedDict, Annotated, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from operator import itemgetter
import uuid
import json
from datetime import datetime

from backend.src.config import settings
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

# Bind tools to LLM
tools = [
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
    rank_doctors_with_llm,
    create_multiple_tickets
]

llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)


def should_continue(state: AgentState) -> str:
    """Determine next step based on state."""
    messages = state["messages"]
    if not messages:
        return "end"
    
    last_message = messages[-1]
    patient_verified = state.get("patient_verified", False)
    collected_info = state.get("collected_info", {})
    
    # If patient is not verified, check if we have all required info
    if not patient_verified:
        has_name = bool(collected_info.get("name"))
        has_phone = bool(collected_info.get("phone"))
        has_dob = bool(collected_info.get("date_of_birth"))

        # If LLM wants to use a tool, check if it's appropriate
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            tool_names = [tc.get("name") for tc in last_message.tool_calls if isinstance(tc, dict)]

            # ALWAYS allow extract_patient_info - it's the first step
            if "extract_patient_info" in tool_names:
                return "tools"  # Allow extraction

            # Allow verify_patient or create_patient if we have all info
            if "verify_patient" in tool_names or "create_patient" in tool_names:
                # Check if we have all required fields
                if has_name and has_phone and has_dob:
                    return "tools"  # Allow verification
                else:
                    # Block tool call - we don't have all info yet
                    # Return "end" to let the LLM ask for missing info in next turn
                    return "end"
            else:
                # Other tools (like get_patient_history, create_ticket, schedule_appointment)
                # should NOT be called until patient is verified
                # UNLESS it's get_patient_history which can be called after verify_patient
                if "get_patient_history" in tool_names and collected_info.get("patient_id"):
                    return "tools"  # Allow fetching history after verification
                return "end"  # Block these tools
        
        # If LLM gave a regular message (no tool calls)
        # Check if we have all required info to verify
        if has_name and has_phone and has_dob:
            # We have info but haven't verified yet - route to verify
            return "verify_patient"
        else:
            # Missing info - end turn and wait for user to provide it
            return "end"
    
    # Patient is verified - allow normal flow
    # Check if last message is a ToolMessage - if so, agent should generate final response
    from langchain_core.messages import ToolMessage
    if isinstance(last_message, ToolMessage):
        tool_name = str(last_message.name) if hasattr(last_message, "name") else ""
        
        # Check if create_multiple_tickets was just called successfully
        if "create_multiple_tickets" in tool_name:
            # Tickets created - end immediately
            return "end"
        
        # Check if doctor tickets are already created
        if state.get("doctor_tickets_created", False):
            return "end"
        
        # Enforce workflow sequence for doctor recommendation
        history_shown = state.get("history_shown", False)
        doctor_tickets_created = state.get("doctor_tickets_created", False)
        
        if history_shown and not doctor_tickets_created:
            # We're in doctor recommendation workflow - enforce sequence
            
            # After get_service_persons_by_type, ensure we proceed to rank_doctors_with_llm
            if "get_service_persons_by_type" in tool_name:
                # Check if doctors were found
                doctors_found = state.get("doctors_found", True)  # Default to True if not set
                if not doctors_found:
                    # No doctors found - end gracefully (LLM will inform user)
                    return "end"
                # Doctors found - continue to agent to call rank_doctors_with_llm
                return "agent"
            
            # After rank_doctors_with_llm, ensure we proceed to create_multiple_tickets
            if "rank_doctors_with_llm" in tool_name:
                # Check if ranking was successful
                ranking_success = state.get("ranking_success", True)  # Default to True if not set
                ranked_doctors = state.get("ranked_doctors", [])
                
                if not ranking_success or not ranked_doctors:
                    # Ranking failed - end gracefully (LLM will inform user)
                    return "end"
                # Ranking successful - continue to agent to call create_multiple_tickets
                return "agent"
        
        # Count tool messages to prevent infinite loops
        tool_message_count = sum(1 for msg in reversed(messages[-5:]) if isinstance(msg, ToolMessage))
        if tool_message_count > 3:  # Reduced threshold for faster termination
            return "end"
        
        return "agent"
    
    # If LLM wants to use a tool, route to tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    # If doctor tickets are created, we're done with doctor recommendation flow
    if state.get("doctor_tickets_created", False):
        return "end"
    
    # If ticket is created, we're done
    if state.get("ticket_created", False):
        return "end"
    
    # LLM gave a response without tool calls - end the turn and wait for user input
    # Ensure there's actual content
    if hasattr(last_message, 'content') and last_message.content and str(last_message.content).strip():
        return "end"
    else:
        # Empty response - end to prevent loops
        return "end"


def collect_info_node(state: AgentState) -> AgentState:
    """Node for collecting required patient information."""
    collected = state.get("collected_info", {})
    missing = state.get("required_fields_missing", [])
    retry_count = state.get("retry_count", {})
    
    # Build prompt to ask for missing fields
    if missing:
        field = missing[0]
        retries = retry_count.get(field, 0)
        
        if retries >= 3:
            prompt = f"I understand you may have concerns, but I need your {field} to verify your identity and provide you with the best care. This information is required for security and to access your medical records. Could you please provide your {field}?"
        else:
            prompt = f"To help you, I need your {field}. Could you please share it?"
        
        messages = state["messages"] + [AIMessage(content=prompt)]
        return {
            **state,
            "messages": messages,
            "retry_count": {**retry_count, field: retries + 1}
        }
    
    # No missing fields, return state as-is (will end)
    return state


def process_tool_results(state: AgentState) -> AgentState:
    """Process tool results and update collected_info from extraction and verification results."""
    from langchain_core.messages import ToolMessage
    import json

    messages = state["messages"]
    collected_info = state.get("collected_info", {})
    patient_verified = state.get("patient_verified", False)

    # Look for extract_patient_info tool results first
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            # Check if this is from extract_patient_info tool
            if "extract_patient_info" in str(msg.name) or "extract_patient_info" in str(getattr(msg, "tool_call_id", "")):
                try:
                    content = msg.content
                    if isinstance(content, str):
                        try:
                            result = json.loads(content)
                        except:
                            result = {}
                    else:
                        result = content

                    # Extract the extracted info and merge with collected_info
                    if isinstance(result, dict) and result.get("success"):
                        extracted = result.get("extracted", {})
                        if "name" in extracted:
                            collected_info["name"] = extracted["name"]
                        if "phone" in extracted:
                            collected_info["phone"] = extracted["phone"]
                        if "date_of_birth" in extracted:
                            collected_info["date_of_birth"] = extracted["date_of_birth"]
                except Exception as e:
                    print(f"Error processing extract_patient_info result: {e}")

    # Look for verify_patient tool results to extract patient info
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            # Check if this is from verify_patient tool
            if "verify_patient" in str(msg.name) or "verify_patient" in str(getattr(msg, "tool_call_id", "")):
                try:
                    content = msg.content
                    if isinstance(content, str):
                        try:
                            result = json.loads(content)
                        except:
                            result = {}
                    else:
                        result = content

                    # If patient found, extract info from result and mark as verified
                    if isinstance(result, dict) and result.get("found"):
                        patient_verified = True
                        if "name" in result:
                            collected_info["name"] = result["name"]
                        if "phone" in result:
                            collected_info["phone"] = result["phone"]
                        if "patient_id" in result:
                            collected_info["patient_id"] = result["patient_id"]
                            state["patient_id"] = result["patient_id"]
                except Exception as e:
                    print(f"Error processing verify_patient result: {e}")

    # Also extract from tool call arguments if available
    for msg in reversed(messages):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tool_call in msg.tool_calls:
                if tool_call.get("name") == "verify_patient":
                    args = tool_call.get("args", {})
                    if "name" in args:
                        collected_info["name"] = args["name"]
                    if "phone" in args:
                        collected_info["phone"] = args["phone"]
                    if "date_of_birth" in args:
                        collected_info["date_of_birth"] = args["date_of_birth"]
                elif tool_call.get("name") == "extract_patient_info":
                    # Extract from the tool call args (the message being parsed)
                    args = tool_call.get("args", {})
                    # The extraction tool takes the message as input
                    # Results will be in the ToolMessage, not here
                    pass

    # Check for patient history results
    patient_history = state.get("patient_history")
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            tool_name = str(msg.name) if hasattr(msg, "name") else ""
            if "get_patient_history" in tool_name:
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
                        patient_history = result
                except Exception as e:
                    print(f"Error processing get_patient_history result: {e}")

    # Check for service type determination and doctor query results
    service_type_determined = state.get("service_type_determined")
    ranked_doctors = state.get("ranked_doctors")
    
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
        updated_state["patient_verified"] = True
    if ticket_created:
        updated_state["ticket_created"] = True
    if patient_history:
        updated_state["patient_history"] = patient_history
    if ranked_doctors:
        updated_state["ranked_doctors"] = ranked_doctors
    if service_type_determined:
        updated_state["service_type_determined"] = service_type_determined
    # Ensure doctor_tickets_created is preserved if already set
    if state.get("doctor_tickets_created"):
        updated_state["doctor_tickets_created"] = True
    if state.get("doctor_tickets"):
        updated_state["doctor_tickets"] = state["doctor_tickets"]

    return updated_state


def verify_patient_node(state: AgentState) -> AgentState:
    """Node for verifying patient."""
    collected = state.get("collected_info", {})
    
    # Validate required fields
    validation = validate_required_fields.invoke({"collected_info": collected})
    if not validation.get("all_present", False):
        return {
            **state,
            "required_fields_missing": validation.get("missing_fields", [])
        }
    
    # Call verify_patient tool (sync function that handles async internally)
    result = verify_patient.invoke({
        "name": collected["name"],
        "phone": collected["phone"],
        "date_of_birth": collected["date_of_birth"]
    })
    
    if result.get("found", False):
        return {
            **state,
            "patient_id": result["patient_id"],
            "patient_verified": True,
            "next_action": "fetch_history",
            "collected_info": {**collected, "patient_id": result["patient_id"]}
        }
    else:
        # Patient not found, need to create new patient
        # But first check if create_patient returned "already_exists"
        return {
            **state,
            "patient_verified": False,
            "next_action": "create_patient",
            "verify_error": result.get("error") or result.get("message")
        }


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
    """Call the LLM with current state."""
    messages = state["messages"]
    collected_info = state.get("collected_info", {})
    
    # Add system prompt
    patient_verified = state.get("patient_verified", False)
    patient_id = state.get("patient_id")
    
    if patient_verified and patient_id:
        # Simplified linear workflow
        history_shown = state.get("history_shown", False)
        patient_history = state.get("patient_history")
        doctor_tickets_created = state.get("doctor_tickets_created", False)
        
        # STEP 1: Show history if not shown yet
        if not history_shown:
            if not patient_history:
                # Trigger history fetch
                system_prompt = """You are a helpful AI assistant for a hospital. The patient has been verified.

1. Call get_patient_history(patient_id=""" + str(patient_id) + """)
2. After getting history, show it to the patient in a friendly format
3. Ask: "What help do you need today?"
4. END - wait for user response

Patient ID: """ + str(patient_id) + """
Conversation ID: """ + str(state.get("conversation_id", "")) + """
"""
            else:
                # History fetched, show it
                history_records = patient_history.get("history", [])
                if history_records:
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
                state = {**state, "history_shown": True}
        
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
            
            # Handle error case: No doctors found
            if doctors_found is False:
                system_prompt = f"""You are a helpful AI assistant for a hospital. The patient has been verified and you've shown their history.

The patient said: "{last_user_message or 'No request'}"

ERROR: No doctors were found for the requested service type.

You must inform the patient politely that:
- No doctors are currently available for their requested service type
- They may need to try a different service type or check back later
- You apologize for the inconvenience

Be empathetic and helpful. END after informing the patient.

Patient ID: {patient_id}
"""
                # Skip the rest of the workflow
                messages = state["messages"]
                if not hasattr(messages[-1], "content") or "helpful AI assistant" not in str(messages[-1].content):
                    messages = [AIMessage(content=system_prompt)] + messages
                response = llm_with_tools.invoke(messages)
                return {
                    **state,
                    "messages": [response]
                }
            
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

STEP 6: END immediately - Do NOT call any more tools after create_multiple_tickets

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
            # Normal verified patient flow (for other requests)
            system_prompt = """You are a helpful AI assistant for a hospital. The patient has already been verified and you have access to their medical history.

Your role is to:
1. Help patients with their current health concerns and service requests
2. Understand what the patient needs

KEY DISTINCTIONS:
- **schedule_appointment**: Use when patient says "schedule", "book", "appointment", "visit", "follow-up", "want to see a doctor"
  Example: "I'd like to schedule an appointment" → Use schedule_appointment(patient_id=..., service_type=..., preferred_date=...)
  
- **create_ticket**: Use when patient needs a specific SERVICE like "blood test", "lab test", "imaging", "need a test"
  Example: "I need a blood test" → Use create_ticket(patient_id=..., service_type="blood_test", ...)

3. When patient wants to SCHEDULE/BOOK an appointment:
   - Use schedule_appointment tool
   - Extract preferred_date from their message (e.g., "next week" = 7 days from now, "tomorrow" = next day)
   - Determine service_type from context (general_consultation, cardiology, etc.)
   - Format date as ISO: "YYYY-MM-DDTHH:MM:SS" (e.g., "2025-01-17T10:00:00")
   
4. When patient needs a SERVICE (test, procedure):
   - Use create_ticket tool
   - Include comprehensive patient information (blood group, past history summary, current symptoms)
   - Set appropriate priority (1=low, 2=medium, 3=high, 4=urgent, 5=critical)

5. Be empathetic, professional, and helpful

IMPORTANT:
- The patient is ALREADY VERIFIED - do NOT ask for their name, phone, or date of birth again
- Patient ID is: """ + str(patient_id) + """
- Conversation ID is: """ + str(state.get("conversation_id", "")) + """
- Focus on understanding their current needs and helping them
- If they say "schedule", "book", "appointment", "follow-up" → use schedule_appointment
- If they say "need", "want", "test", "service" → use create_ticket
- Always be helpful and proactive in assisting them"""
    else:
        # Patient not verified - need to collect info first
        # Check if this is the first message (only patient messages, no previous LLM responses)
        # Filter out system prompts when checking
        human_messages = [m for m in messages if isinstance(m, HumanMessage)]
        ai_messages = [m for m in messages if isinstance(m, AIMessage) and not ("helpful AI assistant" in m.content or "You are a helpful" in m.content)]
        is_first_message = len(human_messages) == 1 and len(ai_messages) == 0
        
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
            # SUBSEQUENT MESSAGES: Check if info collected, if not ask again or extract it
            collected = state.get("collected_info", {})
            has_name = bool(collected.get("name"))
            has_phone = bool(collected.get("phone"))
            has_dob = bool(collected.get("date_of_birth"))

            if not (has_name and has_phone and has_dob):
                # Still missing info - but first check if user just provided it
                system_prompt = f"""You are a helpful AI assistant for a hospital. The patient needs to be verified.

CRITICAL WORKFLOW:
1. **First, check if the user just provided their information** in their latest message
   - If their message contains name, phone, or date of birth information:
     a. IMMEDIATELY call extract_patient_info(message=user_message_content) to extract structured data
     b. After extraction completes, call verify_patient with the extracted information

2. **If extraction found all fields** (name, phone, date_of_birth):
   - Call verify_patient(name=extracted_name, phone=extracted_phone, date_of_birth=extracted_dob)
   - Then call get_patient_history(patient_id=result["patient_id"]) if verification successful
   - Then ask "How can I assist you today?"

3. **If user hasn't provided information yet or extraction found nothing**:
   - Ask politely for the missing fields

Currently collected: {{"name": "{collected.get("name", "Not provided")}", "phone": "{collected.get("phone", "Not provided")}", "date_of_birth": "{collected.get("date_of_birth", "Not provided")}"}}

IMPORTANT:
- If you see a message like "My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28"
  → Use extract_patient_info first, then verify_patient
- Do NOT ask for information if the user just provided it
- Do NOT proceed with other services until verification is complete

Example flow:
User: "My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28"
You: [Call extract_patient_info(message="My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28")]
     [After extraction: Call verify_patient(name="April Maldonado", phone="001-852-326-5094x079", date_of_birth="1955-02-28")]
     [After verification: Call get_patient_history(patient_id=...)]
     [Respond: "Thank you, April! I've verified your identity and retrieved your medical history. How can I assist you today?"]"""
            else:
                # Has info but not verified yet - should verify
                system_prompt = """You are a helpful AI assistant for a hospital. The patient has provided their information but verification is pending.

You have collected:
- Name: """ + str(collected.get("name", "Not provided")) + """
- Phone: """ + str(collected.get("phone", "Not provided")) + """
- Date of Birth: """ + str(collected.get("date_of_birth", "Not provided")) + """

You MUST now call verify_patient with this information to proceed. Extract the exact values from the collected_info and call verify_patient immediately."""
    
    # Add system prompt only if not already present
    has_system_prompt = any(
        isinstance(msg, AIMessage) and ("helpful AI assistant" in msg.content or "You are a helpful" in msg.content)
        for msg in messages
    )
    
    if not has_system_prompt:
        messages = [AIMessage(content=system_prompt)] + messages
    
    # Add current context if patient is verified
    if patient_verified and patient_id:
        context_msg = f"CONTEXT: Patient is already verified (ID: {patient_id}). You have their medical history. Focus on their current request: {messages[-1].content if messages else 'No current message'}"
        messages.append(AIMessage(content=context_msg))
    
    response = llm_with_tools.invoke(messages)
    
    # Preserve state updates made during call_model
    updated_state = {**state}
    if "history_shown" in state:
        updated_state["history_shown"] = state["history_shown"]
    if "service_type_determined" in state:
        updated_state["service_type_determined"] = state.get("service_type_determined")
    if "ranked_doctors" in state:
        updated_state["ranked_doctors"] = state.get("ranked_doctors")
    if "doctor_tickets_created" in state:
        updated_state["doctor_tickets_created"] = state.get("doctor_tickets_created", False)
    
    return {
        **updated_state,
        "messages": [response]
    }


def create_graph():
    """Create the LangGraph StateGraph."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("collect_info", collect_info_node)
    workflow.add_node("verify_patient", verify_patient_node)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    workflow.add_node("process_results", process_tool_results)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Add edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "collect_info": "collect_info",
            "verify_patient": "verify_patient",
            "end": END
        }
    )
    
    workflow.add_edge("tools", "process_results")
    workflow.add_edge("process_results", "agent")
    workflow.add_edge("collect_info", "agent")
    workflow.add_edge("verify_patient", "agent")
    
    # Compile with increased recursion limit
    return workflow.compile()


# Create the graph instance
graph = create_graph()

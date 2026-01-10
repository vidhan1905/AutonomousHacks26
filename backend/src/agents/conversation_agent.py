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
from backend.src.agents.tools.extraction_tools import extract_patient_info
from backend.src.agents.tools.doctor_tools import (
    get_service_persons_by_type,
    get_available_doctors_by_type_and_time,
    rank_doctors_with_llm,
    create_multiple_tickets
)


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
            # Get last user message
            last_user_message = None
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    last_user_message = msg.content
                    break
            
            # Validate before doctor search (HITL check)
            can_proceed, question_msg = validate_before_doctor_search(state)
            if not can_proceed and question_msg:
                # Add question message and return (wait for user)
                messages = state.get("messages", [])
                messages.append(question_msg)
                state["messages"] = messages
                return state
            
            # All validations passed, proceed with doctor recommendation workflow
            from backend.src.config import settings
            top_n = getattr(settings, 'top_doctors_count', 5)
            
            appointment_prefs = get_appointment_preferences(state)
            preferred_date_time = appointment_prefs.preferred_date_time
            service_type = appointment_prefs.service_type
            
            system_prompt = f"""You are a helpful AI assistant for a hospital. The patient has been verified and you've shown their history.

The patient said: "{last_user_message or 'No request'}"
Preferred date/time: {preferred_date_time or 'Not specified'}
Service type: {service_type or 'Not specified'}

CRITICAL WORKFLOW - You MUST call all 3 tools in this EXACT order, then END:

STEP 1: You MUST call get_available_doctors_by_type_and_time FIRST:
   - Call: get_available_doctors_by_type_and_time(
       service_type="{service_type}",
       preferred_date_time="{preferred_date_time or ''}"
     )

STEP 2: You MUST call rank_doctors_with_llm SECOND:
   - Use the doctors list from step 1 result
   - Call: rank_doctors_with_llm(
       patient_history=[patient_history from state],
       user_request="{last_user_message or 'No request'}",
       doctors=[list from step 1 result],
       service_type="{service_type}",
       preferred_date_time="{preferred_date_time or ''}"
     )

STEP 3: You MUST call create_multiple_tickets THIRD:
   - Use the ranked_doctors from step 2 result
   - Call: create_multiple_tickets(...)

STEP 4: END immediately after create_multiple_tickets

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
        
        if collected_name:
            collected_fields.append(f"Name: {collected_name}")
        else:
            missing_fields.append("Full name")
        
        if collected_phone:
            collected_fields.append(f"Phone: {collected_phone}")
        else:
            missing_fields.append("Phone number")
        
        if collected_dob:
            collected_fields.append(f"Date of birth: {collected_dob}")
        else:
            missing_fields.append("Date of birth (YYYY-MM-DD format)")
        
        # Build conversational system prompt based on what's collected
        if not collected_fields:
            # Nothing collected yet - first greeting
            system_prompt = """You are a helpful AI assistant for a hospital call center.

CRITICAL RULES - YOU MUST FOLLOW THESE:
1. You CANNOT access any database or call any SQL tools until the patient is verified
2. You MUST ALWAYS call extract_patient_info tool when user provides ANY information (name, phone, or DOB)
3. You CANNOT call verify_patient, get_patient_history, or any other database tools yet

CURRENT STATE:
- No information collected yet

WORKFLOW:
1. If this is the first message, greet the user and ask for their name, phone, and date of birth
2. If the user provides ANY information in their message, you MUST call extract_patient_info(message="[user's message]") tool FIRST
3. After calling the tool, acknowledge what you received and ask for remaining information
4. Be conversational and friendly

YOUR FIRST MESSAGE should be:
"Hello! I'm your AI assistant here to help you. To verify your identity and access your medical records, I'll need a few details. Could you please provide me with your:
1. Full name
2. Phone number  
3. Date of birth (in YYYY-MM-DD format, e.g., 1955-02-28)

Once you provide these details, I'll be able to assist you with scheduling appointments, creating service tickets, or answering any questions you may have."

IMPORTANT: 
- ALWAYS call extract_patient_info tool if user provides ANY information
- The tool will extract name, phone, and/or DOB from the message
- After extraction, acknowledge what you got and ask for what's still missing"""
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

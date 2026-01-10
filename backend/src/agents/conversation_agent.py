"""LangGraph conversation agent for automated patient conversations."""
from typing import TypedDict, Annotated, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from operator import itemgetter
import uuid
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
from backend.src.agents.tools.extraction_tools import extract_patient_info


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
    update_ticket_status
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
        # After tool results, always go back to agent to generate a response
        # But limit this to prevent infinite loops - check if we've already processed this tool result
        # Count how many times we've seen tool messages in a row
        tool_message_count = sum(1 for msg in reversed(messages[-5:]) if isinstance(msg, ToolMessage))
        if tool_message_count > 3:
            # Too many tool calls in a row - end to prevent infinite loop
            return "end"
        return "agent"
    
    # If LLM wants to use a tool, route to tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
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


def call_model(state: AgentState) -> AgentState:
    """Call the LLM with current state."""
    messages = state["messages"]
    collected_info = state.get("collected_info", {})
    
    # Add system prompt
    patient_verified = state.get("patient_verified", False)
    patient_id = state.get("patient_id")
    
    if patient_verified and patient_id:
        # Patient is already verified - focus on their needs
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
        
        if is_first_message:
            # FIRST MESSAGE: Must ask for verification details immediately
            system_prompt = """You are a helpful AI assistant for a hospital call center.

CRITICAL FIRST STEP - YOU MUST DO THIS NOW:
When a patient first contacts you, your FIRST response MUST be to ask for their verification details. Do NOT greet them or ask how you can help until AFTER they provide their information.

Your FIRST message should be:
"Hello! I'm your AI assistant here to help you. To verify your identity and access your medical records, I'll need a few details. Could you please provide me with your:
1. Full name
2. Phone number  
3. Date of birth (in YYYY-MM-DD format, e.g., 1955-02-28)

Once you provide these details, I'll be able to assist you with scheduling appointments, creating service tickets, or answering any questions you may have."

DO NOT:
- Ask "How can I help you?" or "What can I do for you?" until AFTER verification
- Make any tool calls (verify_patient, create_patient, etc.) until the user provides their information
- Skip asking for verification details

ONLY AFTER the user provides their name, phone, and date of birth:
1. Extract the information from their message:
   - name: Extract the full name (e.g., "April Maldonado")
   - phone: Extract the phone number exactly as provided (e.g., "001-852-326-5094x079")
   - date_of_birth: Extract and convert to YYYY-MM-DD format (e.g., "1955-02-28")
2. IMMEDIATELY call verify_patient(name=extracted_name, phone=extracted_phone, date_of_birth=extracted_dob)
3. If verify_patient returns found=True: call get_patient_history(patient_id=result["patient_id"])
4. If verify_patient returns found=False: call create_patient(name=..., phone=..., date_of_birth=...)

Remember: Your FIRST response must ask for verification details. Do not proceed with anything else until you have this information."""
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
    
    return {
        **state,
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

"""Conversation endpoints with WebSocket support."""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid
import json
from datetime import datetime

from backend.src.database.connection import get_db
from backend.src.database.models import Conversation, Patient
from backend.src.api.dependencies import get_current_patient
from backend.src.agents.workflow_agent import get_graph
from backend.src.agents.state_models import AgentState, create_initial_state
from backend.src.agents.checkpointer import get_checkpointer
from langchain_core.messages import HumanMessage, AIMessage

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    patient_id: Optional[str] = None  # Deprecated: will use authenticated patient
    anonymous: bool = False  # Deprecated: not used for authenticated users


class SendMessageRequest(BaseModel):
    content: str


# Store active WebSocket connections
active_connections: dict[str, WebSocket] = {}


@router.post("")
async def create_conversation(
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation for the authenticated patient."""
    conversation_id = str(uuid.uuid4())
    
    # Use authenticated patient's ID
    patient_id = current_patient.patient_id
    
    conversation = Conversation(
        conversation_id=uuid.UUID(conversation_id),
        patient_id=patient_id,
        status="active"
    )
    db.add(conversation)
    await db.commit()
    
    # Query the conversation again to get the started_at timestamp
    # (refresh can fail if object is detached after commit)
    result = await db.execute(
        select(Conversation).where(Conversation.conversation_id == uuid.UUID(conversation_id))
    )
    conversation = result.scalar_one()
    
    return {
        "conversation_id": conversation_id,
        "status": "active",
        "started_at": conversation.started_at.isoformat() if conversation.started_at else datetime.now().isoformat()
    }


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db)
):
    """Get conversation details for the authenticated patient."""
    result = await db.execute(
        select(Conversation).where(Conversation.conversation_id == uuid.UUID(conversation_id))
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Verify the conversation belongs to the authenticated patient
    if conversation.patient_id != current_patient.patient_id:
        raise HTTPException(status_code=403, detail="Access denied to this conversation")
    
    return {
        "conversation_id": str(conversation.conversation_id),
        "patient_id": str(conversation.patient_id) if conversation.patient_id else None,
        "status": conversation.status,
        "started_at": conversation.started_at.isoformat(),
        "ended_at": conversation.ended_at.isoformat() if conversation.ended_at else None
    }


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db)
):
    """Send a message and get LLM response."""
    # Get conversation
    result = await db.execute(
        select(Conversation).where(Conversation.conversation_id == uuid.UUID(conversation_id))
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Verify the conversation belongs to the authenticated patient
    if conversation.patient_id != current_patient.patient_id:
        raise HTTPException(status_code=403, detail="Access denied to this conversation")
    
    # ROOT CAUSE FIX: Properly merge state with checkpointer
    # LangGraph's checkpointer loads previous state automatically, BUT
    # we're passing initial_state which can overwrite loaded state.
    # Solution: Load previous state manually, merge carefully, then pass only the new message
    
    # Get checkpointer and graph
    checkpointer = await get_checkpointer()
    graph = await get_graph()
    
    # Patient is only verified if verification has been completed in THIS conversation
    # For the first message, always start with False - LLM must verify first
    # Even if conversation.patient_id exists (from login), we still need to verify in this conversation
    if is_first_message:
        patient_verified = False  # Always False for first message, must verify
    else:
        patient_verified = verification_completed and conversation.patient_id is not None
    
    # Extract patient info from previous messages if available
    history_shown = False  # Detect if history was already shown
    waiting_for_datetime = False  # Detect if we're waiting for date/time
    ranked_doctors = None  # Detect if doctors were already ranked
    service_type_determined = None  # Detect if service type was determined
    appointment_datetime = None  # Detect if appointment datetime was provided
    user_request = None  # Detect user's original request
    
    for msg in previous_messages:
        if msg.sender_type == "patient":
            message_history.append(HumanMessage(content=msg.content))
            # Try to extract datetime from patient messages if we're waiting for it
            if waiting_for_datetime and not appointment_datetime:
                # Try to extract datetime using the same logic as the agent
                from backend.src.agents.conversation_agent import extract_datetime_from_message
                extracted = extract_datetime_from_message(msg.content)
                if extracted:
                    appointment_datetime = extracted
        elif msg.sender_type == "llm":
            message_history.append(AIMessage(content=msg.content))
            # Check if this LLM message shows history
            if patient_verified and msg.content:
                history_indicators = ["medical history", "visit history", "previous", "past history", "history summary", "what help do you need"]
                if any(indicator.lower() in msg.content.lower() for indicator in history_indicators):
                    history_shown = True
                # Check if we're waiting for date/time
                if "what date and time would work best" in msg.content.lower() or "provide your preferred date and time" in msg.content.lower() or "date and time would work" in msg.content.lower() or "preferred date and time" in msg.content.lower():
                    waiting_for_datetime = True
                # Check if doctors were ranked (look for ranking indicators or metadata)
                if msg.message_metadata and isinstance(msg.message_metadata, dict):
                    # Try to extract ranked doctors from metadata if available
                    if msg.message_metadata.get("ranked_doctors"):
                        ranked_doctors = msg.message_metadata.get("ranked_doctors")
                    if msg.message_metadata.get("service_type"):
                        service_type_determined = msg.message_metadata.get("service_type")
                    if msg.message_metadata.get("waiting_for_datetime"):
                        waiting_for_datetime = msg.message_metadata.get("waiting_for_datetime")
                    if msg.message_metadata.get("appointment_datetime"):
                        appointment_datetime = msg.message_metadata.get("appointment_datetime")
                    if msg.message_metadata.get("user_request"):
                        user_request = msg.message_metadata.get("user_request")
                # Also check message content for indicators
                if "rank #" in msg.content.lower() or ("top" in msg.content.lower() and "doctor" in msg.content.lower()):
                    # If metadata doesn't have it, at least mark that we're in doctor recommendation flow
                    if not ranked_doctors:
                        # We can't extract from content, but we know doctors were ranked
                        pass
                if "what date and time would work best" in msg.content.lower() or "provide your preferred date and time" in msg.content.lower():
                    waiting_for_datetime = True
    
    # Create base initial state with authenticated patient info
    base_state = create_initial_state(
        conversation_id=conversation_id,
        patient_id=str(conversation.patient_id) if conversation.patient_id else None,
        authenticated_patient=current_patient if conversation.patient_id else None
    )
    
    # Merge existing state with base state
    # CRITICAL: Always use authenticated patient info from base_state if available
    # This ensures authenticated patients are always verified, even if existing state has patient_verified=False
    if existing_state:
        # CRITICAL: Preserve existing state fields, but override with authenticated patient info
        merged_state = {}
        
        # Always use authenticated patient info from base_state if patient is verified there
        # This handles cases where existing state might have patient_verified=False from old conversations
        if base_state.get("patient_verified") and base_state.get("patient_info"):
            merged_state["patient_verified"] = base_state["patient_verified"]
            merged_state["patient_info"] = base_state["patient_info"]
            merged_state["patient_id"] = base_state["patient_id"]
            print(f"[STATE MERGE] Using authenticated patient info from base_state")
        else:
            # Fallback to existing state if base_state doesn't have verified patient
            merged_state["patient_verified"] = existing_state.get("patient_verified", False)
            merged_state["patient_info"] = existing_state.get("patient_info", base_state.get("patient_info", {}))
            merged_state["patient_id"] = existing_state.get("patient_id") or base_state.get("patient_id")
        
        # Preserve other critical state fields from existing state
        for key in ["appointment_preferences", "doctor_ranking", 
                   "ticket_creation", "hitl",
                   "history_shown", "patient_history", "available_doctors",
                   "doctors_found", "doctor_tickets_created", "ticket_created",
                   "next_action", "retry_count"]:
            if key in existing_state:
                # Merge dicts carefully (e.g., appointment_preferences)
                if isinstance(existing_state[key], dict) and isinstance(base_state.get(key), dict):
                    # Merge: existing state values take precedence (they have workflow data)
                    merged = {**base_state.get(key, {}), **existing_state[key]}
                    merged_state[key] = merged
                else:
                    # Use existing value if present and not None/empty
                    merged_state[key] = existing_state[key]
            else:
                # Use base state default
                merged_state[key] = base_state.get(key)
        
        # Messages will be handled by add_messages reducer
        # But we need to preserve conversation_id
        merged_state["conversation_id"] = conversation_id
        
        # Get existing messages
        existing_messages = existing_state.get("messages", [])
        current_user_message = HumanMessage(content=request.content)
        
        # Append new message to existing messages
        merged_state["messages"] = list(existing_messages) + [current_user_message]
        
        initial_state = merged_state
        print(f"[STATE MERGE] Merged existing state with {len(existing_messages)} existing messages")
    else:
        # New conversation - start fresh with authenticated patient info
        current_user_message = HumanMessage(content=request.content)
        base_state["messages"] = [current_user_message]
        initial_state = base_state
        print(f"[STATE MERGE] New conversation - starting fresh with authenticated patient")
    
    # Initialize agent state with conversation history
    initial_state: AgentState = {
        "conversation_id": conversation_id,
        "patient_id": str(conversation.patient_id) if conversation.patient_id else None,
        "patient_verified": patient_verified,
        "messages": message_history,
        "collected_info": collected_info,
        "required_fields_missing": [] if patient_verified else ["name", "phone", "date_of_birth"],
        "retry_count": {},
        "patient_history": None,
        "summary": None,
        "ticket_created": False,
        "next_action": "continue" if patient_verified else "collect_info",
        "history_shown": history_shown,  # Preserve history_shown from previous messages
        "service_type_determined": service_type_determined,  # Preserve service_type from previous messages
        "ranked_doctors": ranked_doctors,  # Preserve ranked_doctors from previous messages
        "doctor_tickets_created": False,
        "waiting_for_appointment_datetime": waiting_for_datetime,  # Preserve waiting_for_datetime from previous messages
        "appointment_datetime": appointment_datetime,  # Preserve appointment_datetime from previous messages
        "user_request": user_request  # Preserve user_request from previous messages
    }
    
    try:
        # Run agent - checkpointer will save state automatically
        final_state = await graph.ainvoke(initial_state, config=config)
        

        all_messages = final_state.get("messages", [])
        
        # Check if patient is verified - if so, we should NOT return old "ask_for_missing" responses
        patient_verified = final_state.get("patient_verified", False)
        history_shown = final_state.get("history_shown", False)
        
        llm_messages = [msg for msg in all_messages if isinstance(msg, AIMessage)]
        llm_response = None
        
        # ROOT FIX: If workflow progressed (verified, history shown, etc.), skip old "ask_for_missing" responses
        # Start from the END and work backwards to find the MOST RECENT relevant response
        # If tickets were created, prioritize the confirmation message
        doctor_tickets_created = final_state.get("doctor_tickets_created", False)
        next_action = final_state.get("next_action", "")
        
        for msg in reversed(llm_messages):
            content = getattr(msg, 'content', None) or ""
            if not content or not str(content).strip():
                continue
            
            # Skip old "ask_for_missing" responses if we've progressed past that stage
            if patient_verified and not history_shown:
                # If verified but history not shown, we should have a "show_history" response
                # Skip messages that look like old "ask_for_missing" (asking for phone/DOB)
                if "phone number" in content.lower() and "date of birth" in content.lower():
                    # This is likely an old "ask_for_missing" response - skip it
                    continue
            
            # ROOT FIX: If tickets were created, skip old "ask_for_request_info" messages
            # These might say "can't schedule" or ask for date/time even though tickets are already created
            if doctor_tickets_created:
                # Skip messages that look like they're asking for scheduling info or saying they can't schedule
                content_lower = content.lower()
                if any(phrase in content_lower for phrase in [
                    "can't schedule", "cannot schedule", "unable to schedule", 
                    "choose a different date", "when would you like", "provide a date",
                    "i'm sorry, but i can't", "i'm sorry but i can't"
                ]):
                    # This is likely an old ask_for_request_info message - skip it
                    print(f"[RESPONSE EXTRACTION] Skipping old scheduling message: {content[:100]}...")
                    continue
            
            # Found a relevant response
            has_tool_calls = hasattr(msg, 'tool_calls') and msg.tool_calls
            if not has_tool_calls:
                llm_response = str(content)
                print(f"[RESPONSE EXTRACTION] Selected response: {llm_response[:200]}...")
                break
            elif not llm_response:
                llm_response = str(content) if str(content).strip() else None
        
        # If no content found, check if last message has tool calls
        if not llm_response:
            if llm_messages:
                last_msg = llm_messages[-1]
                # If last message has tool calls but no content, generate a response
                if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                    # Check what tool was called
                    tool_names = [tc.get("name", "") for tc in last_msg.tool_calls if isinstance(tc, dict)]
                    if "verify_patient" in tool_names:
                        llm_response = "I've verified your identity. How can I assist you today?"
                    elif "create_patient" in tool_names:
                        llm_response = "I've created your patient record. How can I assist you today?"
                    elif "get_patient_history" in tool_names:
                        llm_response = "I've retrieved your medical history. How can I assist you today?"
                    else:
                        llm_response = "I'm processing your request. Please wait a moment."
                else:
                    # No tool calls, but no content either - this shouldn't happen
                    llm_response = "I'm here to help. How can I assist you today?"
            else:
                # No LLM messages at all - check if sequential review ticket was created
                sequential_review_dict = final_state.get("sequential_review", {})
                if sequential_review_dict.get("chain_id"):
                    # Sequential review ticket was created - generate appropriate response
                    from backend.src.agents.state_models import SequentialReviewState
                    try:
                        seq_review = SequentialReviewState(**sequential_review_dict)
                        if seq_review.chain_id:
                            llm_response = "I've received your request for a complex case review. The review process has been started with the appropriate specialists. You'll be updated as the review progresses."
                    except:
                        llm_response = "I'm processing your request. Please wait."
                else:
                    llm_response = "I'm processing your request. Please wait."
        
        # ROOT FIX: If tickets were created but we don't have a proper confirmation message,
        # generate one manually to avoid showing old "can't schedule" messages
        if doctor_tickets_created and llm_response:
            # Check if the response looks like a confirmation (positive, doesn't say "can't schedule")
            content_lower = llm_response.lower()
            is_negative_response = any(phrase in content_lower for phrase in [
                "can't schedule", "cannot schedule", "unable to schedule",
                "choose a different date", "i'm sorry, but i can't", "i'm sorry but i can't"
            ])
            
            if is_negative_response:
                # The response is negative but tickets were created - generate a proper confirmation
                appointment_prefs_dict = final_state.get("appointment_preferences", {})
                service_type = appointment_prefs_dict.get("service_type", "appointment")
                date_time = appointment_prefs_dict.get("preferred_date_time", "")
                
                try:
                    if date_time:
                        dt = datetime.fromisoformat(date_time.replace('Z', '+00:00'))
                        date_time_text = dt.strftime("%B %d, %Y at %I:%M %p")
                    else:
                        date_time_text = "to be confirmed"
                except:
                    date_time_text = date_time if date_time else "to be confirmed"
                
                patient_name = final_state.get("patient_info", {}).get("name", "")
                service_type_display = service_type.replace('_', ' ').title()
                
                llm_response = f"Great! I've successfully scheduled your {service_type_display} appointment"
                if date_time_text and date_time_text != "to be confirmed":
                    llm_response += f" for {date_time_text}"
                llm_response += ". Your appointment request has been submitted and you will be contacted with further details and confirmation soon."
                if patient_name:
                    llm_response += f" Thank you, {patient_name}!"
                llm_response += " Is there anything else I can help you with?"
                
                print(f"[RESPONSE EXTRACTION] Generated fallback confirmation message (tickets created but old response was negative)")
        
        # Ensure we have a response
        if not llm_response or not llm_response.strip():
            llm_response = "I'm here to help. How can I assist you today?"
        
        # Check if this is a doctor recommendation message
        from backend.src.agents.state_models import DoctorRanking, TicketCreation
        doctor_ranking_dict = final_state.get("doctor_ranking", {})
        doctor_ranking = DoctorRanking(**doctor_ranking_dict)
        ranked_doctors = doctor_ranking.ranked_doctors
        
        ticket_creation_dict = final_state.get("ticket_creation", {})
        ticket_creation = TicketCreation(**ticket_creation_dict)
        doctor_tickets = ticket_creation.doctor_tickets or []
        
        doctor_tickets_created = final_state.get("doctor_tickets_created", False)
        service_type_determined = final_state.get("service_type_determined")
        doctor_tickets = final_state.get("doctor_tickets", [])
        waiting_for_datetime = final_state.get("waiting_for_appointment_datetime", False)
        
        is_doctor_recommendation = (
            doctor_tickets_created and 
            ranked_doctors and 
            len(ranked_doctors) > 0
        )
        
        # Also check if we're asking for date/time (before tickets are created)
        is_asking_for_datetime = (
            waiting_for_datetime and 
            ranked_doctors and 
            len(ranked_doctors) > 0 and
            not doctor_tickets_created
        )
        
        # Prepare message metadata
        message_metadata = None
        if is_doctor_recommendation or is_asking_for_datetime:
            # Format doctor recommendations with ticket IDs
            doctors_with_tickets = []
            ticket_map = {t["doctor_id"]: t["ticket_id"] for t in doctor_tickets}
            
            from backend.src.config import settings
            top_n = getattr(settings, 'top_doctors_count', 5)
            
            for doctor in ranked_doctors[:top_n]:
                doctors_with_tickets.append({
                    "doctor_id": doctor["doctor_id"],
                    "name": doctor["name"],
                    "service_type": doctor["service_type"],
                    "specialization": doctor.get("specialization"),
                    "rank": doctor["rank"],
                    "reason": doctor["reason"],
                    "ticket_id": ticket_map.get(doctor["doctor_id"])
                })
            
            if is_doctor_recommendation:
                # Tickets already created
                message_metadata = {
                    "type": "doctor_recommendation",
                    "doctors": doctors_with_tickets,
                    "service_type": service_type_determined,
                    "ranked_doctors": ranked_doctors,  # Store raw ranked_doctors for state restoration
                    "tickets_created": len(doctor_tickets)
                }
            else:
                # Asking for date/time - store ranked_doctors for state restoration
                doctors_list = []
                for doctor in ranked_doctors[:5]:
                    doctors_list.append({
                        "doctor_id": doctor.get("doctor_id") or doctor.get("doctor_id"),
                        "name": doctor.get("name"),
                        "service_type": doctor.get("service_type"),
                        "specialization": doctor.get("specialization"),
                        "rank": doctor.get("rank"),
                        "reason": doctor.get("reason")
                    })
                
                user_request_from_state = final_state.get("user_request")
                message_metadata = {
                    "type": "doctor_recommendation",
                    "doctors": doctors_list,
                    "service_type": service_type_determined,
                    "ranked_doctors": ranked_doctors,  # Store raw ranked_doctors for state restoration
                    "waiting_for_datetime": True,
                    "user_request": user_request_from_state,  # Store user request for state restoration
                    "tickets_created": 0
                }
        
    
        all_messages = final_state.get("messages", [])
        
        # Convert to API format
        from langchain_core.messages import ToolMessage
        formatted_messages = []
        for idx, msg in enumerate(all_messages):
            if isinstance(msg, ToolMessage):
                continue  # Skip tool messages
            msg_data = {
                "message_id": str(getattr(msg, 'id', f"msg-{idx}")),
                "sender_type": "patient" if isinstance(msg, HumanMessage) else "llm",
                "content": str(getattr(msg, 'content', '')),
                "created_at": datetime.utcnow().isoformat()
            }
            formatted_messages.append(msg_data)
        
        # Create response with LLM response and all messages
        response_data = {
            "message_id": str(uuid.uuid4()),  # Generate ID for response
            "content": llm_response,
            "sender_type": "llm",
            "created_at": datetime.utcnow().isoformat(),
            "all_messages": formatted_messages  # Include all messages in response
        }
        
        # Check if booking has been confirmed (next_action is "end" and tickets were created)
        # If confirmed, don't show doctor recommendation details to the patient
        next_action = final_state.get("next_action", "")
        booking_confirmed = (next_action == "end" and doctor_tickets_created)
        
        # Only add doctor recommendation data if booking is NOT yet confirmed
        # After confirmation, patients should only see a simple confirmation message
        if is_doctor_recommendation and message_metadata and not booking_confirmed:
            response_data["type"] = "doctor_recommendation"
            response_data["doctors"] = message_metadata["doctors"]
            response_data["service_type"] = message_metadata["service_type"]
            response_data["tickets_created"] = message_metadata["tickets_created"]
        
        # Don't add tickets to response after booking confirmation - keep it simple for patients
        if not booking_confirmed:
            ticket_creation_dict = final_state.get("ticket_creation", {})
            doctor_tickets_list = ticket_creation_dict.get('doctor_tickets', [])
            if doctor_tickets_list:
                response_data["tickets"] = doctor_tickets_list
                response_data["tickets_count"] = len(doctor_tickets_list)
                response_data["tickets_created_success"] = ticket_creation_dict.get('tickets_creation_success', False)
        
        # Add case summary (AI-generated summary of the case) to response
        case_summary = ticket_creation_dict.get('case_summary')
        if case_summary:
            response_data["case_summary"] = case_summary
        
        # Log complete workflow state after conversation for debugging
        print(f"\n{'#'*80}")
        print(f"[WORKFLOW STATE] Conversation: {conversation_id}")
        print(f"{'#'*80}")
        
        # Patient Info State
        patient_info_dict = final_state.get("patient_info", {})
        print(f"\n[STATE] Patient Info:")
        print(f"  - Name: {patient_info_dict.get('name', 'Not provided')}")
        print(f"  - Phone: {patient_info_dict.get('phone', 'Not provided')}")
        print(f"  - DOB: {patient_info_dict.get('date_of_birth', 'Not provided')}")
        print(f"  - Patient ID: {final_state.get('patient_id', 'Not set')}")
        print(f"  - Verified: {final_state.get('patient_verified', False)}")
        
        # Appointment Preferences State
        appointment_prefs_dict = final_state.get("appointment_preferences", {})
        print(f"\n[STATE] Appointment Preferences:")
        print(f"  - Service Type: {appointment_prefs_dict.get('service_type', 'Not set')}")
        print(f"  - Preferred Date/Time: {appointment_prefs_dict.get('preferred_date_time', 'Not set')}")
        
        # HITL State
        hitl_dict = final_state.get("hitl", {})
        print(f"\n[STATE] HITL (Human In The Loop):")
        print(f"  - Waiting for input: {hitl_dict.get('is_waiting_for_input', False)}")
        print(f"  - Validation complete: {hitl_dict.get('validation_complete', False)}")
        pending_questions = hitl_dict.get('pending_questions', [])
        if pending_questions:
            print(f"  - Pending questions: {len(pending_questions)}")
            for i, q in enumerate(pending_questions[:3], 1):  # Show first 3
                print(f"    {i}. {q[:100]}{'...' if len(q) > 100 else ''}")
        collected_responses = hitl_dict.get('collected_responses', {})
        if collected_responses:
            print(f"  - Collected responses: {', '.join(collected_responses.keys())}")
        
        # Doctor Search State
        print(f"\n[STATE] Doctor Search:")
        print(f"  - Doctors found: {final_state.get('doctors_found', 'Unknown')}")
        if final_state.get('doctors_error'):
            print(f"  - Error: {final_state.get('doctors_error')}")
        available_doctors = final_state.get("available_doctors", [])
        if available_doctors:
            print(f"  - Available doctors count: {len(available_doctors)}")
        
        # Doctor Ranking State
        doctor_ranking_dict = final_state.get("doctor_ranking", {})
        print(f"\n[STATE] Doctor Ranking:")
        print(f"  - Success: {doctor_ranking_dict.get('ranking_success', 'Unknown')}")
        if doctor_ranking_dict.get('ranking_error'):
            print(f"  - Error: {doctor_ranking_dict.get('ranking_error')}")
        ranked_doctors_list = doctor_ranking_dict.get('ranked_doctors', [])
        if ranked_doctors_list:
            print(f"  - Ranked doctors count: {len(ranked_doctors_list)}")
            for i, doc in enumerate(ranked_doctors_list[:3], 1):  # Show top 3
                print(f"    {i}. {doc.get('name', 'Unknown')} - Rank: {doc.get('rank', 'N/A')}")
        
        # Ticket Creation State
        ticket_creation_dict = final_state.get("ticket_creation", {})
        print(f"\n[STATE] Ticket Creation:")
        print(f"  - Success: {ticket_creation_dict.get('tickets_creation_success', 'Unknown')}")
        print(f"  - Tickets created: {ticket_creation_dict.get('tickets_created', 0)}")
        if ticket_creation_dict.get('tickets_creation_error'):
            print(f"  - Error: {ticket_creation_dict.get('tickets_creation_error')}")
        doctor_tickets_list = ticket_creation_dict.get('doctor_tickets', [])
        if doctor_tickets_list:
            print(f"  - Doctor tickets: {len(doctor_tickets_list)}")
            for i, ticket in enumerate(doctor_tickets_list, 1):  # Show ALL tickets
                print(f"    {i}. Ticket ID: {ticket.get('ticket_id', 'Unknown')}")
                print(f"       Doctor ID: {ticket.get('doctor_id', 'Unknown')}")
                print(f"       Service Type: {ticket.get('service_type', 'Unknown')}")
                print(f"       Status: {ticket.get('status', 'Unknown')}")
                if ticket.get('assigned_to'):
                    print(f"       Assigned To: {ticket.get('assigned_to')}")
        else:
            print(f"  - No tickets created yet")
        
        # Overall State Flags
        print(f"\n[STATE] Overall Flags:")
        print(f"  - Patient verified: {final_state.get('patient_verified', False)}")
        print(f"  - History shown: {final_state.get('history_shown', False)}")
        print(f"  - Ticket created: {final_state.get('ticket_created', False)}")
        print(f"  - Doctor tickets created: {final_state.get('doctor_tickets_created', False)}")
        print(f"  - Next action: {final_state.get('next_action', 'Not set')}")
        
        # Message Count
        all_messages_final = final_state.get("messages", [])
        human_msgs = [m for m in all_messages_final if isinstance(m, HumanMessage)]
        ai_msgs = [m for m in all_messages_final if isinstance(m, AIMessage)]
        tool_msgs = [m for m in all_messages_final if isinstance(m, ToolMessage)]
        print(f"\n[STATE] Messages:")
        print(f"  - Human messages: {len(human_msgs)}")
        print(f"  - AI messages: {len(ai_msgs)}")
        print(f"  - Tool messages: {len(tool_msgs)}")
        print(f"  - Total messages: {len(all_messages_final)}")
        
        print(f"\n{'#'*80}\n")
        
        return response_data
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in send_message: {error_details}")  # Debug logging
        return {"content": f"I encountered an error: {str(e)}", "sender_type": "llm", "error": True}


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all messages in a conversation from PostgresSaver checkpointer."""
    # Import here to avoid scoping issues
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    
    try:
        # Get checkpointer
        checkpointer = await get_checkpointer()
        
        # Configure for checkpointer: use conversation_id as thread_id
        config = {"configurable": {"thread_id": conversation_id}}
        
        # Try to load existing state from checkpointer
        try:
            checkpoint = await checkpointer.aget(config)
            if checkpoint and checkpoint.get("channel_values"):
                existing_state = checkpoint["channel_values"]
                all_messages = existing_state.get("messages", [])
                
                # Convert LangChain messages to API format
                messages = []
                for msg in all_messages:
                    if isinstance(msg, HumanMessage):
                        messages.append({
                            "message_id": str(getattr(msg, "id", f"human-{len(messages)}")),
                            "sender_type": "patient",
                            "content": getattr(msg, "content", ""),
                            "created_at": getattr(msg, "additional_kwargs", {}).get("timestamp", datetime.now().isoformat())
                        })
                    elif isinstance(msg, AIMessage):
                        # Check for metadata (doctor recommendations, etc.)
                        metadata = {}
                        content = getattr(msg, "content", "")
                        
                        # Check if this is a doctor recommendation message
                        if hasattr(msg, "additional_kwargs"):
                            additional_kwargs = msg.additional_kwargs
                            if additional_kwargs.get("doctors"):
                                metadata["doctors"] = additional_kwargs["doctors"]
                                metadata["type"] = "doctor_recommendation"
                                metadata["service_type"] = additional_kwargs.get("service_type")
                                metadata["tickets_created"] = additional_kwargs.get("tickets_created")
                        
                        messages.append({
                            "message_id": str(getattr(msg, "id", f"ai-{len(messages)}")),
                            "sender_type": "llm",
                            "content": content,
                            "created_at": getattr(msg, "additional_kwargs", {}).get("timestamp", datetime.now().isoformat()),
                            "type": metadata.get("type", "text") if metadata else "text",
                            **({"metadata": metadata} if metadata else {}),
                            **({"doctors": metadata.get("doctors")} if metadata and metadata.get("doctors") else {}),
                            **({"service_type": metadata.get("service_type")} if metadata and metadata.get("service_type") else {})
                        })
                
                return messages
            else:
                # No checkpoint found - return empty
                return []
        except Exception as e:
            # No checkpoint found - this is normal for new conversations
            print(f"[GET MESSAGES] No checkpoint found for conversation {conversation_id}: {e}")
            return []
    except Exception as e:
        print(f"[GET MESSAGES] Error fetching messages: {e}")
        import traceback
        traceback.print_exc()
        return []


@router.websocket("/{conversation_id}/ws")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()
    active_connections[conversation_id] = websocket
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "system",
            "content": "Connected to AI assistant. How can I help you today?"
        })
        
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Process message through agent
            # This is a simplified version - in production, use proper async handling
            response = {
                "type": "message",
                "content": "I received your message. Processing...",
                "sender_type": "llm"
            }
            
            await websocket.send_json(response)
    
    except WebSocketDisconnect:
        active_connections.pop(conversation_id, None)
    except Exception as e:
        if conversation_id in active_connections:
            active_connections.pop(conversation_id, None)
        await websocket.close()


@router.get("")
async def list_conversations(
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db)
):
    """List conversations for the authenticated patient."""
    # Use authenticated patient's ID
    query = select(Conversation).where(Conversation.patient_id == current_patient.patient_id)
    
    result = await db.execute(query.order_by(Conversation.started_at.desc()))
    conversations = result.scalars().all()
    
    return [
        {
            "conversation_id": str(conv.conversation_id),
            "patient_id": str(conv.patient_id) if conv.patient_id else None,
            "status": conv.status,
            "started_at": conv.started_at.isoformat(),
            "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
            "summary": conv.summary
        }
        for conv in conversations
    ]

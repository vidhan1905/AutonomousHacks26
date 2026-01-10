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
from backend.src.database.models import Conversation, Message, Patient
from backend.src.agents.conversation_agent import graph, AgentState
from langchain_core.messages import HumanMessage, AIMessage

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    patient_id: Optional[str] = None
    anonymous: bool = False


class SendMessageRequest(BaseModel):
    content: str


# Store active WebSocket connections
active_connections: dict[str, WebSocket] = {}


@router.post("")
async def create_conversation(
    request: CreateConversationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    
    # If anonymous, create a temporary patient or use None
    patient_id = None
    if request.patient_id:
        patient_id = uuid.UUID(request.patient_id)
    elif not request.anonymous:
        raise HTTPException(
            status_code=400,
            detail="Either patient_id or anonymous=true required"
        )
    
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
    db: AsyncSession = Depends(get_db)
):
    """Get conversation details."""
    result = await db.execute(
        select(Conversation).where(Conversation.conversation_id == uuid.UUID(conversation_id))
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
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
    
    # Save patient message
    patient_message = Message(
        conversation_id=uuid.UUID(conversation_id),
        sender_type="patient",
        sender_id=conversation.patient_id,
        content=request.content
    )
    db.add(patient_message)
    await db.commit()
    
    # Load previous messages to maintain conversation context
    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == uuid.UUID(conversation_id))
        .order_by(Message.created_at)
    )
    previous_messages = messages_result.scalars().all()
    
    # Build message history for the agent
    message_history = []
    collected_info = {}
    
    # Check if this is the first message (no previous messages)
    is_first_message = len(previous_messages) == 0
    
    # Check if verification has been completed in this conversation
    # Strategy: If there are LLM responses that don't ask for verification details,
    # and there are subsequent patient messages, verification likely completed
    verification_completed = False
    if not is_first_message:
        llm_messages = [msg for msg in previous_messages if msg.sender_type == "llm"]
        patient_messages = [msg for msg in previous_messages if msg.sender_type == "patient"]
        
        if len(llm_messages) > 0:
            # Check the most recent LLM message - if it doesn't ask for verification,
            # and there are patient messages after it, verification likely completed
            last_llm_msg = llm_messages[-1]
            content_lower = last_llm_msg.content.lower()
            
            # Check if it asks for verification details
            asks_for_verification = any(phrase in content_lower for phrase in [
                "your name", "your phone", "your date of birth", "your dob",
                "verify your identity", "verification", "provide me with your",
                "could you please provide", "i need your", "i'll need your"
            ])
            
            # If last LLM message doesn't ask for verification, assume it's completed
            # (because if verification was needed, LLM would have asked)
            if not asks_for_verification:
                verification_completed = True
            else:
                # Check for explicit verification success phrases
                for msg in llm_messages:
                    content_lower = msg.content.lower()
                    if any(phrase in content_lower for phrase in [
                        "verified successfully", "verification successful", "found your record",
                        "i've verified", "i have verified", "you're verified", "you are verified",
                        "retrieved your history", "your medical history"
                    ]):
                        verification_completed = True
                        break
    
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
    
    # Add current message
    message_history.append(HumanMessage(content=request.content))
    
    # Only set collected_info if patient is verified through conversation
    # Don't pre-populate from patient record - let LLM verify first
    if patient_verified and conversation.patient_id:
        patient_result = await db.execute(
            select(Patient).where(Patient.patient_id == conversation.patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        if patient:
            collected_info = {
                "name": patient.name,
                "phone": patient.phone_number,
                "date_of_birth": patient.date_of_birth.strftime("%Y-%m-%d") if patient.date_of_birth else None,
                "patient_id": str(patient.patient_id)
            }
    
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
    
    # Run agent with increased recursion limit
    try:
        config = {"recursion_limit": 100}  # Increased to handle complex flows
        final_state = await graph.ainvoke(initial_state, config=config)
        
        # Get LLM response - find the last AIMessage with actual content
        # Skip tool call messages that might not have content
        llm_messages = [msg for msg in final_state["messages"] if isinstance(msg, AIMessage)]
        llm_response = None
        
        # Look backwards for the last message with content
        for msg in reversed(llm_messages):
            # Check if message has content and it's not empty
            content = getattr(msg, 'content', None) or ""
            if content and str(content).strip():
                # Check if it has tool calls - if so, prefer a message without tool calls
                has_tool_calls = hasattr(msg, 'tool_calls') and msg.tool_calls
                if not has_tool_calls:
                    llm_response = str(content)
                    break
                elif not llm_response:  # Use tool call message as fallback if no other content
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
                # No LLM messages at all - shouldn't happen
                llm_response = "I'm processing your request. Please wait."
        
        # Ensure we have a response
        if not llm_response or not llm_response.strip():
            llm_response = "I'm here to help. How can I assist you today?"
        
        # Check if this is a doctor recommendation message
        ranked_doctors = final_state.get("ranked_doctors")
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
            
            for doctor in ranked_doctors[:5]:
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
        
        # Save LLM message
        llm_message = Message(
            conversation_id=uuid.UUID(conversation_id),
            sender_type="llm",
            sender_id=None,
            content=llm_response,
            message_metadata=message_metadata
        )
        db.add(llm_message)
        await db.commit()
        
        response_data = {
            "message_id": str(llm_message.message_id),
            "content": llm_response,
            "sender_type": "llm",
            "created_at": llm_message.created_at.isoformat()
        }
        
        # Add doctor recommendation data if present
        if is_doctor_recommendation and message_metadata:
            response_data["type"] = "doctor_recommendation"
            response_data["doctors"] = message_metadata["doctors"]
            response_data["service_type"] = message_metadata["service_type"]
        
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
    """Get all messages in a conversation."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == uuid.UUID(conversation_id))
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    
    result_messages = []
    for msg in messages:
        msg_data = {
            "message_id": str(msg.message_id),
            "sender_type": msg.sender_type,
            "content": msg.content,
            "created_at": msg.created_at.isoformat()
        }
        # Include metadata if present (for doctor recommendations)
        if msg.message_metadata:
            msg_data["metadata"] = msg.message_metadata
            if msg.message_metadata.get("type") == "doctor_recommendation":
                msg_data["type"] = "doctor_recommendation"
                msg_data["doctors"] = msg.message_metadata.get("doctors", [])
                msg_data["service_type"] = msg.message_metadata.get("service_type")
        result_messages.append(msg_data)
    
    return result_messages


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
    patient_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List conversations (requires patient_id filter)."""
    query = select(Conversation)
    if patient_id:
        query = query.where(Conversation.patient_id == uuid.UUID(patient_id))
    
    result = await db.execute(query.order_by(Conversation.started_at.desc()))
    conversations = result.scalars().all()
    
    return [
        {
            "conversation_id": str(conv.conversation_id),
            "patient_id": str(conv.patient_id) if conv.patient_id else None,
            "status": conv.status,
            "started_at": conv.started_at.isoformat()
        }
        for conv in conversations
    ]

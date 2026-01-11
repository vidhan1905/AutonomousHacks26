"""LangGraph tools for complex case detection and sequential multi-doctor review."""
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.src.database.models import (
    SequentialReviewChain, SequentialReviewStep, ServicePerson, Ticket, Conversation, Patient
)
from backend.src.database.connection import async_session_maker
from backend.src.agents.tools.doctor_tools import get_available_service_types, get_available_doctors_by_type_and_time
import uuid
import asyncio
import concurrent.futures
import json
from backend.src.config import settings
from datetime import datetime

# Initialize LLM
llm = ChatOpenAI(
    model=settings.openai_model,
    temperature=settings.openai_temperature,
    max_tokens=settings.openai_max_tokens,
    api_key=settings.openai_api_key,
)


def run_async_safely(async_func, *args, session_maker_param=False, **kwargs):
    """Run an async function safely from a sync context using a thread pool."""
    def run_in_thread():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            from backend.src.database.connection import create_async_session_maker
            if session_maker_param:
                fresh_session_maker = create_async_session_maker()
                kwargs['session_maker'] = fresh_session_maker
            return new_loop.run_until_complete(async_func(*args, **kwargs))
        finally:
            new_loop.close()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        return future.result(timeout=30)


@tool
def detect_complex_case(
    patient_history: Optional[Dict[str, Any]],
    user_query: str,
    current_symptoms: Optional[List[str]] = None
) -> dict:
    """Detect if a case requires sequential multi-doctor review.
    
    Analyzes the patient query and history to determine if multiple service types
    are needed (complex case) or if a single service type is sufficient (normal case).
    
    Args:
        patient_history: Patient's medical history (dict with keys like 'history_records', 'summary', etc.)
        user_query: User's current query/request
        current_symptoms: List of current symptoms (optional)
    
    Returns:
        Dictionary with:
        - is_complex: bool - Whether case requires sequential review
        - complexity_score: float (0-100) - Complexity score
        - complexity_reason: str - Reason why case is complex
        - suggested_doctors_count: int - Number of doctors needed (2-4)
        - suggested_service_types: List[str] - List of service types needed (e.g., ["cardiology", "endocrinology", "neurology"])
    """
    try:
        # Fetch available service types from database
        available_service_types = get_available_service_types()
        
        if not available_service_types:
            return {
                "status": "error",
                "error": "No service types available in database",
                "is_complex": False
            }
        
        # Prepare context for LLM
        history_text = ""
        if patient_history:
            if isinstance(patient_history, dict):
                history_text = json.dumps(patient_history, indent=2)
            else:
                history_text = str(patient_history)
        
        symptoms_text = ", ".join(current_symptoms) if current_symptoms else "Not specified"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a medical case analysis AI. Analyze the patient's query and history to determine if this case requires sequential multi-doctor review (complex case) or can be handled by a single service type (normal case).

Available service types in the system: {available_service_types}

A complex case requires sequential multi-doctor review if:
1. The case involves multiple symptoms/conditions that span different medical specialties
2. The case requires coordination between multiple specialists (e.g., pre-surgical clearance, multi-symptom diagnosis)
3. The case involves complex conditions that need multiple perspectives

A normal case can be handled by a single service type if:
1. The case involves a single symptom/condition
2. The case fits clearly into one medical specialty
3. No coordination between multiple specialists is needed

Respond with a JSON object containing:
- is_complex: boolean (true if multiple service types needed, false if single service type sufficient)
- complexity_score: number (0-100, where 0=simple, 100=very complex)
- complexity_reason: string (explanation of why case is complex or normal)
- suggested_doctors_count: number (2-4 if complex, 1 if normal)
- suggested_service_types: array of strings (list of service types needed, e.g., ["cardiology", "endocrinology"])

If complex, list the service types in order of priority (which specialist should review first, second, etc.)."""),
            ("human", """Patient Query: {user_query}

Current Symptoms: {symptoms_text}

Patient History:
{history_text}

Analyze this case and determine if it requires sequential multi-doctor review."""),
        ])
        
        chain = prompt | llm
        response = chain.invoke({
            "available_service_types": ", ".join(available_service_types),
            "user_query": user_query,
            "symptoms_text": symptoms_text,
            "history_text": history_text[:2000] if history_text else "No history available"
        })
        
        # Parse LLM response
        response_text = response.content.strip()
        
        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            # Fallback: try to parse as JSON directly
            result = json.loads(response_text)
        
        # Validate and return
        is_complex = result.get("is_complex", False)
        complexity_score = float(result.get("complexity_score", 0))
        complexity_reason = result.get("complexity_reason", "")
        suggested_doctors_count = int(result.get("suggested_doctors_count", 1))
        suggested_service_types = result.get("suggested_service_types", [])
        
        # Validate service types exist
        validated_service_types = [st for st in suggested_service_types if st in available_service_types]
        
        if is_complex and not validated_service_types:
            # If LLM suggested service types that don't exist, mark as normal
            is_complex = False
            complexity_reason = f"Suggested service types not available. Original reason: {complexity_reason}"
        
        return {
            "status": "success",
            "is_complex": is_complex,
            "complexity_score": complexity_score,
            "complexity_reason": complexity_reason,
            "suggested_doctors_count": suggested_doctors_count if is_complex else 1,
            "suggested_service_types": validated_service_types if is_complex else []
        }
        
    except Exception as e:
        import traceback
        error_msg = f"Error detecting complex case: {str(e)}\n{traceback.format_exc()}"
        print(f"[ERROR] {error_msg}")
        return {
            "status": "error",
            "error": error_msg,
            "is_complex": False,
            "complexity_score": 0,
            "complexity_reason": f"Error during analysis: {str(e)}",
            "suggested_doctors_count": 1,
            "suggested_service_types": []
        }


async def _create_sequential_review_chain_async(
    patient_id: str,
    conversation_id: str,
    required_doctors_count: int,
    complexity_reason: str,
    user_query: str,
    patient_history: Optional[Dict[str, Any]],
    suggested_service_types: List[str],
    session_maker=None
) -> dict:
    """Create sequential review chain and steps.
    
    For each service type, finds available doctors and selects one.
    Creates SequentialReviewChain and SequentialReviewStep records.
    """
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            # Validate patient and conversation exist
            patient_result = await session.execute(
                select(Patient).where(Patient.patient_id == uuid.UUID(patient_id))
            )
            patient = patient_result.scalar_one_or_none()
            if not patient:
                return {"status": "error", "error": f"Patient {patient_id} not found"}
            
            conversation_result = await session.execute(
                select(Conversation).where(Conversation.conversation_id == uuid.UUID(conversation_id))
            )
            conversation = conversation_result.scalar_one_or_none()
            if not conversation:
                return {"status": "error", "error": f"Conversation {conversation_id} not found"}
            
            # Use LLM to determine doctor selection and order
            # For each service type, find available doctors and select one
            review_steps_data = []
            
            for idx, service_type in enumerate(suggested_service_types):
                # Get available doctors for this service type
                doctors_result = get_available_doctors_by_type_and_time.invoke({
                    "service_type": service_type,
                    "preferred_date_time": None  # No specific time preference
                })
                
                if doctors_result.get("status") != "success" or not doctors_result.get("doctors"):
                    return {
                        "status": "error",
                        "error": f"No available doctors found for service type: {service_type}"
                    }
                
                doctors = doctors_result.get("doctors", [])
                if not doctors:
                    return {
                        "status": "error",
                        "error": f"No available doctors found for service type: {service_type}"
                    }
                
                # Select first available doctor (can be enhanced with ranking later)
                selected_doctor = doctors[0]
                
                review_steps_data.append({
                    "step_index": idx,
                    "service_type": service_type,
                    "doctor_id": selected_doctor["doctor_id"],
                    "doctor_name": selected_doctor["name"],
                    "specialization": selected_doctor.get("specialization", "")
                })
            
            # Create SequentialReviewChain
            chain = SequentialReviewChain(
                conversation_id=uuid.UUID(conversation_id),
                patient_id=uuid.UUID(patient_id),
                case_complexity_score=int(100),  # Store as integer (0-100 scale)
                complexity_reason=complexity_reason,
                required_doctors_count=required_doctors_count,
                current_step_index=0,
                status="pending"
            )
            session.add(chain)
            await session.flush()  # Get chain_id
            
            # Create SequentialReviewStep records
            review_steps = []
            steps_list = []  # Store step objects with their data for ticket creation
            for step_data in review_steps_data:
                step = SequentialReviewStep(
                    chain_id=chain.chain_id,
                    step_index=step_data["step_index"],
                    doctor_id=uuid.UUID(step_data["doctor_id"]),
                    status="pending"
                )
                session.add(step)
                steps_list.append((step, step_data))  # Store both step and step_data
                review_steps.append({
                    "step_id": str(step.step_id),
                    "step_index": step_data["step_index"],
                    "doctor_id": step_data["doctor_id"],
                    "doctor_name": step_data["doctor_name"],
                    "service_type": step_data["service_type"],
                    "specialization": step_data["specialization"]
                })
            
            await session.flush()  # Flush to get step_ids
            
            # Create SequentialReviewTicket for each step
            from backend.src.database.models import SequentialReviewTicket
            from backend.src.database.models import ServicePerson
            
            # Get patient info for ticket description
            patient_name = patient.name if patient.name else "Unknown"
            patient_phone = patient.phone_number if patient.phone_number else ""
            patient_dob = str(patient.date_of_birth) if patient.date_of_birth else ""
            
            # Build base description from user query
            base_description = f"CURRENT CASE:\n{user_query}\n\n"
            base_description += f"Sequential Review - Step {{step_num}} of {len(steps_list)}"
            
            # Build patient details
            patient_details = {
                "name": patient_name,
                "phone": patient_phone,
                "date_of_birth": patient_dob,
            }
            
            # Build past history summary
            past_history_summary = ""
            if patient_history and isinstance(patient_history, dict):
                if patient_history.get("summary"):
                    past_history_summary = patient_history["summary"]
                elif patient_history.get("history_records"):
                    past_history_summary = f"Patient has {len(patient_history['history_records'])} previous medical records."
            
            # Create tickets for all steps
            for idx, (step, step_data) in enumerate(steps_list):
                # Get doctor info for LLM summary
                doctor_result = await session.execute(
                    select(ServicePerson).where(ServicePerson.service_person_id == step.doctor_id)
                )
                doctor = doctor_result.scalar_one_or_none()
                doctor_name = doctor.name if doctor else step_data["doctor_name"]
                service_type = step_data["service_type"]
                
                # Build description for this step
                description = base_description.format(step_num=idx + 1)
                if idx > 0:
                    description = "PREVIOUS DOCTORS' REVIEWS:\nNo previous reviews yet.\n\n" + description
                
                # Build LLM summary
                llm_summary = f"Sequential Review Chain - Step {idx + 1} of {len(steps_list)}\n"
                llm_summary += f"Doctor: {doctor_name} ({service_type})\n"
                
                # Create ticket - only first step can start
                ticket = SequentialReviewTicket(
                    chain_id=chain.chain_id,
                    conversation_id=uuid.UUID(conversation_id),
                    patient_id=uuid.UUID(patient_id),
                    step_id=step.step_id,
                    step_index=step.step_index,
                    can_start=(idx == 0),  # Only first step can start
                    description=description,
                    llm_summary=llm_summary,
                    patient_details=patient_details,
                    past_history_summary=past_history_summary,
                    status="step_pending"
                )
                session.add(ticket)
            
            await session.commit()
            await session.refresh(chain)
            
            return {
                "status": "success",
                "chain_id": str(chain.chain_id),
                "review_steps": review_steps
            }
            
        except Exception as e:
            await session.rollback()
            import traceback
            error_msg = f"Error creating sequential review chain: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            return {"status": "error", "error": error_msg}


@tool
def create_sequential_review_chain(
    patient_id: str,
    conversation_id: str,
    required_doctors_count: int,
    complexity_reason: str,
    user_query: str,
    patient_history: Optional[Dict[str, Any]],
    suggested_service_types: List[str]
) -> dict:
    """Create sequential review chain with steps for each doctor.
    
    Args:
        patient_id: Patient UUID
        conversation_id: Conversation UUID
        required_doctors_count: Number of doctors needed (2-4)
        complexity_reason: Reason why case is complex
        user_query: Original user query
        patient_history: Patient history dict
        suggested_service_types: List of service types in order (e.g., ["cardiology", "endocrinology", "neurology"])
    
    Returns:
        Dictionary with chain_id and review_steps (list of steps with doctor info)
    """
    try:
        return run_async_safely(
            _create_sequential_review_chain_async,
            patient_id,
            conversation_id,
            required_doctors_count,
            complexity_reason,
            user_query,
            patient_history,
            suggested_service_types,
            session_maker_param=True
        )
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": f"Exception in create_sequential_review_chain: {str(e)}\n{traceback.format_exc()}"
        }


async def _get_next_doctor_in_chain_async(
    chain_id: str,
    session_maker=None
) -> dict:
    """Get next doctor in chain with accumulated context."""
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            # Get chain
            chain_result = await session.execute(
                select(SequentialReviewChain).where(SequentialReviewChain.chain_id == uuid.UUID(chain_id))
            )
            chain = chain_result.scalar_one_or_none()
            if not chain:
                return {"status": "error", "error": f"Chain {chain_id} not found"}
            
            # Get current step
            step_result = await session.execute(
                select(SequentialReviewStep).where(
                    SequentialReviewStep.chain_id == uuid.UUID(chain_id),
                    SequentialReviewStep.step_index == chain.current_step_index
                )
            )
            step = step_result.scalar_one_or_none()
            if not step:
                return {"status": "error", "error": f"Step {chain.current_step_index} not found for chain {chain_id}"}
            
            # Get doctor info
            doctor_result = await session.execute(
                select(ServicePerson).where(ServicePerson.service_person_id == step.doctor_id)
            )
            doctor = doctor_result.scalar_one_or_none()
            if not doctor:
                return {"status": "error", "error": f"Doctor {step.doctor_id} not found"}
            
            # Build accumulated context from previous completed steps
            print(f"[TOOLS] Building accumulated context for chain {chain_id}, current_step_index: {chain.current_step_index}")
            previous_steps_result = await session.execute(
                select(SequentialReviewStep).where(
                    SequentialReviewStep.chain_id == uuid.UUID(chain_id),
                    SequentialReviewStep.step_index < chain.current_step_index,
                    SequentialReviewStep.status == "completed"
                ).order_by(SequentialReviewStep.step_index)
            )
            previous_steps = previous_steps_result.scalars().all()
            print(f"[TOOLS] Found {len(previous_steps)} previous completed steps")
            
            accumulated_context_parts = []
            for prev_step in previous_steps:
                prev_doctor_result = await session.execute(
                    select(ServicePerson).where(ServicePerson.service_person_id == prev_step.doctor_id)
                )
                prev_doctor = prev_doctor_result.scalar_one_or_none()
                doctor_name = prev_doctor.name if prev_doctor else "Unknown Doctor"
                doctor_specialization = prev_doctor.specialization if prev_doctor and prev_doctor.specialization else ""
                
                context_part = f"Doctor {prev_step.step_index + 1}: {doctor_name}"
                if doctor_specialization:
                    context_part += f" ({doctor_specialization})"
                context_part += "\n"
                
                if prev_step.review_summary:
                    context_part += f"Summary: {prev_step.review_summary}\n"
                if prev_step.review_notes:
                    context_part += f"Notes: {prev_step.review_notes}\n"
                
                accumulated_context_parts.append(context_part)
                print(f"[TOOLS] Added context from Step {prev_step.step_index + 1}: {doctor_name}")
            
            accumulated_context = "\n\n".join(accumulated_context_parts) if accumulated_context_parts else "No previous reviews."
            # #region agent log
            import json
            with open('/Users/vidhan/Vidhan/GDG FINAL/AutonomousHacks26/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"complex_case_tools.py:419","message":"Accumulated context built","data":{"chain_id":chain_id,"current_step_index":chain.current_step_index,"previous_steps_count":len(previous_steps),"accumulated_context_length":len(accumulated_context),"has_review_notes":any(s.review_notes for s in previous_steps)},"timestamp":int(datetime.utcnow().timestamp()*1000)}) + '\n')
            # #endregion
            print(f"[TOOLS] Accumulated context length: {len(accumulated_context)} characters")
            
            # Get total steps
            total_steps_result = await session.execute(
                select(SequentialReviewStep).where(SequentialReviewStep.chain_id == uuid.UUID(chain_id))
            )
            total_steps = len(total_steps_result.scalars().all())
            
            return {
                "status": "success",
                "step_id": str(step.step_id),
                "doctor_id": str(step.doctor_id),
                "doctor_info": {
                    "doctor_id": str(doctor.service_person_id),
                    "name": doctor.name,
                    "service_type": doctor.service_type,
                    "specialization": doctor.specialization,
                    "email": doctor.email
                },
                "accumulated_context": accumulated_context,
                "step_index": step.step_index,
                "total_steps": total_steps
            }
            
        except Exception as e:
            import traceback
            error_msg = f"Error getting next doctor in chain: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            return {"status": "error", "error": error_msg}


@tool
def get_next_doctor_in_chain(chain_id: str) -> dict:
    """Get next doctor in chain with accumulated context from previous doctors.
    
    Args:
        chain_id: SequentialReviewChain UUID
    
    Returns:
        Dictionary with step_id, doctor_id, doctor_info, accumulated_context, step_index, total_steps
    """
    try:
        return run_async_safely(
            _get_next_doctor_in_chain_async,
            chain_id,
            session_maker_param=True
        )
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": f"Exception in get_next_doctor_in_chain: {str(e)}\n{traceback.format_exc()}"
        }


async def _submit_doctor_review_async(
    step_id: str,
    review_notes: str,
    doctor_id: str,
    session_maker=None
) -> dict:
    """Submit doctor review and advance chain to next step."""
    # #region agent log
    import json
    with open('/Users/vidhan/Vidhan/GDG FINAL/AutonomousHacks26/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"complex_case_tools.py:478","message":"_submit_doctor_review_async called","data":{"step_id":step_id,"doctor_id":doctor_id,"review_notes_length":len(review_notes) if review_notes else 0},"timestamp":int(datetime.utcnow().timestamp()*1000)}) + '\n')
    # #endregion
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            # Get step
            step_result = await session.execute(
                select(SequentialReviewStep).where(SequentialReviewStep.step_id == uuid.UUID(step_id))
            )
            step = step_result.scalar_one_or_none()
            if not step:
                # #region agent log
                with open('/Users/vidhan/Vidhan/GDG FINAL/AutonomousHacks26/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"complex_case_tools.py:497","message":"Step not found","data":{"step_id":step_id},"timestamp":int(datetime.utcnow().timestamp()*1000)}) + '\n')
                # #endregion
                return {"status": "error", "error": f"Step {step_id} not found"}
            
            # Verify doctor matches
            if str(step.doctor_id) != doctor_id:
                return {"status": "error", "error": "Doctor ID does not match step assignment"}
            
            # Get chain
            chain_result = await session.execute(
                select(SequentialReviewChain).where(SequentialReviewChain.chain_id == step.chain_id)
            )
            chain = chain_result.scalar_one_or_none()
            if not chain:
                return {"status": "error", "error": f"Chain {chain.chain_id} not found"}
            
            # Generate AI summary of review
            summary_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a medical AI assistant. Summarize the doctor's review notes into a concise summary highlighting key findings and recommendations."),
                ("human", "Doctor's Review Notes:\n{review_notes}\n\nGenerate a concise summary:")
            ])
            summary_chain = summary_prompt | llm
            summary_response = summary_chain.invoke({"review_notes": review_notes})
            review_summary = summary_response.content.strip()
            
            # Update step
            step.review_notes = review_notes
            step.review_summary = review_summary
            step.status = "completed"
            step.completed_at = datetime.utcnow()
            
            # Build accumulated context (include this review)
            accumulated_context = {
                "step_index": step.step_index,
                "doctor_id": str(step.doctor_id),
                "review_notes": review_notes,
                "review_summary": review_summary,
                "completed_at": step.completed_at.isoformat()
            }
            step.accumulated_context = accumulated_context
            
            # Advance chain
            chain.current_step_index += 1
            
            # Check if chain is complete
            total_steps_result = await session.execute(
                select(SequentialReviewStep).where(SequentialReviewStep.chain_id == chain.chain_id)
            )
            total_steps = len(total_steps_result.scalars().all())
            
            if chain.current_step_index >= total_steps:
                chain.status = "completed"
                chain.completed_at = datetime.utcnow()
            else:
                chain.status = "in_progress"
            
            await session.commit()
            await session.refresh(step)
            await session.refresh(chain)
            # #region agent log
            with open('/Users/vidhan/Vidhan/GDG FINAL/AutonomousHacks26/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"complex_case_tools.py:551","message":"After commit - step and chain status","data":{"step_status":step.status,"chain_current_step":chain.current_step_index,"chain_status":chain.status,"has_completed_at":step.completed_at is not None},"timestamp":int(datetime.utcnow().timestamp()*1000)}) + '\n')
            # #endregion
            
            # Get current doctor info for logging
            current_doctor_result = await session.execute(
                select(ServicePerson).where(ServicePerson.service_person_id == step.doctor_id)
            )
            current_doctor = current_doctor_result.scalar_one_or_none()
            current_doctor_name = current_doctor.name if current_doctor else "Unknown"
            current_service_type = current_doctor.service_type if current_doctor else "Unknown"
            
            # Get next step if exists
            next_step_id = None
            next_doctor_name = None
            next_service_type = None
            if chain.current_step_index < total_steps:
                next_step_result = await session.execute(
                    select(SequentialReviewStep).where(
                        SequentialReviewStep.chain_id == chain.chain_id,
                        SequentialReviewStep.step_index == chain.current_step_index
                    )
                )
                next_step = next_step_result.scalar_one_or_none()
                if next_step:
                    next_step_id = str(next_step.step_id)
                    # Get next doctor info
                    next_doctor_result = await session.execute(
                        select(ServicePerson).where(ServicePerson.service_person_id == next_step.doctor_id)
                    )
                    next_doctor = next_doctor_result.scalar_one_or_none()
                    next_doctor_name = next_doctor.name if next_doctor else "Unknown"
                    next_service_type = next_doctor.service_type if next_doctor else "Unknown"
            
            return {
                "status": "success",
                "step_completed": True,
                "next_step_id": next_step_id,
                "chain_status": chain.status,
                "current_step_index": step.step_index,
                "total_steps": total_steps,
                "current_doctor_name": current_doctor_name,
                "current_service_type": current_service_type,
                "next_doctor_name": next_doctor_name,
                "next_service_type": next_service_type
            }
            
        except Exception as e:
            await session.rollback()
            import traceback
            error_msg = f"Error submitting doctor review: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            return {"status": "error", "error": error_msg}


@tool
def submit_doctor_review(
    step_id: str,
    review_notes: str,
    doctor_id: str
) -> dict:
    """Submit doctor review and advance chain to next step.
    
    Args:
        step_id: SequentialReviewStep UUID
        review_notes: Doctor's review notes/insights
        doctor_id: Doctor's UUID (for verification)
    
    Returns:
        Dictionary with step_completed, next_step_id (if exists), chain_status
    """
    try:
        return run_async_safely(
            _submit_doctor_review_async,
            step_id,
            review_notes,
            doctor_id,
            session_maker_param=True
        )
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": f"Exception in submit_doctor_review: {str(e)}\n{traceback.format_exc()}"
        }


async def _get_accumulated_context_async(
    chain_id: str,
    step_index: int,
    session_maker=None
) -> dict:
    """Get accumulated context from all previous doctors' reviews."""
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            # Get all completed steps before this step_index
            steps_result = await session.execute(
                select(SequentialReviewStep).where(
                    SequentialReviewStep.chain_id == uuid.UUID(chain_id),
                    SequentialReviewStep.step_index < step_index,
                    SequentialReviewStep.status == "completed"
                ).order_by(SequentialReviewStep.step_index)
            )
            steps = steps_result.scalars().all()
            
            context_parts = []
            for step in steps:
                doctor_result = await session.execute(
                    select(ServicePerson).where(ServicePerson.service_person_id == step.doctor_id)
                )
                doctor = doctor_result.scalar_one_or_none()
                doctor_name = doctor.name if doctor else "Unknown Doctor"
                
                context_part = f"Doctor {step.step_index + 1}: {doctor_name}\n"
                if step.review_summary:
                    context_part += f"Summary: {step.review_summary}\n"
                if step.review_notes:
                    context_part += f"Notes: {step.review_notes}\n"
                
                context_parts.append(context_part)
            
            accumulated_context = "\n\n".join(context_parts) if context_parts else "No previous reviews."
            
            return {
                "status": "success",
                "accumulated_context": accumulated_context,
                "steps_count": len(steps)
            }
            
        except Exception as e:
            import traceback
            error_msg = f"Error getting accumulated context: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            return {"status": "error", "error": error_msg}


@tool
def get_accumulated_context(chain_id: str, step_index: int) -> dict:
    """Get accumulated context from all previous doctors' reviews.
    
    Args:
        chain_id: SequentialReviewChain UUID
        step_index: Step index to get context up to (exclusive)
    
    Returns:
        Dictionary with accumulated_context (formatted text) and steps_count
    """
    try:
        return run_async_safely(
            _get_accumulated_context_async,
            chain_id,
            step_index,
            session_maker_param=True
        )
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": f"Exception in get_accumulated_context: {str(e)}\n{traceback.format_exc()}"
        }

"""LangGraph tools for doctor/service person operations."""
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.src.database.models import ServicePerson, Ticket
from backend.src.database.connection import async_session_maker
import uuid
import asyncio
import concurrent.futures
import json
from backend.src.config import settings


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
        return future.result(timeout=30)  # Increased timeout for LLM calls


class RankedDoctor(BaseModel):
    """Model for a ranked doctor."""
    doctor_id: str = Field(description="Service person ID")
    name: str = Field(description="Doctor name")
    service_type: str = Field(description="Service type")
    specialization: Optional[str] = Field(None, description="Specialization if available")
    rank: int = Field(description="Ranking from 1-5 (1 is best)")
    reason: str = Field(description="Reason for this ranking")


class DoctorRankingResult(BaseModel):
    """Model for doctor ranking results."""
    ranked_doctors: List[RankedDoctor] = Field(description="Top 5 ranked doctors")


async def _get_service_persons_by_type_async(service_type: str, session_maker=None) -> dict:
    """Async implementation of get_service_persons_by_type."""
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            result = await session.execute(
                select(ServicePerson).where(
                    ServicePerson.service_type == service_type,
                    ServicePerson.is_active == True
                )
            )
            doctors = result.scalars().all()
            
            doctors_list = []
            for doctor in doctors:
                doctors_list.append({
                    "doctor_id": str(doctor.service_person_id),
                    "name": doctor.name,
                    "service_type": doctor.service_type,
                    "specialization": doctor.specialization,
                    "email": doctor.email
                })
            
            return {
                "status": "success",
                "service_type": service_type,
                "doctors": doctors_list,
                "count": len(doctors_list)
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


@tool
def get_service_persons_by_type(service_type: str) -> dict:
    """Query service persons (doctors) by service type.
    
    Args:
        service_type: The service type to filter by (e.g., 'orthopedics', 'cardiology', 'emergency')
    
    Returns:
        Dictionary with status, service_type, doctors list, and count
    """
    try:
        return run_async_safely(
            _get_service_persons_by_type_async,
            service_type,
            session_maker_param=True
        )
    except Exception as e:
        import traceback
        return {"status": "error", "error": f"Exception in get_service_persons_by_type: {str(e)}\n{traceback.format_exc()}"}


async def _rank_doctors_with_llm_async(
    patient_history: dict,
    user_request: str,
    doctors: List[dict],
    service_type: str,
    session_maker=None
) -> dict:
    """Async implementation of rank_doctors_with_llm."""
    try:
        # Initialize LLM with structured output
        ranking_llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.3,  # Lower temperature for more consistent ranking
            api_key=settings.openai_api_key
        )
        structured_llm = ranking_llm.with_structured_output(DoctorRankingResult)
        
        # Format patient history for prompt
        history_text = "No previous history available."
        if patient_history and patient_history.get("history"):
            history_records = patient_history.get("history", [])
            if history_records:
                history_lines = []
                for record in history_records[:10]:  # Limit to last 10 records
                    history_lines.append(
                        f"- {record.get('visit_date', 'Unknown date')}: "
                        f"{record.get('service_type', 'Unknown')} - "
                        f"{record.get('diagnosis', 'No diagnosis')}"
                    )
                history_text = "\n".join(history_lines)
        
        # Format doctors list for prompt
        doctors_text = "\n".join([
            f"- {doc['name']} (ID: {doc['doctor_id']}): {doc['service_type']}"
            f"{' - ' + doc['specialization'] if doc.get('specialization') else ''}"
            for doc in doctors
        ])
        
        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a medical assistant helping to rank doctors for a patient.
Given the patient's medical history, their current request, and available doctors, 
rank the top 5 most suitable doctors. Consider:
- Specialization match with patient history
- Service type alignment
- Patient's current symptoms/needs
- Relevance to the medical condition

Provide ranking (1-5) with clear, concise reasoning for each doctor (1-2 sentences each).
Only rank doctors that are actually in the provided list."""),
            ("human", """Patient Medical History:
{history}

Current Request: {request}

Service Type Needed: {service_type}

Available Doctors:
{doctors}

Please rank the top 5 most suitable doctors for this patient with clear reasoning.""")
        ])
        
        # Limit to top 10 doctors if more than 10 provided
        doctors_to_rank = doctors[:10] if len(doctors) > 10 else doctors
        
        # Get ranking from LLM
        chain = prompt | structured_llm
        result = chain.invoke({
            "history": history_text,
            "request": user_request,
            "service_type": service_type,
            "doctors": doctors_text
        })
        
        # Convert to dict format
        ranked_list = []
        # Ensure we rank up to 5 doctors, but handle cases with fewer doctors
        max_doctors_to_rank = min(5, len(doctors))
        for ranked_doc in result.ranked_doctors[:max_doctors_to_rank]:
            ranked_list.append({
                "doctor_id": ranked_doc.doctor_id,
                "name": ranked_doc.name,
                "service_type": ranked_doc.service_type,
                "specialization": ranked_doc.specialization,
                "rank": ranked_doc.rank,
                "reason": ranked_doc.reason
            })
        
        # Validation: Ensure we have at least one ranked doctor
        if not ranked_list:
            raise ValueError(f"No doctors could be ranked. Available doctors: {len(doctors)}")
        
        # Log warning if fewer than 5 doctors
        if len(ranked_list) < 5:
            print(f"Warning: Only {len(ranked_list)} doctor(s) available for ranking (requested 5)")
        
        return {
            "status": "success",
            "ranked_doctors": ranked_list,
            "service_type": service_type,
            "doctors_available": len(doctors),
            "doctors_ranked": len(ranked_list)
        }
    except Exception as e:
        import traceback
        # Fallback: simple ranking by service_type match
        # Handle cases with fewer than 5 doctors
        max_doctors = min(5, len(doctors))
        if max_doctors == 0:
            return {
                "status": "error",
                "ranked_doctors": [],
                "service_type": service_type,
                "error": "No doctors available to rank",
                "doctors_available": 0,
                "doctors_ranked": 0
            }
        
        fallback_ranked = []
        for idx, doc in enumerate(doctors[:max_doctors], 1):
            fallback_ranked.append({
                "doctor_id": doc["doctor_id"],
                "name": doc["name"],
                "service_type": doc["service_type"],
                "specialization": doc.get("specialization"),
                "rank": idx,
                "reason": f"Available {doc['service_type']} specialist"
            })
        
        # Log warning about fallback
        print(f"Warning: Using fallback ranking due to error: {str(e)}")
        if len(fallback_ranked) < 5:
            print(f"Warning: Only {len(fallback_ranked)} doctor(s) available (requested 5)")
        
        return {
            "status": "fallback",
            "ranked_doctors": fallback_ranked,
            "service_type": service_type,
            "error": str(e),
            "doctors_available": len(doctors),
            "doctors_ranked": len(fallback_ranked)
        }


@tool
def rank_doctors_with_llm(
    patient_history: dict,
    user_request: str,
    doctors: List[dict],
    service_type: str
) -> dict:
    """Rank doctors using LLM based on patient history and request.
    
    Args:
        patient_history: Patient's medical history dictionary
        user_request: The user's current request/description of their need
        doctors: List of doctor dictionaries from get_service_persons_by_type
        service_type: The determined service type
    
    Returns:
        Dictionary with status and ranked_doctors list (top 5)
    """
    try:
        return run_async_safely(
            _rank_doctors_with_llm_async,
            patient_history,
            user_request,
            doctors,
            service_type,
            session_maker_param=True
        )
    except Exception as e:
        import traceback
        return {"status": "error", "error": f"Exception in rank_doctors_with_llm: {str(e)}\n{traceback.format_exc()}"}


async def _create_multiple_tickets_async(
    patient_id: str,
    conversation_id: str,
    ranked_doctors: List[dict],
    service_type: str,
    description: str,
    patient_details: dict,
    past_history_summary: str,
    llm_summary: str,
    priority: int = 3,
    session_maker=None
) -> dict:
    """Async implementation of create_multiple_tickets."""
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            # Validation: Ensure we have ranked doctors
            if not ranked_doctors or len(ranked_doctors) == 0:
                return {
                    "status": "error",
                    "error": "No ranked doctors provided. Cannot create tickets.",
                    "tickets_created": 0,
                    "tickets": []
                }
            
            # Handle cases with fewer than 5 doctors - create tickets for all available
            doctors_to_process = ranked_doctors[:5]  # Max 5, but can be fewer
            if len(doctors_to_process) < 5:
                print(f"Info: Creating tickets for {len(doctors_to_process)} doctor(s) (fewer than 5 available)")
            
            created_tickets = []
            errors = []
            
            for doctor in doctors_to_process:
                try:
                    ticket = Ticket(
                        conversation_id=uuid.UUID(conversation_id),
                        patient_id=uuid.UUID(patient_id),
                        service_type=service_type,
                        description=description,
                        priority=priority,
                        assigned_to=uuid.UUID(doctor["doctor_id"]),
                        patient_details=patient_details,
                        past_history_summary=past_history_summary,
                        llm_summary=f"{llm_summary}\n\nDoctor Ranking: Rank #{doctor['rank']} - {doctor['reason']}",
                        status="open"  # Start as open, doctor must accept to proceed
                    )
                    session.add(ticket)
                    await session.flush()  # Flush to get ticket_id
                    
                    created_tickets.append({
                        "ticket_id": str(ticket.ticket_id),
                        "doctor_id": doctor["doctor_id"],
                        "doctor_name": doctor["name"],
                        "rank": doctor["rank"],
                        "status": "created"
                    })
                except Exception as e:
                    errors.append({
                        "doctor_id": doctor.get("doctor_id", "unknown"),
                        "doctor_name": doctor.get("name", "unknown"),
                        "error": str(e)
                    })
            
            await session.commit()
            
            # Validation: Check if any tickets were created
            if len(created_tickets) == 0:
                return {
                    "status": "error",
                    "error": "Failed to create any tickets. All attempts resulted in errors.",
                    "tickets_created": 0,
                    "tickets": [],
                    "errors": errors
                }
            
            return {
                "status": "success",
                "tickets_created": len(created_tickets),
                "tickets": created_tickets,
                "errors": errors if errors else None,
                "doctors_processed": len(doctors_to_process),
                "doctors_successful": len(created_tickets)
            }
        except Exception as e:
            await session.rollback()
            import traceback
            return {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tickets_created": 0,
                "tickets": []
            }


@tool
def create_multiple_tickets(
    patient_id: str,
    conversation_id: str,
    ranked_doctors: List[dict],
    service_type: str,
    description: str,
    patient_details: dict,
    past_history_summary: str,
    llm_summary: str,
    priority: int = 3
) -> dict:
    """Create tickets for multiple doctors (top 5 ranked doctors).
    
    Args:
        patient_id: Patient UUID
        conversation_id: Conversation UUID
        ranked_doctors: List of ranked doctor dictionaries (from rank_doctors_with_llm)
        service_type: Service type string
        description: Description of the patient's request
        patient_details: Full patient details dictionary
        past_history_summary: Formatted patient history summary
        llm_summary: LLM-generated summary
        priority: Ticket priority (1-5, default 3)
    
    Returns:
        Dictionary with status, tickets_created count, and tickets list
    """
    try:
        return run_async_safely(
            _create_multiple_tickets_async,
            patient_id,
            conversation_id,
            ranked_doctors,
            service_type,
            description,
            patient_details,
            past_history_summary,
            llm_summary,
            priority,
            session_maker_param=True
        )
    except Exception as e:
        import traceback
        return {"status": "error", "error": f"Exception in create_multiple_tickets: {str(e)}\n{traceback.format_exc()}"}

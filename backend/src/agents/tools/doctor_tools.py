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
from datetime import datetime

# Get top N from config
TOP_N_DOCTORS = getattr(settings, 'top_doctors_count', 5)


async def _get_available_service_types_async(session_maker=None) -> List[str]:
    """Get unique service types from active service persons.
    
    Returns a list of unique service_type values from service_persons where is_active = True.
    This is dynamic and will automatically include any new service types added to the database.
    
    Returns:
        List of unique service type strings (e.g., ['lab test', 'general consultation', 'cardiology'])
    """
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            # Get distinct service_type values from active and available service persons
            result = await session.execute(
                select(ServicePerson.service_type).distinct().where(
                    ServicePerson.is_active == True,
                    ServicePerson.is_available == True  # Only include available service persons
                )
            )
            service_types = [row[0] for row in result.fetchall()]
            print(f"[SCHEMA CHECK] Service types query successful: {len(service_types)} types found")
            return sorted(service_types) if service_types else []
        except AttributeError as e:
            # Likely schema issue - column doesn't exist
            import traceback
            error_msg = f"SCHEMA ERROR: Column may not exist in ServicePerson model. Error: {str(e)}\n{traceback.format_exc()}"
            print(f"[SCHEMA ERROR] {error_msg}")
            raise Exception(f"Database schema issue: {error_msg}")
        except Exception as e:
            import traceback
            error_msg = f"Error fetching available service types: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            # Re-raise to distinguish from "no results" (empty list)
            raise Exception(f"Database query error: {error_msg}")


def get_available_service_types() -> List[str]:
    """Get unique service types from active service persons (sync wrapper).
    
    Returns a list of unique service_type values dynamically from the database.
    """
    try:
        return run_async_safely(
            _get_available_service_types_async,
            session_maker_param=True
        )
    except Exception as e:
        print(f"Error fetching available service types: {e}")
        return []


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
    ranked_doctors: List[RankedDoctor] = Field(description=f"Top {TOP_N_DOCTORS} ranked doctors")


async def _get_service_persons_by_type_async(service_type: str, session_maker=None) -> dict:
    """Async implementation of get_service_persons_by_type."""
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            try:
                test_query = select(ServicePerson.service_person_id).limit(1)
                await session.execute(test_query)
            except (AttributeError, Exception) as schema_error:
                error_msg = f"SCHEMA ERROR: ServicePerson table or columns may not exist. Error: {str(schema_error)}"
                print(f"[SCHEMA ERROR] {error_msg}")
                return {
                    "status": "schema_error",
                    "error": error_msg,
                    "service_type": service_type,
                    "doctors": [],
                    "count": 0,
                    "diagnostic": "Schema validation failed - check database schema"
                }
            
            # Query available doctors: active, available, and with workload capacity
            print(f"[QUERY] Searching doctors with filters: service_type={service_type}, is_active=True, is_available=True, workload<max")
            result = await session.execute(
                select(ServicePerson).where(
                    ServicePerson.service_type == service_type,
                    ServicePerson.is_active == True,
                    ServicePerson.is_available == True,  # Check availability flag
                    ServicePerson.current_workload < ServicePerson.max_workload  # Check workload capacity
                )
            )
            doctors = result.scalars().all()
            
            # Diagnostic: Check how many doctors exist without filters
            total_result = await session.execute(
                select(ServicePerson).where(ServicePerson.service_type == service_type)
            )
            total_doctors = total_result.scalars().all()
            
            print(f"[QUERY RESULT] Found {len(doctors)} available doctors (out of {len(total_doctors)} total for service_type '{service_type}')")
            
            # If no doctors found, provide diagnostic information
            if len(doctors) == 0:
                # Check why no doctors found
                active_result = await session.execute(
                    select(ServicePerson).where(
                        ServicePerson.service_type == service_type,
                        ServicePerson.is_active == True
                    )
                )
                active_doctors = active_result.scalars().all()
                
                available_result = await session.execute(
                    select(ServicePerson).where(
                        ServicePerson.service_type == service_type,
                        ServicePerson.is_active == True,
                        ServicePerson.is_available == True
                    )
                )
                available_doctors = available_result.scalars().all()
                
                workload_ok_result = await session.execute(
                    select(ServicePerson).where(
                        ServicePerson.service_type == service_type,
                        ServicePerson.is_active == True,
                        ServicePerson.is_available == True,
                        ServicePerson.current_workload < ServicePerson.max_workload
                    )
                )
                workload_ok_doctors = workload_ok_result.scalars().all()
                
                diagnostic_info = {
                    "total_with_service_type": len(total_doctors),
                    "active_count": len(active_doctors),
                    "available_count": len(available_doctors),
                    "workload_ok_count": len(workload_ok_doctors),
                    "reason": "No doctors found matching all criteria"
                }
                
                if len(total_doctors) == 0:
                    diagnostic_info["reason"] = f"No doctors exist with service_type '{service_type}'"
                elif len(active_doctors) == 0:
                    diagnostic_info["reason"] = f"All {len(total_doctors)} doctors with service_type '{service_type}' are inactive"
                elif len(available_doctors) == 0:
                    diagnostic_info["reason"] = f"All {len(active_doctors)} active doctors are marked as unavailable"
                elif len(workload_ok_doctors) == 0:
                    diagnostic_info["reason"] = f"All {len(available_doctors)} available doctors have reached max workload"
                
                print(f"[DIAGNOSTIC] {diagnostic_info['reason']}")
                
                return {
                    "status": "success",  # Still success - no doctors is a valid result
                    "service_type": service_type,
                    "doctors": [],
                    "count": 0,
                    "diagnostic": diagnostic_info,
                    "message": diagnostic_info["reason"]
                }
            
            doctors_list = []
            for doctor in doctors:
                doctors_list.append({
                    "doctor_id": str(doctor.service_person_id),
                    "name": doctor.name,
                    "service_type": doctor.service_type,
                    "specialization": doctor.specialization,
                    "email": doctor.email,
                    "current_workload": doctor.current_workload,
                    "max_workload": doctor.max_workload,
                    "is_available": doctor.is_available
                })
            
            return {
                "status": "success",
                "service_type": service_type,
                "doctors": doctors_list,
                "count": len(doctors_list)
            }
        except AttributeError as e:
            # Schema issue - attribute doesn't exist on model
            import traceback
            error_msg = f"SCHEMA ERROR: ServicePerson model attribute may not exist. Error: {str(e)}\n{traceback.format_exc()}"
            print(f"[SCHEMA ERROR] {error_msg}")
            return {
                "status": "schema_error",
                "error": error_msg,
                "service_type": service_type,
                "doctors": [],
                "count": 0,
                "diagnostic": "Schema validation failed - check ServicePerson model columns"
            }
        except Exception as e:
            import traceback
            error_msg = f"Database query error: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
                "service_type": service_type,
                "doctors": [],
                "count": 0
            }


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


async def _get_available_doctors_async(
    service_type: str,
    preferred_date_time: Optional[str] = None,
    session_maker=None
) -> dict:
    """Get active doctors available at specific date/time filtered by service_type.
    
    ROOT FIX: Filter by both is_active AND service_type.
    Then rank the filtered doctors and select top N.
    
    Args:
        service_type: Service type to filter by (e.g., 'orthopedics', 'lab test', 'cardiology')
        preferred_date_time: ISO format datetime (e.g., '2025-01-17T14:00:00')
                           If None, returns all active doctors in the service type
    
    Returns:
        Dictionary with status, doctors list, and count
    """
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            # Schema validation - verify table exists and columns are accessible
            try:
                test_query = select(ServicePerson.service_person_id).limit(1)
                await session.execute(test_query)
            except (AttributeError, Exception) as schema_error:
                error_msg = f"SCHEMA ERROR: ServicePerson table or columns may not exist. Error: {str(schema_error)}"
                print(f"[SCHEMA ERROR] {error_msg}")
                return {
                    "status": "schema_error",
                    "error": error_msg,
                    "service_type": service_type,
                    "preferred_date_time": preferred_date_time,
                    "doctors": [],
                    "count": 0,
                    "diagnostic": "Schema validation failed - check database schema"
                }
            
            # Query available doctors: active, available, and with workload capacity
            print(f"[QUERY] Searching doctors with filters: service_type={service_type}, is_active=True, is_available=True, workload<max")
            result = await session.execute(
                select(ServicePerson).where(
                    ServicePerson.is_active == True,
                    ServicePerson.is_available == True,  # Check availability flag
                    ServicePerson.service_type == service_type,
                    ServicePerson.current_workload < ServicePerson.max_workload  # Check workload capacity
                )
            )
            doctors = result.scalars().all()
            
            # Diagnostic: Check breakdown of why doctors might not be available
            total_result = await session.execute(
                select(ServicePerson).where(ServicePerson.service_type == service_type)
            )
            total_doctors = total_result.scalars().all()
            
            print(f"[QUERY RESULT] Found {len(doctors)} available doctors (out of {len(total_doctors)} total for service_type '{service_type}')")
            
            # If no doctors found, provide diagnostic information
            if len(doctors) == 0:
                # Diagnostic queries to understand why no results
                active_result = await session.execute(
                    select(ServicePerson).where(
                        ServicePerson.service_type == service_type,
                        ServicePerson.is_active == True
                    )
                )
                active_doctors = active_result.scalars().all()
                
                available_result = await session.execute(
                    select(ServicePerson).where(
                        ServicePerson.service_type == service_type,
                        ServicePerson.is_active == True,
                        ServicePerson.is_available == True
                    )
                )
                available_doctors = available_result.scalars().all()
                
                # Check workload details
                workload_details = []
                for doc in available_doctors:
                    workload_details.append({
                        "doctor_id": str(doc.service_person_id),
                        "name": doc.name,
                        "current_workload": doc.current_workload,
                        "max_workload": doc.max_workload,
                        "overloaded": doc.current_workload >= doc.max_workload
                    })
                
                diagnostic_info = {
                    "total_with_service_type": len(total_doctors),
                    "active_count": len(active_doctors),
                    "available_count": len(available_doctors),
                    "workload_ok_count": len(doctors),
                    "workload_details": workload_details,
                    "reason": "No doctors found matching all criteria"
                }
                
                if len(total_doctors) == 0:
                    diagnostic_info["reason"] = f"No doctors exist with service_type '{service_type}'. Check if service_type is correct."
                elif len(active_doctors) == 0:
                    diagnostic_info["reason"] = f"All {len(total_doctors)} doctors with service_type '{service_type}' are inactive (is_active=False)"
                elif len(available_doctors) == 0:
                    diagnostic_info["reason"] = f"All {len(active_doctors)} active doctors are marked as unavailable (is_available=False)"
                elif len(doctors) == 0:
                    diagnostic_info["reason"] = f"All {len(available_doctors)} available doctors have reached max workload (current_workload >= max_workload)"
                
                print(f"[DIAGNOSTIC] {diagnostic_info['reason']}")
                print(f"[DIAGNOSTIC] Workload details: {workload_details}")
                
                return {
                    "status": "success",  # No doctors found is a valid result, not an error
                    "service_type": service_type,
                    "preferred_date_time": preferred_date_time,
                    "doctors": [],
                    "count": 0,
                    "diagnostic": diagnostic_info,
                    "message": diagnostic_info["reason"]
                }
            
            doctors_list = []
            for doctor in doctors:
                doctors_list.append({
                    "doctor_id": str(doctor.service_person_id),
                    "name": doctor.name,
                    "service_type": doctor.service_type,
                    "specialization": doctor.specialization,
                    "email": doctor.email,
                    "current_workload": doctor.current_workload,
                    "max_workload": doctor.max_workload,
                    "is_available": doctor.is_available
                })
            
            return {
                "status": "success",
                "service_type": service_type,  # Keep for context
                "doctors": doctors_list,
                "count": len(doctors_list),
                "preferred_date_time": preferred_date_time
            }
        except AttributeError as e:
            # Schema issue - attribute doesn't exist on model
            import traceback
            error_msg = f"SCHEMA ERROR: ServicePerson model attribute may not exist. Check if columns (is_active, is_available, current_workload, max_workload) exist. Error: {str(e)}\n{traceback.format_exc()}"
            print(f"[SCHEMA ERROR] {error_msg}")
            return {
                "status": "schema_error",
                "error": error_msg,
                "service_type": service_type,
                "preferred_date_time": preferred_date_time,
                "doctors": [],
                "count": 0,
                "diagnostic": "Schema validation failed - verify ServicePerson model has: is_active, is_available, current_workload, max_workload columns"
            }
        except Exception as e:
            import traceback
            error_msg = f"Database query error: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
                "service_type": service_type,
                "preferred_date_time": preferred_date_time,
                "doctors": [],
                "count": 0
            }


@tool
def get_available_doctors_by_type_and_time(
    service_type: str,
    preferred_date_time: Optional[str] = None
) -> dict:
    """Get active doctors filtered by service type and available at specific date/time.

    
    Args:
        service_type: The service type to filter by (e.g., 'orthopedics', 'cardiology', 'lab test')
        preferred_date_time: ISO format datetime (e.g., '2025-01-17T14:00:00')
                           If None, returns all active doctors in the service type
    
    Returns:
        Dictionary with status, service_type, doctors list, count, and preferred_date_time
    """
    try:
        return run_async_safely(
            _get_available_doctors_async,
            service_type,
            preferred_date_time,
            session_maker_param=True
        )
    except Exception as e:
        import traceback
        return {"status": "error", "error": f"Exception in get_available_doctors_by_type_and_time: {str(e)}\n{traceback.format_exc()}"}


async def _rank_doctors_with_llm_async(
    patient_history: dict,
    user_request: str,
    doctors: List[dict],
    service_type: str,
    preferred_date_time: Optional[str] = None,
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
        # ROOT FIX: Use 'history_records' field (not 'history') from get_patient_history tool
        history_text = "No previous history available."
        history_summary = ""
        if patient_history and patient_history.get("history_records"):
            history_records = patient_history.get("history_records", [])
            if history_records:
                history_lines = []
                service_types_seen = {}
                diagnoses_seen = {}
                
                for record in history_records[:10]:  # Limit to last 10 records
                    service_type = record.get('service_type', 'Unknown')
                    diagnosis = record.get('diagnosis', 'No diagnosis')
                    treatment = record.get('treatment', '')
                    
                    # Track service types and diagnoses for pattern analysis
                    service_types_seen[service_type] = service_types_seen.get(service_type, 0) + 1
                    if diagnosis and diagnosis != 'No diagnosis':
                        diagnoses_seen[diagnosis] = diagnoses_seen.get(diagnosis, 0) + 1
                    
                    history_line = f"- {record.get('visit_date', 'Unknown date')}: {service_type}"
                    if diagnosis and diagnosis != 'No diagnosis':
                        history_line += f" - Diagnosis: {diagnosis}"
                    if treatment:
                        history_line += f" - Treatment: {treatment[:100]}"  # Limit treatment length
                    history_lines.append(history_line)
                
                history_text = "\n".join(history_lines)
                
                # Add summary of patterns
                if service_types_seen:
                    common_services = sorted(service_types_seen.items(), key=lambda x: x[1], reverse=True)[:3]
                    history_summary = f"\n\nPatient History Patterns:\n"
                    history_summary += f"- Most frequent service types: {', '.join([f'{s} ({c}x)' for s, c in common_services])}\n"
                    if diagnoses_seen:
                        common_diagnoses = sorted(diagnoses_seen.items(), key=lambda x: x[1], reverse=True)[:3]
                        history_summary += f"- Recurring conditions: {', '.join([f'{d} ({c}x)' for d, c in common_diagnoses])}"
        elif patient_history and patient_history.get("status") == "schema_error":
            # Schema error - include in prompt for context
            error_msg = patient_history.get("error", "Schema error retrieving history")
            history_text = f"Note: Unable to retrieve patient history due to schema issue: {error_msg}"
        
        # Format doctors list for prompt with workload information
        doctors_text = "\n".join([
            f"- {doc['name']} (ID: {doc['doctor_id']}): {doc['service_type']}"
            f"{' - ' + doc['specialization'] if doc.get('specialization') else ''}"
            f" | Workload: {doc.get('current_workload', 0)}/{doc.get('max_workload', 10)} "
            f"({(doc.get('current_workload', 0) / doc.get('max_workload', 10) * 100) if doc.get('max_workload', 10) > 0 else 0:.0f}% capacity)"
            for doc in doctors
        ])
        
        top_n = min(TOP_N_DOCTORS, len(doctors))
        date_time_context = f"\nPreferred Appointment Time: {preferred_date_time}" if preferred_date_time else ""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a medical assistant helping to rank doctors for a patient.
Given the patient's medical history, their current request, and available doctors, 
rank the top 5 most suitable doctors. 

IMPORTANT: All doctors in the provided list are already ACTIVE and AVAILABLE (is_active=True), 
so you don't need to filter by availability. Focus on ranking based on:

- Specialization match with patient history
- Service type alignment
- Patient's current symptoms/needs
- Relevance to the medical condition
- Experience and expertise for the specific condition

Provide ranking (1-5) with clear, concise reasoning for each doctor (1-2 sentences each).
Only rank doctors that are actually in the provided list.
Prioritize doctors who are most suitable for the patient's specific medical needs."""),
            ("human", """Patient Medical History:
{history}

Rank ALL {len(doctors)} doctors from most suitable (1) to least suitable ({len(doctors)}).
Provide clear, concise reasoning for each doctor (1-2 sentences each), mentioning specialization match, workload capacity, and expertise.
Then select the top {top_n} from your rankings."""),
            ("human", f"""Patient Medical History:
{{history}}{{history_summary}}

Current Request: {{request}}

Service Type Needed: {service_type}{date_time_context}

Available Doctors ({len(doctors)} active doctors filtered by service_type '{service_type}' with available capacity):
{{doctors}}

Please rank ALL {len(doctors)} doctors based on:
1. Specialization match with patient history and current symptoms
2. Workload capacity (prefer doctors with lower workload when specialization match is similar)
3. General expertise

Then provide the top {top_n} most suitable doctors with clear reasoning that includes workload consideration.""")
        ])
        
        # Limit to top 10 doctors if more than 10 provided
        doctors_to_rank = doctors[:10] if len(doctors) > 10 else doctors
        
        # Get ranking from LLM
        chain = prompt | structured_llm
        result = chain.invoke({
            "history": history_text,
            "history_summary": history_summary,
            "request": user_request,
            "service_type": service_type,
            "doctors": doctors_text
        })
        
        # Convert to dict format
        ranked_list = []
        # Ensure we rank up to top_n doctors (from config), but handle cases with fewer doctors
        max_doctors_to_rank = min(TOP_N_DOCTORS, len(doctors))
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
        
        # Log warning if fewer than top_n doctors
        if len(ranked_list) < TOP_N_DOCTORS:
            print(f"Warning: Only {len(ranked_list)} doctor(s) available for ranking (requested {TOP_N_DOCTORS})")
        
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
        # Handle cases with fewer than top_n doctors
        max_doctors = min(TOP_N_DOCTORS, len(doctors))
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
        if len(fallback_ranked) < TOP_N_DOCTORS:
            print(f"Warning: Only {len(fallback_ranked)} doctor(s) available (requested {TOP_N_DOCTORS})")
        
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
    service_type: str,
    preferred_date_time: Optional[str] = None
) -> dict:
    """Rank doctors using LLM based on patient history and request.
    
    Args:
        patient_history: Patient's medical history dictionary
        user_request: The user's current request/description of their need
        doctors: List of doctor dictionaries from get_available_doctors_by_type_and_time
        service_type: The determined service type
        preferred_date_time: Optional preferred date/time in ISO format
    
    Returns:
        Dictionary with status and ranked_doctors list (top N from config)
    """
    try:
        return run_async_safely(
            _rank_doctors_with_llm_async,
            patient_history,
            user_request,
            doctors,
            service_type,
            preferred_date_time,
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
            
            # Handle cases with fewer than top_n doctors - create tickets for all available
            top_n = TOP_N_DOCTORS
            doctors_to_process = ranked_doctors[:top_n]  # Max top_n, but can be fewer
            if len(doctors_to_process) < top_n:
                print(f"Info: Creating tickets for {len(doctors_to_process)} doctor(s) (fewer than {top_n} available)")
            
            created_tickets = []
            errors = []
            
            for doctor in doctors_to_process:
                try:
                    print(f"DEBUG: Creating ticket for doctor: {doctor.get('name')} (ID: {doctor.get('doctor_id')})")
                    print(f"DEBUG: conversation_id={conversation_id}, patient_id={patient_id}, service_type={service_type}")
                    
                    ticket = Ticket(
                        conversation_id=uuid.UUID(conversation_id),
                        patient_id=uuid.UUID(patient_id),
                        service_type=service_type,
                        description=description,
                        priority=priority,
                        assigned_to=uuid.UUID(doctor["doctor_id"]),  # This is the "offered to" doctor
                        patient_details=patient_details,
                        past_history_summary=past_history_summary,
                        llm_summary=llm_summary,  # Use the patient case summary directly, no doctor ranking info
                        status="open"  # Start as open, doctor must accept to proceed
                    )
                    session.add(ticket)
                    await session.flush()  # Flush to get ticket_id
                    
                    print(f"DEBUG: Successfully created ticket {ticket.ticket_id} for doctor {doctor.get('name')}")
                    
                    created_tickets.append({
                        "ticket_id": str(ticket.ticket_id),
                        "doctor_id": doctor["doctor_id"],
                        "doctor_name": doctor["name"],
                        "rank": doctor["rank"],
                        "status": "open",  # Match database status
                        "service_type": service_type,  # ROOT FIX: Include service_type in ticket data
                        "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
                        "priority": priority,
                        "conversation_id": str(ticket.conversation_id) if ticket.conversation_id else None,
                    })
                except Exception as e:
                    import traceback
                    error_traceback = traceback.format_exc()
                    error_msg = f"{str(e)}\n{traceback.format_exc()}"
                    print(f"ERROR: Failed to create ticket for doctor {doctor.get('name')}: {error_msg}")
                    errors.append({
                        "doctor_id": doctor.get("doctor_id", "unknown"),
                        "doctor_name": doctor.get("name", "unknown"),
                        "error": str(e),
                        "traceback": error_traceback
                    })
            
            await session.commit()
            
            # Validation: Check if any tickets were created
            if len(created_tickets) == 0:
                error_summary = "\n".join([f"- {e.get('doctor_name', 'Unknown')}: {e.get('error', 'Unknown error')}" for e in errors])
                print(f"ERROR: Failed to create any tickets. Errors:\n{error_summary}")
                return {
                    "status": "error",
                    "error": f"Failed to create any tickets. All attempts resulted in errors.\n\nErrors:\n{error_summary}",
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
    """Create tickets for multiple doctors (top N ranked doctors from config).
    
    Args:
        patient_id: Patient UUID
        conversation_id: Conversation UUID
        ranked_doctors: List of ranked doctor dictionaries (from rank_doctors_with_llm result - MUST be the ranked_doctors list from the tool result)
        service_type: Service type string
        description: Description of the patient's request
        patient_details: Full patient details dictionary
        past_history_summary: Formatted patient history summary
        llm_summary: LLM-generated summary
        priority: Ticket priority (1-5, default 3)
    
    Returns:
        Dictionary with status, tickets_created count, and tickets list
    
    IMPORTANT: ranked_doctors MUST be the list from rank_doctors_with_llm result. Each doctor dict must have:
    - doctor_id (string UUID)
    - name (string)
    - rank (integer)
    - reason (string)
    """
    print(f"DEBUG: create_multiple_tickets called with:")
    print(f"  - patient_id: {patient_id}")
    print(f"  - conversation_id: {conversation_id}")
    print(f"  - ranked_doctors type: {type(ranked_doctors)}, length: {len(ranked_doctors) if ranked_doctors else 0}")
    print(f"  - ranked_doctors value: {ranked_doctors}")
    print(f"  - service_type: {service_type}")
    print(f"  - description received: '{description}'")
    print(f"  - llm_summary received: '{llm_summary[:100] if llm_summary else 'None'}...'")
    
    # Clean up description if it contains time references (in case LLM didn't follow instructions)
    import re
    time_patterns = [
        r'\b(?:tomorrow|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week))\b',
        r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+\d+:\d+\s*(?:AM|PM|am|pm)\b',
        r'\bat\s+\d+:\d+\s*(?:AM|PM|am|pm)\b',
        r'\(Preferred appointment time:.*?\)',
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
    ]
    original_description = description
    for pattern in time_patterns:
        description = re.sub(pattern, '', description, flags=re.IGNORECASE)
    description = description.strip().replace('  ', ' ').replace(', ,', ',').strip()
    if not description or len(description) < 3:
        description = "Patient request"
    if original_description != description:
        print(f"DEBUG: Cleaned description from '{original_description}' to '{description}'")
    
    # Validate ranked_doctors
    if not ranked_doctors:
        print(f"ERROR: ranked_doctors is empty or None!")
        return {
            "status": "error",
            "error": "No ranked doctors provided. ranked_doctors parameter is empty. Make sure you pass the ranked_doctors list from the rank_doctors_with_llm tool result.",
            "tickets_created": 0,
            "tickets": []
        }
    
    if not isinstance(ranked_doctors, list):
        print(f"ERROR: ranked_doctors is not a list! Type: {type(ranked_doctors)}")
        return {
            "status": "error",
            "error": f"ranked_doctors must be a list, but got {type(ranked_doctors)}. Make sure you pass the ranked_doctors list from the rank_doctors_with_llm tool result.",
            "tickets_created": 0,
            "tickets": []
        }
    
    # Validate each doctor has required fields
    for i, doctor in enumerate(ranked_doctors):
        if not isinstance(doctor, dict):
            print(f"ERROR: Doctor at index {i} is not a dict: {doctor}")
            return {
                "status": "error",
                "error": f"Doctor at index {i} is not a dictionary. Each doctor must be a dict with doctor_id, name, rank, and reason.",
                "tickets_created": 0,
                "tickets": []
            }
        required_fields = ["doctor_id", "name", "rank"]
        missing_fields = [field for field in required_fields if field not in doctor]
        if missing_fields:
            print(f"ERROR: Doctor at index {i} missing fields: {missing_fields}")
            return {
                "status": "error",
                "error": f"Doctor at index {i} is missing required fields: {missing_fields}. Each doctor must have doctor_id, name, and rank.",
                "tickets_created": 0,
                "tickets": []
            }
    
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
        error_msg = f"Exception in create_multiple_tickets: {str(e)}\n{traceback.format_exc()}"
        print(f"ERROR: {error_msg}")
        return {"status": "error", "error": error_msg}

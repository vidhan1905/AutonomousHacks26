"""LangGraph tools for appointment operations."""
from typing import Optional
from langchain_core.tools import tool
from datetime import datetime, timedelta
from backend.src.database.models import Appointment
from backend.src.database.connection import async_session_maker
import uuid
import asyncio
import concurrent.futures


async def _schedule_appointment_async(
    patient_id: str, service_type: str, preferred_date: str,
    notes: Optional[str] = None, ticket_id: Optional[str] = None,
    service_person_id: Optional[str] = None,
    session_maker=None
) -> dict:
    """Async implementation of schedule_appointment."""
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            scheduled_date = datetime.fromisoformat(preferred_date.replace("Z", "+00:00"))
            appointment = Appointment(
                patient_id=uuid.UUID(patient_id),
                service_type=service_type,
                scheduled_date=scheduled_date,
                notes=notes,
                appointment_type="consultation",
                status="scheduled"
            )
            if ticket_id:
                appointment.ticket_id = uuid.UUID(ticket_id)
            if service_person_id:
                appointment.service_person_id = uuid.UUID(service_person_id)
            
            session.add(appointment)
            await session.commit()
            await session.refresh(appointment)
            return {
                "appointment_id": str(appointment.appointment_id),
                "status": "scheduled",
                "scheduled_date": preferred_date
            }
        except Exception as e:
            await session.rollback()
            return {"status": "error", "error": str(e)}


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
        return future.result(timeout=10)


@tool
def schedule_appointment(
    patient_id: str, service_type: str, preferred_date: str,
    notes: Optional[str] = None, ticket_id: Optional[str] = None,
    service_person_id: Optional[str] = None
) -> dict:
    """Schedule an appointment for a patient.
    
    Args:
        patient_id: Patient UUID
        service_type: Type of service (general_consultation, cardiology, etc.)
        preferred_date: Preferred date/time in ISO format (e.g., "2025-01-17T10:00:00")
        notes: Optional notes about the appointment
        ticket_id: Optional ticket ID if this appointment is related to a ticket
        service_person_id: Optional service person ID to assign to
    
    Returns:
        dict with appointment_id, status, scheduled_date
    """
    try:
        # Parse and validate date
        try:
            # Handle various date formats
            if "next week" in preferred_date.lower() or "next week" in (notes or "").lower():
                # Calculate next week's date (7 days from now, same time)
                next_week = datetime.now() + timedelta(days=7)
                preferred_date = next_week.strftime("%Y-%m-%dT10:00:00")
            elif "tomorrow" in preferred_date.lower():
                tomorrow = datetime.now() + timedelta(days=1)
                preferred_date = tomorrow.strftime("%Y-%m-%dT10:00:00")
            elif "today" in preferred_date.lower():
                preferred_date = datetime.now().strftime("%Y-%m-%dT10:00:00")
            
            return run_async_safely(
                _schedule_appointment_async,
                patient_id, service_type, preferred_date, notes, ticket_id, service_person_id,
                session_maker_param=True
            )
        except Exception as e:
            import traceback
            return {"status": "error", "error": f"Exception in schedule_appointment: {str(e)}\n{traceback.format_exc()}"}
    except Exception as e:
        import traceback
        return {"status": "error", "error": f"Exception in schedule_appointment: {str(e)}\n{traceback.format_exc()}"}

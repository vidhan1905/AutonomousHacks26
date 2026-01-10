"""LangGraph tools for ticket operations."""
from typing import Optional
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.src.database.models import Ticket, TicketUpdate
from backend.src.database.connection import async_session_maker
import uuid
import asyncio
import concurrent.futures


async def _create_ticket_async(
    patient_id: str, conversation_id: str, service_type: str,
    description: str, priority: int, patient_details: dict,
    past_history_summary: str, llm_summary: str,
    current_symptoms: Optional[dict] = None,
    session_maker=None
) -> dict:
    """Async implementation of create_ticket."""
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            ticket = Ticket(
                conversation_id=uuid.UUID(conversation_id),
                patient_id=uuid.UUID(patient_id),
                service_type=service_type,
                description=description,
                priority=priority,
                patient_details=patient_details,
                past_history_summary=past_history_summary,
                llm_summary=llm_summary,
                current_symptoms=current_symptoms or {}
            )
            session.add(ticket)
            await session.commit()
            await session.refresh(ticket)
            return {
                "ticket_id": str(ticket.ticket_id),
                "status": "created",
                "service_type": service_type,
                "priority": priority
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
def create_ticket(
    patient_id: str, conversation_id: str, service_type: str,
    description: str, priority: int, patient_details: dict,
    past_history_summary: str, llm_summary: str,
    current_symptoms: Optional[dict] = None
) -> dict:
    """Create a new ticket with comprehensive patient information.
    
    Use this when a patient needs a service like blood test, lab test, imaging, etc.
    Do NOT use this for scheduling appointments - use schedule_appointment instead.
    """
    try:
        return run_async_safely(
            _create_ticket_async,
            patient_id, conversation_id, service_type, description,
            priority, patient_details, past_history_summary,
            llm_summary, current_symptoms,
            session_maker_param=True
        )
    except Exception as e:
        import traceback
        return {"status": "error", "error": f"Exception in create_ticket: {str(e)}\n{traceback.format_exc()}"}


async def _update_ticket_status_async(ticket_id: str, status: str, updated_by: str, session_maker=None) -> dict:
    """Async implementation of update_ticket_status."""
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            result = await session.execute(
                select(Ticket).where(Ticket.ticket_id == uuid.UUID(ticket_id))
            )
            ticket = result.scalar_one_or_none()
            if not ticket:
                return {"status": "error", "error": "Ticket not found"}
            
            old_status = ticket.status
            ticket.status = status
            
            update = TicketUpdate(
                ticket_id=uuid.UUID(ticket_id),
                updated_by=uuid.UUID(updated_by),
                update_type="status_change",
                old_value=old_status,
                new_value=status
            )
            session.add(update)
            await session.commit()
            return {"status": "updated", "ticket_id": ticket_id, "new_status": status}
        except Exception as e:
            await session.rollback()
            return {"status": "error", "error": str(e)}


@tool
def update_ticket_status(ticket_id: str, status: str, updated_by: str) -> dict:
    """Update ticket status."""
    try:
        return run_async_safely(
            _update_ticket_status_async,
            ticket_id, status, updated_by,
            session_maker_param=True
        )
    except Exception as e:
        import traceback
        return {"status": "error", "error": f"Exception in update_ticket_status: {str(e)}\n{traceback.format_exc()}"}


@tool
def validate_required_fields(collected_info: dict) -> dict:
    """Validate that required fields are present."""
    required = ["name", "phone", "date_of_birth"]
    missing = [field for field in required if not collected_info.get(field)]
    return {
        "all_present": len(missing) == 0,
        "missing_fields": missing
    }

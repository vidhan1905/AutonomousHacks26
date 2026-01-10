"""Ticket service operations."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid
from datetime import datetime
import logging
from backend.src.database.models import Ticket, TicketUpdate
from backend.src.utils.category_normalizer import normalize_category_value

logger = logging.getLogger(__name__)


async def get_ticket_by_id(db: AsyncSession, ticket_id: str) -> Optional[Ticket]:
    """Get ticket by ID."""
    result = await db.execute(
        select(Ticket).where(Ticket.ticket_id == uuid.UUID(ticket_id))
    )
    return result.scalar_one_or_none()


async def list_tickets(
    db: AsyncSession,
    patient_id: Optional[str] = None,
    service_person_id: Optional[str] = None,
    status: Optional[str] = None
) -> list[Ticket]:
    """List tickets with filters."""
    query = select(Ticket)
    
    if patient_id:
        query = query.where(Ticket.patient_id == uuid.UUID(patient_id))
    if service_person_id:
        query = query.where(Ticket.assigned_to == uuid.UUID(service_person_id))
    if status:
        try:
            normalized_status = await normalize_category_value(
                table_name="tickets",
                column_name="status",
                user_input=status,
                context="Listing tickets by status"
            )
            query = query.where(Ticket.status == normalized_status)
        except Exception as e:
            logger.warning(f"Failed to normalize status '{status}': {e}. Using original value.")
            query = query.where(Ticket.status == status)
    
    result = await db.execute(query.order_by(Ticket.created_at.desc()))
    return list(result.scalars().all())

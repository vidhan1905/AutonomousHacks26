"""Ticket management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime

from backend.src.database.connection import get_db
from backend.src.database.models import Ticket, TicketUpdate
from backend.src.api.dependencies import (
    get_current_user,
    get_current_service_person,
    get_current_admin
)
from backend.src.database.models import ServicePerson

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


class AssignTicketRequest(BaseModel):
    service_person_id: str


class UpdateTicketStatusRequest(BaseModel):
    status: str  # "open", "assigned", "in_progress", "completed", "cancelled"


class AddCommentRequest(BaseModel):
    comment: str


@router.get("")
async def list_tickets(
    status: Optional[str] = Query(None),
    service_type: Optional[str] = Query(None),
    priority: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List tickets (filtered by user role)."""
    user = current_user["user"]
    user_type = current_user["type"]
    
    query = select(Ticket)
    
    # Filter based on user type
    if user_type == "patient":
        query = query.where(Ticket.patient_id == user.patient_id)
    elif user_type == "service_person":
        # Service persons see assigned tickets and available tickets
        query = query.where(
            or_(
                Ticket.assigned_to == user.service_person_id,
                Ticket.status == "open"
            )
        )
    # Admins see all tickets
    
    # Apply filters
    if status:
        query = query.where(Ticket.status == status)
    if service_type:
        query = query.where(Ticket.service_type == service_type)
    if priority:
        query = query.where(Ticket.priority == priority)
    
    result = await db.execute(query.order_by(Ticket.created_at.desc()))
    tickets = result.scalars().all()
    
    return [
        {
            "ticket_id": str(ticket.ticket_id),
            "conversation_id": str(ticket.conversation_id),
            "patient_id": str(ticket.patient_id),
            "service_type": ticket.service_type,
            "status": ticket.status,
            "priority": ticket.priority,
            "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
            "description": ticket.description,
            "created_at": ticket.created_at.isoformat()
        }
        for ticket in tickets
    ]


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get ticket details."""
    result = await db.execute(
        select(Ticket).where(Ticket.ticket_id == uuid.UUID(ticket_id))
    )
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    user = current_user["user"]
    user_type = current_user["type"]
    
    # Check access
    if user_type == "patient" and ticket.patient_id != user.patient_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "ticket_id": str(ticket.ticket_id),
        "conversation_id": str(ticket.conversation_id),
        "patient_id": str(ticket.patient_id),
        "service_type": ticket.service_type,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
        "description": ticket.description,
        "patient_details": ticket.patient_details,
        "past_history_summary": ticket.past_history_summary,
        "llm_summary": ticket.llm_summary,
        "current_symptoms": ticket.current_symptoms,
        "created_at": ticket.created_at.isoformat(),
        "assigned_at": ticket.assigned_at.isoformat() if ticket.assigned_at else None,
        "completed_at": ticket.completed_at.isoformat() if ticket.completed_at else None
    }


@router.put("/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: str,
    request: AssignTicketRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Assign ticket to a service person."""
    user_type = current_user["type"]
    if user_type not in ["service_person", "admin"]:
        raise HTTPException(status_code=403, detail="Only service persons and admins can assign tickets")
    
    # Get ticket
    result = await db.execute(
        select(Ticket).where(Ticket.ticket_id == uuid.UUID(ticket_id))
    )
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Verify service person exists
    service_person_result = await db.execute(
        select(ServicePerson).where(ServicePerson.service_person_id == uuid.UUID(request.service_person_id))
    )
    service_person = service_person_result.scalar_one_or_none()
    
    if not service_person:
        raise HTTPException(status_code=404, detail="Service person not found")
    
    # Assign ticket
    ticket.assigned_to = uuid.UUID(request.service_person_id)
    ticket.status = "assigned"
    ticket.assigned_at = datetime.utcnow()
    
    # Create update record
    update = TicketUpdate(
        ticket_id=uuid.UUID(ticket_id),
        updated_by=uuid.UUID(str(current_user["user"].service_person_id if user_type == "service_person" else current_user["user"].admin_id)),
        update_type="assignment",
        new_value=request.service_person_id,
        comment=f"Ticket assigned to {service_person.name}"
    )
    db.add(update)
    
    await db.commit()
    await db.refresh(ticket)
    
    return {
        "ticket_id": str(ticket.ticket_id),
        "status": "assigned",
        "assigned_to": request.service_person_id,
        "assigned_at": ticket.assigned_at.isoformat()
    }


@router.put("/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: str,
    request: UpdateTicketStatusRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update ticket status."""
    user_type = current_user["type"]
    if user_type not in ["service_person", "admin"]:
        raise HTTPException(status_code=403, detail="Only service persons and admins can update ticket status")
    
    valid_statuses = ["open", "assigned", "in_progress", "completed", "cancelled"]
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    # Get ticket
    result = await db.execute(
        select(Ticket).where(Ticket.ticket_id == uuid.UUID(ticket_id))
    )
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    old_status = ticket.status
    ticket.status = request.status
    
    if request.status == "completed":
        ticket.completed_at = datetime.utcnow()
    
    # Create update record
    update = TicketUpdate(
        ticket_id=uuid.UUID(ticket_id),
        updated_by=uuid.UUID(str(current_user["user"].service_person_id if user_type == "service_person" else current_user["user"].admin_id)),
        update_type="status_change",
        old_value=old_status,
        new_value=request.status
    )
    db.add(update)
    
    await db.commit()
    await db.refresh(ticket)
    
    return {
        "ticket_id": str(ticket.ticket_id),
        "status": ticket.status,
        "completed_at": ticket.completed_at.isoformat() if ticket.completed_at else None
    }


@router.post("/{ticket_id}/comments")
async def add_comment(
    ticket_id: str,
    request: AddCommentRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a comment/update to a ticket."""
    user_type = current_user["type"]
    if user_type not in ["service_person", "admin"]:
        raise HTTPException(status_code=403, detail="Only service persons and admins can add comments")
    
    # Get ticket
    result = await db.execute(
        select(Ticket).where(Ticket.ticket_id == uuid.UUID(ticket_id))
    )
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Create update record
    update = TicketUpdate(
        ticket_id=uuid.UUID(ticket_id),
        updated_by=uuid.UUID(str(current_user["user"].service_person_id if user_type == "service_person" else current_user["user"].admin_id)),
        update_type="comment",
        comment=request.comment
    )
    db.add(update)
    
    await db.commit()
    
    return {
        "update_id": str(update.update_id),
        "comment": request.comment,
        "created_at": update.created_at.isoformat()
    }

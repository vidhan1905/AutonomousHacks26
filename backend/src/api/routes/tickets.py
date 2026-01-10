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


class AcceptRejectTicketRequest(BaseModel):
    action: str  # "accept" or "reject"


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
        # Service persons ONLY see tickets assigned to them (excluding cancelled)
        # Ensure both are UUID objects for proper comparison
        service_person_uuid = user.service_person_id
        if isinstance(service_person_uuid, str):
            service_person_uuid = uuid.UUID(service_person_uuid)
        
        print(f"DEBUG list_tickets: Filtering tickets for service_person_id: {service_person_uuid} (type: {type(service_person_uuid)})")
        
        query = query.where(
            Ticket.assigned_to == service_person_uuid,
            Ticket.status != "cancelled"
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
    
    # Debug logging and verification for service persons
    if user_type == "service_person":
        print(f"DEBUG list_tickets: Found {len(tickets)} tickets")
        verified_tickets = []
        for ticket in tickets:
            ticket_assigned_uuid = ticket.assigned_to
            if isinstance(ticket_assigned_uuid, str):
                ticket_assigned_uuid = uuid.UUID(ticket_assigned_uuid)
            
            # Verify the ticket is actually assigned to this user (safety check)
            if ticket_assigned_uuid == service_person_uuid:
                verified_tickets.append(ticket)
                print(f"  - Ticket {ticket.ticket_id}: assigned_to={ticket.assigned_to} (type: {type(ticket.assigned_to)}), status={ticket.status} ✓")
            else:
                print(f"  - WARNING: Ticket {ticket.ticket_id} assigned_to={ticket.assigned_to} does NOT match service_person_id={service_person_uuid} - FILTERING OUT")
        tickets = verified_tickets
    
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


@router.post("/{ticket_id}/accept-reject")
async def accept_reject_ticket(
    ticket_id: str,
    request: AcceptRejectTicketRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Accept or reject a ticket. When accepted, cancels other related tickets."""
    user_type = current_user["type"]
    if user_type != "service_person":
        raise HTTPException(status_code=403, detail="Only service persons can accept/reject tickets")
    
    if request.action not in ["accept", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'accept' or 'reject'")
    
    # Get ticket
    result = await db.execute(
        select(Ticket).where(Ticket.ticket_id == uuid.UUID(ticket_id))
    )
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Verify ticket is assigned to this service person
    # Compare UUIDs properly - convert both to UUID if needed
    current_service_person_id = current_user["user"].service_person_id
    ticket_assigned_to = ticket.assigned_to
    
    # Debug logging
    print(f"DEBUG accept_reject_ticket:")
    print(f"  - current_service_person_id: {current_service_person_id} (type: {type(current_service_person_id)})")
    print(f"  - ticket_assigned_to: {ticket_assigned_to} (type: {type(ticket_assigned_to)})")
    print(f"  - ticket_id: {ticket_id}")
    print(f"  - ticket status: {ticket.status}")
    
    # Check if ticket is assigned
    if ticket_assigned_to is None:
        raise HTTPException(status_code=400, detail="Ticket is not assigned to anyone. Cannot accept/reject unassigned ticket.")
    
    # Ensure both are UUID objects for comparison
    if isinstance(current_service_person_id, str):
        current_service_person_id = uuid.UUID(current_service_person_id)
    if isinstance(ticket_assigned_to, str):
        ticket_assigned_to = uuid.UUID(ticket_assigned_to)
    
    # Normalize both to UUID strings for comparison (most reliable)
    current_id_str = str(current_service_person_id) if current_service_person_id else None
    ticket_id_str = str(ticket_assigned_to) if ticket_assigned_to else None
    
    print(f"  - After UUID conversion:")
    print(f"    - current_service_person_id: {current_service_person_id} (type: {type(current_service_person_id)})")
    print(f"    - ticket_assigned_to: {ticket_assigned_to} (type: {type(ticket_assigned_to)})")
    print(f"    - current_id_str: {current_id_str}")
    print(f"    - ticket_id_str: {ticket_id_str}")
    print(f"    - UUID comparison: {ticket_assigned_to == current_service_person_id}")
    print(f"    - String comparison: {current_id_str == ticket_id_str}")
    
    # Compare as UUIDs first, then fallback to strings
    if ticket_assigned_to != current_service_person_id:
        raise HTTPException(
            status_code=403, 
            detail=f"You can only accept/reject tickets assigned to you. Ticket is assigned to {ticket_id_str}, but you are {current_id_str}"
        )
    
    # Verify ticket is in open status
    if ticket.status != "open":
        raise HTTPException(status_code=400, detail=f"Ticket is already {ticket.status}. Cannot accept/reject.")
    
    service_person_id = current_user["user"].service_person_id
    
    if request.action == "accept":
        # Accept ticket: change status to "assigned" and cancel other related tickets
        ticket.status = "assigned"
        ticket.assigned_at = datetime.utcnow()
        
        # Find and cancel other tickets from the same conversation with same service_type
        # These are the other 4 doctors' tickets
        other_tickets_result = await db.execute(
            select(Ticket).where(
                Ticket.conversation_id == ticket.conversation_id,
                Ticket.service_type == ticket.service_type,
                Ticket.ticket_id != uuid.UUID(ticket_id),
                Ticket.status == "open"
            )
        )
        other_tickets = other_tickets_result.scalars().all()
        
        # Cancel all other tickets
        for other_ticket in other_tickets:
            other_ticket.status = "cancelled"
            # Create update record for cancellation
            cancel_update = TicketUpdate(
                ticket_id=other_ticket.ticket_id,
                updated_by=service_person_id,
                update_type="status_change",
                old_value="open",
                new_value="cancelled",
                comment=f"Ticket cancelled because another doctor accepted the case"
            )
            db.add(cancel_update)
        
        # Create update record for acceptance
        accept_update = TicketUpdate(
            ticket_id=uuid.UUID(ticket_id),
            updated_by=service_person_id,
            update_type="status_change",
            old_value="open",
            new_value="assigned",
            comment="Ticket accepted by doctor"
        )
        db.add(accept_update)
        
        await db.commit()
        await db.refresh(ticket)
        
        return {
            "ticket_id": str(ticket.ticket_id),
            "status": "assigned",
            "action": "accepted",
            "cancelled_tickets": len(other_tickets),
            "assigned_at": ticket.assigned_at.isoformat()
        }
    
    else:  # reject
        # Reject ticket: cancel this ticket
        ticket.status = "cancelled"
        
        # Create update record
        reject_update = TicketUpdate(
            ticket_id=uuid.UUID(ticket_id),
            updated_by=service_person_id,
            update_type="status_change",
            old_value="open",
            new_value="cancelled",
            comment="Ticket rejected by doctor"
        )
        db.add(reject_update)
        
        await db.commit()
        await db.refresh(ticket)
        
        return {
            "ticket_id": str(ticket.ticket_id),
            "status": "cancelled",
            "action": "rejected"
        }

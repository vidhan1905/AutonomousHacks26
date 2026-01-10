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
    try:
        if user_type == "patient":
            query = query.where(Ticket.patient_id == user.patient_id)
        elif user_type == "service_person":
            # Service persons see tickets assigned to them OR offered to them (via assignment_status)
            # Check both assigned_to and accepted_by for service person
            query = query.where(
                (Ticket.assigned_to == user.service_person_id) | 
                (Ticket.accepted_by == user.service_person_id),
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
    except AttributeError as e:
        # Schema error - column may not exist
        import traceback
        error_msg = f"SCHEMA ERROR: Ticket model column may not exist. Error: {str(e)}\n{traceback.format_exc()}"
        print(f"[SCHEMA ERROR] {error_msg}")
        raise HTTPException(status_code=500, detail=f"Database schema issue: {error_msg}")
    except Exception as e:
        import traceback
        error_msg = f"Database query error: {str(e)}\n{traceback.format_exc()}"
        print(f"[ERROR] {error_msg}")
        raise HTTPException(status_code=500, detail=f"Database error: {error_msg}")
    
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
            "assignment_status": ticket.assignment_status,
            "accepted_by": str(ticket.accepted_by) if ticket.accepted_by else None,
            "accepted_at": ticket.accepted_at.isoformat() if ticket.accepted_at else None,
            "offered_to_count": ticket.offered_to_count,
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
    
    case_summary = None
    if ticket.llm_summary and ticket.llm_summary.startswith("CASE SUMMARY:"):
        try:
            # Extract case summary (between "CASE SUMMARY:\n" and "\n\n")
            parts = ticket.llm_summary.split("\n\n", 1)
            if len(parts) > 1:
                case_summary = parts[0].replace("CASE SUMMARY:\n", "").strip()
        except Exception:
            pass  # If extraction fails, case_summary remains None
    
    return {
        "ticket_id": str(ticket.ticket_id),
        "conversation_id": str(ticket.conversation_id),
        "patient_id": str(ticket.patient_id),
        "service_type": ticket.service_type,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
        "description": ticket.description,  # Contains issue description (e.g., "Patient has cold")
        "patient_details": ticket.patient_details,  # Contains: name, phone, DOB, gender, blood_group, emergency_contact, medical_history
        "past_history_summary": ticket.past_history_summary,
        "llm_summary": ticket.llm_summary,
        "case_summary": case_summary,  # ROOT FIX: Extracted case summary for UI display
        "current_symptoms": ticket.current_symptoms,
        "assignment_status": ticket.assignment_status,
        "accepted_by": str(ticket.accepted_by) if ticket.accepted_by else None,
        "accepted_at": ticket.accepted_at.isoformat() if ticket.accepted_at else None,
        "offered_to_count": ticket.offered_to_count,
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
    
    valid_statuses = ["open", "assigned", "in_progress", "completed", "cancelled", "offered"]
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
    
    # Verify ticket is assigned/offered to this service person
    # Check both assigned_to (initial assignment) and accepted_by (if already accepted by someone else)
    service_person_id = current_user["user"].service_person_id
    if ticket.assigned_to != service_person_id:
        # Also check if this ticket was offered to them via assignment_status
        if hasattr(ticket, 'assignment_status') and ticket.assignment_status != "offered":
            raise HTTPException(status_code=403, detail="You can only accept/reject tickets assigned/offered to you")
        elif not hasattr(ticket, 'assignment_status'):
            # Fallback for older schema
            raise HTTPException(status_code=403, detail="You can only accept/reject tickets assigned to you")
    
    # Verify ticket is in open status or offered status (for new workflow)
    if ticket.status not in ["open", "offered"]:
        raise HTTPException(status_code=400, detail=f"Ticket is already {ticket.status}. Cannot accept/reject.")
    
    service_person_id = current_user["user"].service_person_id
    
    if request.action == "accept":
        # Accept ticket: change status to "assigned" and cancel other related tickets
        ticket.status = "assigned"
        ticket.assigned_at = datetime.utcnow()
        # Update new workflow fields
        ticket.assignment_status = "accepted"
        ticket.accepted_by = service_person_id
        ticket.accepted_at = datetime.utcnow()
        
        # Find and cancel other tickets from the same conversation with same service_type
        # These are the other 4 doctors' tickets
        # Filter by assignment_status to find tickets that were "offered" but not yet accepted
        try:
            other_tickets_result = await db.execute(
                select(Ticket).where(
                    Ticket.conversation_id == ticket.conversation_id,
                    Ticket.service_type == ticket.service_type,
                    Ticket.ticket_id != uuid.UUID(ticket_id),
                    Ticket.status == "open",
                    Ticket.assignment_status.in_(["offered", "unassigned"])  # Only cancel tickets that were offered/not accepted yet
                )
            )
            other_tickets = other_tickets_result.scalars().all()
        except AttributeError as e:
            # Fallback if assignment_status column doesn't exist (backwards compatibility)
            print(f"[WARNING] assignment_status column may not exist, using fallback query: {e}")
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
            # Update assignment_status if needed
            if other_ticket.assignment_status == "offered":
                other_ticket.assignment_status = "rejected_all"  # Mark as rejected since another doctor accepted
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
        ticket.assignment_status = "rejected_all"  # Mark this doctor's offer as rejected
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

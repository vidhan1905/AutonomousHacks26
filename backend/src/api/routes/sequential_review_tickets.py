"""Sequential review ticket management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime

from backend.src.database.connection import get_db
from backend.src.database.models import (
    SequentialReviewTicket,
    SequentialReviewChain,
    SequentialReviewStep,
    ServicePerson
)
from backend.src.api.dependencies import (
    get_current_user,
    get_current_service_person,
    get_current_admin
)

router = APIRouter(prefix="/api/sequential-review-tickets", tags=["sequential-review-tickets"])


class AcceptStepRequest(BaseModel):
    pass  # No additional fields needed


class RejectStepRequest(BaseModel):
    reason: Optional[str] = None


class UpdateStepStatusRequest(BaseModel):
    status: str  # "step_accepted", "step_in_progress", "step_completed"
    review_notes: Optional[str] = None


@router.get("")
async def list_sequential_review_tickets(
    status: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List sequential review tickets (filtered by user role)."""
    try:
        user = current_user["user"]
        user_type = current_user["type"]
        
        query = select(SequentialReviewTicket)
        
        # Filter based on user type
        if user_type == "patient":
            query = query.where(SequentialReviewTicket.patient_id == user.patient_id)
        elif user_type == "service_person":
            # Service persons see tickets where they are assigned to the step
            # Join on step_id to get the step's doctor_id
            query = query.join(
                SequentialReviewStep,
                SequentialReviewTicket.step_id == SequentialReviewStep.step_id
            ).where(
                SequentialReviewStep.doctor_id == user.service_person_id,
                SequentialReviewTicket.status != "chain_cancelled"
            )
        # Admins see all tickets
        
        # Apply status filter
        if status:
            query = query.where(SequentialReviewTicket.status == status)
        
        result = await db.execute(query.order_by(SequentialReviewTicket.chain_id, SequentialReviewTicket.step_index))
        tickets = result.scalars().all()
    except Exception as e:
        # If table doesn't exist or other error, return empty list
        import traceback
        print(f"[ERROR] Failed to list sequential review tickets: {e}")
        print(traceback.format_exc())
        tickets = []
    
    return [
        {
            "ticket_id": str(ticket.ticket_id),
            "chain_id": str(ticket.chain_id),
            "conversation_id": str(ticket.conversation_id),
            "patient_id": str(ticket.patient_id),
            "status": ticket.status,
            "step_id": str(ticket.step_id),
            "step_index": ticket.step_index,
            "can_start": ticket.can_start,
            "description": ticket.description,
            "llm_summary": ticket.llm_summary,
            "patient_details": ticket.patient_details,
            "past_history_summary": ticket.past_history_summary,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
            "chain_completed_at": ticket.chain_completed_at.isoformat() if ticket.chain_completed_at else None,
        }
        for ticket in tickets
    ]


@router.get("/{ticket_id}")
async def get_sequential_review_ticket(
    ticket_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get sequential review ticket details."""
    result = await db.execute(
        select(SequentialReviewTicket).where(
            SequentialReviewTicket.ticket_id == uuid.UUID(ticket_id)
        )
    )
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Sequential review ticket not found")
    
    user = current_user["user"]
    user_type = current_user["type"]
    
    # Check access
    if user_type == "patient" and ticket.patient_id != user.patient_id:
        raise HTTPException(status_code=403, detail="Access denied")
    elif user_type == "service_person":
        # Check if user is assigned to this step
        step_result = await db.execute(
            select(SequentialReviewStep).where(
                SequentialReviewStep.step_id == ticket.step_id
            )
        )
        step = step_result.scalar_one_or_none()
        if not step or step.doctor_id != user.service_person_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Get step details
    step_result = await db.execute(
        select(SequentialReviewStep).where(
            SequentialReviewStep.step_id == ticket.step_id
        )
    )
    step = step_result.scalar_one_or_none()
    current_step = None
    if step:
        doctor_result = await db.execute(
            select(ServicePerson).where(ServicePerson.service_person_id == step.doctor_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        current_step = {
            "step_id": str(step.step_id),
            "step_index": step.step_index,
            "doctor_id": str(step.doctor_id),
            "doctor_name": doctor.name if doctor else "Unknown",
            "service_type": doctor.service_type if doctor else "",
            "status": step.status,
            "review_notes": step.review_notes,
            "review_summary": step.review_summary,
        }
    
    return {
        "ticket_id": str(ticket.ticket_id),
        "chain_id": str(ticket.chain_id),
        "conversation_id": str(ticket.conversation_id),
        "patient_id": str(ticket.patient_id),
        "status": ticket.status,
        "step_id": str(ticket.step_id),
        "step_index": ticket.step_index,
        "can_start": ticket.can_start,
        "current_step": current_step,  # Keep for backward compatibility
        "description": ticket.description,
        "llm_summary": ticket.llm_summary,
        "patient_details": ticket.patient_details,
        "past_history_summary": ticket.past_history_summary,
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
        "chain_completed_at": ticket.chain_completed_at.isoformat() if ticket.chain_completed_at else None,
    }


@router.get("/{ticket_id}/progress")
async def get_ticket_progress(
    ticket_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get sequential review progress for a ticket."""
    # Get ticket
    ticket_result = await db.execute(
        select(SequentialReviewTicket).where(
            SequentialReviewTicket.ticket_id == uuid.UUID(ticket_id)
        )
    )
    ticket = ticket_result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Sequential review ticket not found")
    
    # Get chain and steps
    chain_result = await db.execute(
        select(SequentialReviewChain).where(
            SequentialReviewChain.chain_id == ticket.chain_id
        )
    )
    chain = chain_result.scalar_one_or_none()
    
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    
    # Get all steps
    steps_result = await db.execute(
        select(SequentialReviewStep).where(
            SequentialReviewStep.chain_id == chain.chain_id
        ).order_by(SequentialReviewStep.step_index)
    )
    steps = steps_result.scalars().all()
    
    # Build progress data
    steps_progress = []
    for step in steps:
        doctor_result = await db.execute(
            select(ServicePerson).where(ServicePerson.service_person_id == step.doctor_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        
        steps_progress.append({
            "step_number": step.step_index + 1,
            "doctor_name": doctor.name if doctor else "Unknown",
            "service_type": doctor.service_type if doctor else "",
            "status": step.status,  # pending, in_review, completed
            "completed_at": step.completed_at.isoformat() if step.completed_at else None,
            "review_summary": step.review_summary,
            "review_notes": step.review_notes
        })
    
    completed_count = sum(1 for s in steps if s.status == "completed")
    
    return {
        "total_steps": chain.required_doctors_count,
        "current_step": chain.current_step_index + 1,
        "completed_steps": completed_count,
        "steps": steps_progress
    }


@router.post("/{ticket_id}/accept-step")
async def accept_step(
    ticket_id: str,
    request: AcceptStepRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Accept current step in sequential review."""
    user_type = current_user["type"]
    if user_type != "service_person":
        raise HTTPException(status_code=403, detail="Only service persons can accept steps")
    
    # Get ticket
    ticket_result = await db.execute(
        select(SequentialReviewTicket).where(
            SequentialReviewTicket.ticket_id == uuid.UUID(ticket_id)
        )
    )
    ticket = ticket_result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Sequential review ticket not found")
    
    if ticket.status != "step_pending":
        raise HTTPException(status_code=400, detail=f"Step is not pending. Current status: {ticket.status}")
    
    # Check if step can be started
    if not ticket.can_start:
        raise HTTPException(
            status_code=400,
            detail="This step cannot be started yet. Please wait for the previous doctor to complete their review."
        )
    
    # Get step
    step_result = await db.execute(
        select(SequentialReviewStep).where(
            SequentialReviewStep.step_id == ticket.step_id
        )
    )
    step = step_result.scalar_one_or_none()
    
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    # Verify doctor is assigned to this step
    service_person_id = current_user["user"].service_person_id
    if step.doctor_id != service_person_id:
        raise HTTPException(status_code=403, detail="You are not assigned to this step")
    
    # Update step and ticket status
    step.status = "in_review"
    step.started_at = datetime.utcnow()
    ticket.status = "step_accepted"
    
    # Note: SequentialReviewTicket doesn't use TicketUpdate (it's for regular tickets)
    # Status changes are tracked via the ticket.status and step.status fields
    
    await db.commit()
    await db.refresh(ticket)
    
    return {
        "ticket_id": str(ticket.ticket_id),
        "status": ticket.status,
        "step_status": step.status
    }


@router.post("/{ticket_id}/reject-step")
async def reject_step(
    ticket_id: str,
    request: RejectStepRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reject current step in sequential review."""
    user_type = current_user["type"]
    if user_type != "service_person":
        raise HTTPException(status_code=403, detail="Only service persons can reject steps")
    
    # Get ticket
    ticket_result = await db.execute(
        select(SequentialReviewTicket).where(
            SequentialReviewTicket.ticket_id == uuid.UUID(ticket_id)
        )
    )
    ticket = ticket_result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Sequential review ticket not found")
    
    if ticket.status != "step_pending":
        raise HTTPException(status_code=400, detail=f"Step is not pending. Current status: {ticket.status}")
    
    # Get step
    step_result = await db.execute(
        select(SequentialReviewStep).where(
            SequentialReviewStep.step_id == ticket.step_id
        )
    )
    step = step_result.scalar_one_or_none()
    
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    # Verify doctor is assigned to this step
    service_person_id = current_user["user"].service_person_id
    if step.doctor_id != service_person_id:
        raise HTTPException(status_code=403, detail="You are not assigned to this step")
    
    # Get chain to check if this is the last step
    chain_result = await db.execute(
        select(SequentialReviewChain).where(
            SequentialReviewChain.chain_id == ticket.chain_id
        )
    )
    chain = chain_result.scalar_one_or_none()
    
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    
    # If this is the last step, cancel the chain
    if step.step_index == chain.required_doctors_count - 1:
        ticket.status = "chain_cancelled"
        chain.status = "cancelled"
    else:
        # For now, we'll just mark the step as skipped
        # In a full implementation, we might want to route to next doctor or handle differently
        step.status = "skipped"
        ticket.status = "chain_cancelled"
        chain.status = "cancelled"
    
    # Note: SequentialReviewTicket doesn't use TicketUpdate (it's for regular tickets)
    # Status changes are tracked via the ticket.status and step.status fields
    
    await db.commit()
    await db.refresh(ticket)
    
    return {
        "ticket_id": str(ticket.ticket_id),
        "status": ticket.status,
        "message": "Step rejected. Chain cancelled." if ticket.status == "chain_cancelled" else "Step rejected."
    }


async def build_accumulated_context(chain_id: str, up_to_step_index: int, db: AsyncSession) -> str:
    """Build accumulated context from all completed steps up to (but not including) the given step index."""
    # Query all completed steps with step_index < up_to_step_index
    steps_result = await db.execute(
        select(SequentialReviewStep).where(
            SequentialReviewStep.chain_id == uuid.UUID(chain_id),
            SequentialReviewStep.step_index < up_to_step_index,
            SequentialReviewStep.status == "completed"
        ).order_by(SequentialReviewStep.step_index)
    )
    previous_steps = steps_result.scalars().all()
    
    if not previous_steps:
        return "No previous reviews."
    
    context_parts = []
    for prev_step in previous_steps:
        # Get doctor info
        doctor_result = await db.execute(
            select(ServicePerson).where(ServicePerson.service_person_id == prev_step.doctor_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        doctor_name = doctor.name if doctor else "Unknown Doctor"
        doctor_specialization = doctor.specialization if doctor and doctor.specialization else ""
        
        context_part = f"Doctor {prev_step.step_index + 1}: {doctor_name}"
        if doctor_specialization:
            context_part += f" ({doctor_specialization})"
        context_part += "\n"
        
        if prev_step.review_summary:
            context_part += f"Summary: {prev_step.review_summary}\n"
        if prev_step.review_notes:
            context_part += f"Notes: {prev_step.review_notes}\n"
        
        context_parts.append(context_part)
    
    return "\n\n".join(context_parts)


@router.put("/{ticket_id}/step-status")
async def update_step_status(
    ticket_id: str,
    request: UpdateStepStatusRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update step status (start work, complete)."""
    user_type = current_user["type"]
    if user_type != "service_person":
        raise HTTPException(status_code=403, detail="Only service persons can update step status")
    
    valid_statuses = ["step_accepted", "step_in_progress", "step_completed"]
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    # Get ticket
    ticket_result = await db.execute(
        select(SequentialReviewTicket).where(
            SequentialReviewTicket.ticket_id == uuid.UUID(ticket_id)
        )
    )
    ticket = ticket_result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Sequential review ticket not found")
    
    # Get step
    step_result = await db.execute(
        select(SequentialReviewStep).where(
            SequentialReviewStep.step_id == ticket.step_id
        )
    )
    step = step_result.scalar_one_or_none()
    
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    # Verify doctor is assigned to this step
    service_person_id = current_user["user"].service_person_id
    if step.doctor_id != service_person_id:
        raise HTTPException(status_code=403, detail="You are not assigned to this step")
    
    # Update based on status
    old_status = ticket.status
    
    if request.status == "step_in_progress":
        if ticket.status != "step_accepted":
            raise HTTPException(status_code=400, detail="Step must be accepted before starting work")
        ticket.status = "step_in_progress"
        step.status = "in_review"
        if not step.started_at:
            step.started_at = datetime.utcnow()
    
    elif request.status == "step_completed":
        if ticket.status not in ["step_accepted", "step_in_progress"]:
            raise HTTPException(status_code=400, detail="Step must be accepted or in progress before completing")
        if not request.review_notes:
            raise HTTPException(status_code=400, detail="Review notes are required when completing a step")
        
        ticket.status = "step_completed"
        step.status = "completed"
        step.review_notes = request.review_notes
        step.completed_at = datetime.utcnow()
        
        # Get chain to check if all steps are done
        chain_result = await db.execute(
            select(SequentialReviewChain).where(
                SequentialReviewChain.chain_id == ticket.chain_id
            )
        )
        chain = chain_result.scalar_one_or_none()
        
        if chain:
            # Advance chain to next step
            chain.current_step_index += 1
            
            # Check if all steps are completed
            all_steps_result = await db.execute(
                select(SequentialReviewStep).where(
                    SequentialReviewStep.chain_id == chain.chain_id
                )
            )
            all_steps = all_steps_result.scalars().all()
            
            if all(s.status == "completed" for s in all_steps):
                # All steps completed - mark all tickets as chain_completed
                all_tickets_result = await db.execute(
                    select(SequentialReviewTicket).where(
                        SequentialReviewTicket.chain_id == chain.chain_id
                    )
                )
                all_tickets = all_tickets_result.scalars().all()
                for t in all_tickets:
                    t.status = "chain_completed"
                ticket.chain_completed_at = datetime.utcnow()
                chain.status = "completed"
                chain.completed_at = datetime.utcnow()
            else:
                # More steps remaining - enable next step's ticket
                next_step_index = step.step_index + 1
                next_step_result = await db.execute(
                    select(SequentialReviewStep).where(
                        SequentialReviewStep.chain_id == chain.chain_id,
                        SequentialReviewStep.step_index == next_step_index
                    )
                )
                next_step = next_step_result.scalar_one_or_none()
                
                if next_step:
                    # Find next step's ticket
                    next_ticket_result = await db.execute(
                        select(SequentialReviewTicket).where(
                            SequentialReviewTicket.step_id == next_step.step_id
                        )
                    )
                    next_ticket = next_ticket_result.scalar_one_or_none()
                    
                    if next_ticket:
                        # Build accumulated context from all completed steps
                        accumulated_context = await build_accumulated_context(
                            str(chain.chain_id), next_step_index, db
                        )
                        
                        # Get original case description (from first ticket)
                        # Find the first ticket in the chain to get original case
                        first_ticket_result = await db.execute(
                            select(SequentialReviewTicket).where(
                                SequentialReviewTicket.chain_id == chain.chain_id,
                                SequentialReviewTicket.step_index == 0
                            )
                        )
                        first_ticket = first_ticket_result.scalar_one_or_none()
                        
                        original_case = ""
                        if first_ticket and first_ticket.description:
                            # Extract original case from first ticket
                            desc = first_ticket.description
                            if "CURRENT CASE:" in desc:
                                parts = desc.split("CURRENT CASE:")
                                if len(parts) > 1:
                                    original_case = parts[-1].split("\n\nSequential Review")[0].strip()
                            else:
                                # Fallback: use description as-is if no CURRENT CASE marker
                                original_case = desc.split("\n\nSequential Review")[0].strip() if "\n\nSequential Review" in desc else desc
                        
                        if not original_case:
                            if "CURRENT CASE:" in ticket.description:
                                original_case = ticket.description.split("CURRENT CASE:")[-1].split("\n\nSequential Review")[0].strip()
                            else:
                                original_case = ticket.description
                        
                        # Update next ticket with accumulated context
                        next_ticket.can_start = True
                        next_ticket.description = f"PREVIOUS DOCTORS' REVIEWS:\n{accumulated_context}\n\nCURRENT CASE:\n{original_case}\n\nSequential Review - Step {next_step_index + 1} of {len(all_steps)}"
                        next_ticket.status = "step_pending"
                        
                        # Update LLM summary
                        doctor_result = await db.execute(
                            select(ServicePerson).where(ServicePerson.service_person_id == next_step.doctor_id)
                        )
                        doctor = doctor_result.scalar_one_or_none()
                        doctor_name = doctor.name if doctor else "Unknown Doctor"
                        service_type = doctor.service_type if doctor else "Unknown"
                        
                        # Get total steps
                        total_steps = len(all_steps)
                        next_ticket.llm_summary = f"Sequential Review Chain - Step {next_step_index + 1} of {total_steps}\n"
                        next_ticket.llm_summary += f"Doctor: {doctor_name} ({service_type})\n"
                        if accumulated_context and accumulated_context != "No previous reviews.":
                            next_ticket.llm_summary += f"\nPrevious Reviews:\n{accumulated_context}\n"
                        
                        print(f"[API] ✅ Enabled next step ticket {next_ticket.ticket_id} for step {next_step_index + 1}")
                    else:
                        print(f"[API] WARNING: Next step ticket not found for step {next_step_index + 1}")
                else:
                    print(f"[API] WARNING: Next step not found at index {next_step_index}")
    
    # Note: SequentialReviewTicket doesn't use TicketUpdate (it's for regular tickets)
    # Status changes are tracked via the ticket.status and step.status fields
    # Review notes are stored in step.review_notes
    
    await db.commit()
    await db.refresh(ticket)
    
    return {
        "ticket_id": str(ticket.ticket_id),
        "status": ticket.status,
        "step_status": step.status
    }

"""Sequential review chain management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import uuid

from backend.src.database.connection import get_db
from backend.src.database.models import (
    SequentialReviewChain, SequentialReviewStep, ServicePerson, Ticket
)
from backend.src.api.dependencies import get_current_user

router = APIRouter(prefix="/api/sequential-reviews", tags=["sequential-reviews"])


@router.get("/{chain_id}")
async def get_chain_status(
    chain_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get sequential review chain status and progress."""
    result = await db.execute(
        select(SequentialReviewChain).where(SequentialReviewChain.chain_id == uuid.UUID(chain_id))
    )
    chain = result.scalar_one_or_none()
    
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    
    # Get all steps
    steps_result = await db.execute(
        select(SequentialReviewStep).where(
            SequentialReviewStep.chain_id == uuid.UUID(chain_id)
        ).order_by(SequentialReviewStep.step_index)
    )
    steps = steps_result.scalars().all()
    
    # Get doctor info for each step
    steps_data = []
    for step in steps:
        doctor_result = await db.execute(
            select(ServicePerson).where(ServicePerson.service_person_id == step.doctor_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        
        steps_data.append({
            "step_id": str(step.step_id),
            "step_index": step.step_index,
            "doctor_id": str(step.doctor_id),
            "doctor_name": doctor.name if doctor else "Unknown",
            "specialization": doctor.specialization if doctor else "",
            "service_type": doctor.service_type if doctor else "",
            "status": step.status,
            "review_summary": step.review_summary,
            "review_notes": step.review_notes,
            "started_at": step.started_at.isoformat() if step.started_at else None,
            "completed_at": step.completed_at.isoformat() if step.completed_at else None,
            "ticket_id": str(step.ticket_id) if step.ticket_id else None
        })
    
    return {
        "chain_id": str(chain.chain_id),
        "conversation_id": str(chain.conversation_id),
        "patient_id": str(chain.patient_id),
        "case_complexity_score": chain.case_complexity_score,
        "complexity_reason": chain.complexity_reason,
        "required_doctors_count": chain.required_doctors_count,
        "current_step_index": chain.current_step_index,
        "status": chain.status,
        "created_at": chain.created_at.isoformat(),
        "updated_at": chain.updated_at.isoformat(),
        "completed_at": chain.completed_at.isoformat() if chain.completed_at else None,
        "steps": steps_data
    }


@router.get("/{chain_id}/context")
async def get_accumulated_context(
    chain_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get accumulated context from all previous doctors' reviews."""
    result = await db.execute(
        select(SequentialReviewChain).where(SequentialReviewChain.chain_id == uuid.UUID(chain_id))
    )
    chain = result.scalar_one_or_none()
    
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    
    # Get all completed steps
    steps_result = await db.execute(
        select(SequentialReviewStep).where(
            SequentialReviewStep.chain_id == uuid.UUID(chain_id),
            SequentialReviewStep.status == "completed"
        ).order_by(SequentialReviewStep.step_index)
    )
    steps = steps_result.scalars().all()
    
    context_parts = []
    for step in steps:
        doctor_result = await db.execute(
            select(ServicePerson).where(ServicePerson.service_person_id == step.doctor_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        doctor_name = doctor.name if doctor else "Unknown Doctor"
        
        context_part = f"Doctor {step.step_index + 1}: {doctor_name}"
        if doctor and doctor.specialization:
            context_part += f" ({doctor.specialization})"
        context_part += "\n"
        
        if step.review_summary:
            context_part += f"Summary: {step.review_summary}\n"
        if step.review_notes:
            context_part += f"Notes: {step.review_notes}\n"
        
        context_parts.append(context_part)
    
    accumulated_context = "\n\n".join(context_parts) if context_parts else "No previous reviews."
    
    return {
        "chain_id": str(chain_id),
        "accumulated_context": accumulated_context,
        "steps_count": len(steps)
    }


@router.get("/patient/{patient_id}")
async def get_patient_chains(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all sequential review chains for a patient."""
    user_type = current_user["type"]
    user = current_user["user"]
    
    # Verify access
    if user_type == "patient" and str(user.patient_id) != patient_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.execute(
        select(SequentialReviewChain).where(
            SequentialReviewChain.patient_id == uuid.UUID(patient_id)
        ).order_by(SequentialReviewChain.created_at.desc())
    )
    chains = result.scalars().all()
    
    chains_data = []
    for chain in chains:
        chains_data.append({
            "chain_id": str(chain.chain_id),
            "conversation_id": str(chain.conversation_id),
            "status": chain.status,
            "current_step_index": chain.current_step_index,
            "required_doctors_count": chain.required_doctors_count,
            "complexity_reason": chain.complexity_reason,
            "created_at": chain.created_at.isoformat(),
            "completed_at": chain.completed_at.isoformat() if chain.completed_at else None
        })
    
    return {"chains": chains_data}


@router.get("/tickets/{ticket_id}/sequential-context")
async def get_ticket_sequential_context(
    ticket_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get accumulated context for a ticket's sequential review step."""
    # Get ticket
    ticket_result = await db.execute(
        select(Ticket).where(Ticket.ticket_id == uuid.UUID(ticket_id))
    )
    ticket = ticket_result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if not ticket.is_sequential_review or not ticket.sequential_review_chain_id:
        return {
            "is_sequential_review": False,
            "accumulated_context": None
        }
    
    # Get step for this ticket
    step_result = await db.execute(
        select(SequentialReviewStep).where(SequentialReviewStep.ticket_id == uuid.UUID(ticket_id))
    )
    step = step_result.scalar_one_or_none()
    
    if not step:
        return {
            "is_sequential_review": True,
            "accumulated_context": "No previous reviews."
        }
    
    # Get accumulated context up to this step
    previous_steps_result = await db.execute(
        select(SequentialReviewStep).where(
            SequentialReviewStep.chain_id == step.chain_id,
            SequentialReviewStep.step_index < step.step_index,
            SequentialReviewStep.status == "completed"
        ).order_by(SequentialReviewStep.step_index)
    )
    previous_steps = previous_steps_result.scalars().all()
    
    context_parts = []
    for prev_step in previous_steps:
        doctor_result = await db.execute(
            select(ServicePerson).where(ServicePerson.service_person_id == prev_step.doctor_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        doctor_name = doctor.name if doctor else "Unknown Doctor"
        
        context_part = f"Doctor {prev_step.step_index + 1}: {doctor_name}"
        if doctor and doctor.specialization:
            context_part += f" ({doctor.specialization})"
        context_part += "\n"
        
        if prev_step.review_summary:
            context_part += f"Summary: {prev_step.review_summary}\n"
        if prev_step.review_notes:
            context_part += f"Notes: {prev_step.review_notes}\n"
        
        context_parts.append(context_part)
    
    accumulated_context = "\n\n".join(context_parts) if context_parts else "No previous reviews."
    
    # Get chain info
    chain_result = await db.execute(
        select(SequentialReviewChain).where(SequentialReviewChain.chain_id == step.chain_id)
    )
    chain = chain_result.scalar_one_or_none()
    
    return {
        "is_sequential_review": True,
        "chain_id": str(step.chain_id),
        "step_index": step.step_index,
        "total_steps": chain.required_doctors_count if chain else 0,
        "accumulated_context": accumulated_context,
        "current_step_status": step.status
    }

"""Appointment endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

from backend.src.database.connection import get_db
from backend.src.database.models import Appointment
from backend.src.api.dependencies import get_current_user

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


class CreateAppointmentRequest(BaseModel):
    patient_id: str
    service_type: str
    scheduled_date: str  # ISO format
    service_person_id: Optional[str] = None
    ticket_id: Optional[str] = None
    notes: Optional[str] = None


class UpdateAppointmentRequest(BaseModel):
    scheduled_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
async def list_appointments(
    patient_id: Optional[str] = Query(None),
    service_person_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List appointments."""
    user = current_user["user"]
    user_type = current_user["type"]
    
    query = select(Appointment)
    
    # Filter based on user type
    if user_type == "patient":
        query = query.where(Appointment.patient_id == user.patient_id)
    elif user_type == "service_person":
        query = query.where(Appointment.service_person_id == user.service_person_id)
    
    # Additional filters
    if patient_id:
        query = query.where(Appointment.patient_id == uuid.UUID(patient_id))
    if service_person_id:
        query = query.where(Appointment.service_person_id == uuid.UUID(service_person_id))
    if status:
        query = query.where(Appointment.status == status)
    
    result = await db.execute(query.order_by(Appointment.scheduled_date))
    appointments = result.scalars().all()
    
    return [
        {
            "appointment_id": str(apt.appointment_id),
            "ticket_id": str(apt.ticket_id) if apt.ticket_id else None,
            "patient_id": str(apt.patient_id),
            "service_person_id": str(apt.service_person_id) if apt.service_person_id else None,
            "appointment_type": apt.appointment_type,
            "scheduled_date": apt.scheduled_date.isoformat(),
            "status": apt.status,
            "notes": apt.notes,
            "created_at": apt.created_at.isoformat()
        }
        for apt in appointments
    ]


@router.post("")
async def create_appointment(
    request: CreateAppointmentRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new appointment."""
    user_type = current_user["type"]
    if user_type not in ["service_person", "admin"]:
        raise HTTPException(status_code=403, detail="Only service persons and admins can create appointments")
    
    try:
        scheduled_date = datetime.fromisoformat(request.scheduled_date.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
    
    appointment = Appointment(
        patient_id=uuid.UUID(request.patient_id),
        service_type=request.service_type,
        scheduled_date=scheduled_date,
        appointment_type="consultation",
        status="scheduled",
        notes=request.notes
    )
    
    if request.service_person_id:
        appointment.service_person_id = uuid.UUID(request.service_person_id)
    if request.ticket_id:
        appointment.ticket_id = uuid.UUID(request.ticket_id)
    
    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)
    
    return {
        "appointment_id": str(appointment.appointment_id),
        "patient_id": str(appointment.patient_id),
        "scheduled_date": appointment.scheduled_date.isoformat(),
        "status": appointment.status
    }


@router.put("/{appointment_id}")
async def update_appointment(
    appointment_id: str,
    request: UpdateAppointmentRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an appointment."""
    user_type = current_user["type"]
    if user_type not in ["service_person", "admin"]:
        raise HTTPException(status_code=403, detail="Only service persons and admins can update appointments")
    
    result = await db.execute(
        select(Appointment).where(Appointment.appointment_id == uuid.UUID(appointment_id))
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if request.scheduled_date:
        appointment.scheduled_date = datetime.fromisoformat(request.scheduled_date.replace("Z", "+00:00"))
    if request.status:
        valid_statuses = ["scheduled", "completed", "cancelled", "no_show"]
        if request.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        appointment.status = request.status
    if request.notes is not None:
        appointment.notes = request.notes
    
    await db.commit()
    await db.refresh(appointment)
    
    return {
        "appointment_id": str(appointment.appointment_id),
        "scheduled_date": appointment.scheduled_date.isoformat(),
        "status": appointment.status,
        "notes": appointment.notes
    }

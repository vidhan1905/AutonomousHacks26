"""Patient profile endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict
from datetime import datetime

from backend.src.database.connection import get_db
from backend.src.api.dependencies import get_current_patient
from backend.src.database.models import Patient

router = APIRouter(prefix="/api/patients", tags=["patients"])


class EmergencyContact(BaseModel):
    """Emergency contact information."""
    name: str
    phone: str
    relationship: str


class PatientProfileUpdate(BaseModel):
    """Patient profile update request model."""
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    emergency_contact: Optional[EmergencyContact] = None
    blood_group: Optional[str] = None
    gender: Optional[str] = None


class PatientProfileResponse(BaseModel):
    """Patient profile response model."""
    patient_id: str
    name: str
    phone_number: str
    email: Optional[str] = None
    date_of_birth: str
    gender: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[Dict] = None
    blood_group: Optional[str] = None


@router.get("/profile", response_model=PatientProfileResponse)
async def get_patient_profile(
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated patient's profile."""
    return PatientProfileResponse(
        patient_id=str(current_patient.patient_id),
        name=current_patient.name,
        phone_number=current_patient.phone_number,
        email=current_patient.email,
        date_of_birth=str(current_patient.date_of_birth) if current_patient.date_of_birth else "",
        gender=current_patient.gender,
        address=current_patient.address,
        emergency_contact=current_patient.emergency_contact,
        blood_group=current_patient.blood_group
    )


@router.put("/profile", response_model=PatientProfileResponse)
async def update_patient_profile(
    profile_data: PatientProfileUpdate,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db)
):
    """Update current authenticated patient's profile.
    
    Only allows updating: email, address, emergency_contact, blood_group, gender.
    name, phone_number, and date_of_birth are read-only (set during signup).
    """
    # Validate blood_group if provided
    valid_blood_groups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    if profile_data.blood_group and profile_data.blood_group not in valid_blood_groups:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid blood group. Must be one of: {', '.join(valid_blood_groups)}"
        )
    
    # Validate gender if provided
    valid_genders = ["male", "female", "other", "prefer_not_to_say"]
    if profile_data.gender and profile_data.gender not in valid_genders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid gender. Must be one of: {', '.join(valid_genders)}"
        )
    
    # Update fields if provided
    if profile_data.email is not None:
        current_patient.email = profile_data.email
    
    if profile_data.address is not None:
        current_patient.address = profile_data.address
    
    if profile_data.emergency_contact is not None:
        # Convert EmergencyContact model to dict for JSON storage
        current_patient.emergency_contact = profile_data.emergency_contact.model_dump()
    
    if profile_data.blood_group is not None:
        current_patient.blood_group = profile_data.blood_group
    
    if profile_data.gender is not None:
        current_patient.gender = profile_data.gender
    
    db.add(current_patient)
    await db.commit()
    await db.refresh(current_patient)
    
    return PatientProfileResponse(
        patient_id=str(current_patient.patient_id),
        name=current_patient.name,
        phone_number=current_patient.phone_number,
        email=current_patient.email,
        date_of_birth=str(current_patient.date_of_birth) if current_patient.date_of_birth else "",
        gender=current_patient.gender,
        address=current_patient.address,
        emergency_contact=current_patient.emergency_contact,
        blood_group=current_patient.blood_group
    )

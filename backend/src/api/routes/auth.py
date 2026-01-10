"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from backend.src.database.connection import get_db
from backend.src.services.auth_service import (
    authenticate_patient,
    authenticate_service_person,
    authenticate_admin,
    create_access_token,
    get_password_hash
)
from backend.src.api.dependencies import (
    get_current_user,
    get_current_patient,
    get_current_service_person,
    get_current_admin
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()


class LoginRequest(BaseModel):
    username: str
    password: str
    user_type: str  # "patient", "service_person", "admin"


class PatientLoginRequest(BaseModel):
    phone_number: str
    # For patients, we might use OTP instead of password


class RegisterRequest(BaseModel):
    name: str
    phone_number: str
    email: str
    password: str
    date_of_birth: str
    gender: str


@router.post("/login")
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login endpoint for service persons and admins."""
    if request.user_type == "service_person":
        user = await authenticate_service_person(db, request.username, request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        access_token = create_access_token(
            data={"sub": str(user.service_person_id), "type": "service_person"}
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.service_person_id),
                "username": user.username,
                "name": user.name,
                "service_type": user.service_type,
                "type": "service_person"
            }
        }
    
    elif request.user_type == "admin":
        user = await authenticate_admin(db, request.username, request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        access_token = create_access_token(
            data={"sub": str(user.admin_id), "type": "admin"}
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.admin_id),
                "username": user.username,
                "role": user.role,
                "type": "admin"
            }
        }
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user type"
        )


@router.post("/login/patient")
async def patient_login(
    request: PatientLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login endpoint for patients (phone-based)."""
    # In production, implement OTP verification
    # For now, just verify phone exists
    from sqlalchemy import select
    from backend.src.database.models import Patient
    
    result = await db.execute(
        select(Patient).where(Patient.phone_number == request.phone_number)
    )
    patient = result.scalar_one_or_none()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Patient not found"
        )
    
    access_token = create_access_token(
        data={"sub": str(patient.patient_id), "type": "patient"}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(patient.patient_id),
            "name": patient.name,
            "phone": patient.phone_number,
            "type": "patient"
        }
    }


@router.post("/register")
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a new patient."""
    from sqlalchemy import select
    from backend.src.database.models import Patient
    from datetime import datetime
    
    # Check if patient already exists
    result = await db.execute(
        select(Patient).where(Patient.phone_number == request.phone_number)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient with this phone number already exists"
        )
    
    dob = datetime.strptime(request.date_of_birth, "%Y-%m-%d").date()
    patient = Patient(
        name=request.name,
        phone_number=request.phone_number,
        email=request.email,
        date_of_birth=dob,
        gender=request.gender
    )
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    
    access_token = create_access_token(
        data={"sub": str(patient.patient_id), "type": "patient"}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(patient.patient_id),
            "name": patient.name,
            "type": "patient"
        }
    }


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user."""
    user = current_user["user"]
    user_type = current_user["type"]
    
    if user_type == "patient":
        return {
            "id": str(user.patient_id),
            "name": user.name,
            "phone": user.phone_number,
            "email": user.email,
            "type": "patient"
        }
    elif user_type == "service_person":
        return {
            "id": str(user.service_person_id),
            "username": user.username,
            "name": user.name,
            "service_type": user.service_type,
            "type": "service_person"
        }
    elif user_type == "admin":
        return {
            "id": str(user.admin_id),
            "username": user.username,
            "role": user.role,
            "type": "admin"
        }


@router.post("/logout")
async def logout():
    """Logout endpoint (client should discard token)."""
    return {"message": "Logged out successfully"}

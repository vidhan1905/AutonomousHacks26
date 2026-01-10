"""FastAPI dependencies."""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from backend.src.database.connection import get_db
from backend.src.services.auth_service import decode_token
from backend.src.database.models import Patient, ServicePerson, Admin
from sqlalchemy import select

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated user."""
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    user_type = payload.get("type")  # "patient", "service_person", "admin"
    
    if user_type == "patient":
        result = await db.execute(select(Patient).where(Patient.patient_id == user_id))
        user = result.scalar_one_or_none()
    elif user_type == "service_person":
        result = await db.execute(select(ServicePerson).where(ServicePerson.service_person_id == user_id))
        user = result.scalar_one_or_none()
    elif user_type == "admin":
        result = await db.execute(select(Admin).where(Admin.admin_id == user_id))
        user = result.scalar_one_or_none()
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user type",
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return {"user": user, "type": user_type}


async def get_current_patient(
    current_user: dict = Depends(get_current_user)
) -> Patient:
    """Get current authenticated patient."""
    if current_user["type"] != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a patient",
        )
    return current_user["user"]


async def get_current_service_person(
    current_user: dict = Depends(get_current_user)
) -> ServicePerson:
    """Get current authenticated service person."""
    if current_user["type"] != "service_person":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a service person",
        )
    return current_user["user"]


async def get_current_admin(
    current_user: dict = Depends(get_current_user)
) -> Admin:
    """Get current authenticated admin."""
    if current_user["type"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not an admin",
        )
    return current_user["user"]

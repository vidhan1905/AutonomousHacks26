"""Patient service operations."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid
from backend.src.database.models import Patient, PatientHistory


async def get_patient_by_id(db: AsyncSession, patient_id: str) -> Optional[Patient]:
    """Get patient by ID."""
    result = await db.execute(
        select(Patient).where(Patient.patient_id == uuid.UUID(patient_id))
    )
    return result.scalar_one_or_none()


async def get_patient_by_phone(db: AsyncSession, phone_number: str) -> Optional[Patient]:
    """Get patient by phone number."""
    result = await db.execute(
        select(Patient).where(Patient.phone_number == phone_number)
    )
    return result.scalar_one_or_none()


async def get_patient_history_records(db: AsyncSession, patient_id: str) -> list[PatientHistory]:
    """Get all history records for a patient."""
    result = await db.execute(
        select(PatientHistory)
        .where(PatientHistory.patient_id == uuid.UUID(patient_id))
        .order_by(PatientHistory.visit_date.desc())
    )
    return list(result.scalars().all())

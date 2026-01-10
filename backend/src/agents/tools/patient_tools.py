"""LangGraph tools for patient operations."""
from typing import Optional, Callable, Any
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from backend.src.database.models import Patient, PatientHistory
from backend.src.database.connection import async_session_maker
import uuid
import asyncio
import concurrent.futures


def run_async_safely(async_func: Callable, *args, session_maker_param=False, **kwargs) -> Any:
    """Run an async function safely from a sync context using a thread pool."""
    def run_in_thread():
        """Run async function in a new event loop in a separate thread."""
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            from backend.src.database.connection import create_async_session_maker
            # Create a fresh session maker for this event loop
            fresh_session_maker = create_async_session_maker()
            # If function needs session_maker, add it to kwargs
            if session_maker_param:
                kwargs['session_maker'] = fresh_session_maker
            return new_loop.run_until_complete(async_func(*args, **kwargs))
        finally:
            new_loop.close()
    
    # Use ThreadPoolExecutor to run in a separate thread with its own event loop
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        return future.result(timeout=10)  # 10 second timeout


async def _verify_patient_async(name: str, phone: str, date_of_birth: str, session_maker=None) -> dict:
    """Async implementation of verify_patient."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Use provided session maker or create a new one for this event loop
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            # Parse date - handle various formats
            try:
                dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
            except ValueError:
                # Try other formats
                try:
                    dob = datetime.strptime(date_of_birth, "%m/%d/%Y").date()
                except ValueError:
                    try:
                        dob = datetime.strptime(date_of_birth, "%d/%m/%Y").date()
                    except ValueError:
                        return {"found": False, "error": f"Invalid date format: {date_of_birth}. Use YYYY-MM-DD"}
            
            # Normalize inputs
            normalized_name = name.strip().title()
            normalized_phone = phone.strip()
            
            logger.info(f"Verifying patient: name='{normalized_name}', phone='{normalized_phone}', dob='{dob}'")
            
            # Strategy 1: Try exact match on phone (most reliable, phone is unique)
            result = await session.execute(
                select(Patient).where(Patient.phone_number == normalized_phone)
            )
            patient = result.scalar_one_or_none()
            
            if patient:
                logger.info(f"Found patient by phone: {patient.name}, DOB: {patient.date_of_birth}")
                # Verify name and DOB match
                name_matches = (
                    patient.name.lower() == normalized_name.lower() or
                    normalized_name.lower() in patient.name.lower() or
                    patient.name.lower() in normalized_name.lower()
                )
                dob_matches = patient.date_of_birth == dob
                
                logger.info(f"Name match: {name_matches} (DB: '{patient.name}' vs Input: '{normalized_name}')")
                logger.info(f"DOB match: {dob_matches} (DB: {patient.date_of_birth} vs Input: {dob})")
                
                if name_matches and dob_matches:
                    return {
                        "patient_id": str(patient.patient_id),
                        "name": patient.name,
                        "phone": patient.phone_number,
                        "found": True
                    }
                else:
                    # Phone matches but name/DOB don't - return partial match info
                    return {
                        "found": False,
                        "patient_id": None,
                        "message": f"Phone number found but name/DOB don't match. DB: name='{patient.name}', dob={patient.date_of_birth}. Input: name='{normalized_name}', dob={dob}"
                    }
            
            # Strategy 2: Try matching by name and DOB (in case phone format differs)
            result = await session.execute(
                select(Patient).where(
                    Patient.name.ilike(f"%{normalized_name}%"),
                    Patient.date_of_birth == dob
                )
            )
            patient = result.scalar_one_or_none()
            
            if patient:
                # Check if phone is similar (might have formatting differences)
                db_phone_clean = patient.phone_number.replace("-", "").replace(" ", "").replace(".", "").replace("x", "")
                input_phone_clean = normalized_phone.replace("-", "").replace(" ", "").replace(".", "").replace("x", "")
                
                if db_phone_clean == input_phone_clean or db_phone_clean.endswith(input_phone_clean) or input_phone_clean.endswith(db_phone_clean):
                    return {
                        "patient_id": str(patient.patient_id),
                        "name": patient.name,
                        "phone": patient.phone_number,
                        "found": True
                    }
            
            # Strategy 3: Try all three together with flexible matching
            result = await session.execute(
                select(Patient).where(
                    Patient.name.ilike(f"%{normalized_name}%"),
                    Patient.phone_number.ilike(f"%{normalized_phone}%"),
                    Patient.date_of_birth == dob
                )
            )
            patient = result.scalar_one_or_none()
            
            if patient:
                return {
                    "patient_id": str(patient.patient_id),
                    "name": patient.name,
                    "phone": patient.phone_number,
                    "found": True
                }
            
            return {"found": False, "patient_id": None, "message": "Patient not found with provided information"}
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"Error in _verify_patient_async: {error_msg}")
            return {"found": False, "error": error_msg}


@tool
def verify_patient(name: str, phone: str, date_of_birth: str) -> dict:
    """Verify a patient by name, phone number, and date of birth.
    
    Args:
        name: Full name of the patient (e.g., "April Maldonado")
        phone: Phone number exactly as stored in database (e.g., "001-852-326-5094x079")
        date_of_birth: Date in YYYY-MM-DD format (e.g., "1955-02-28")
    
    Returns:
        dict with "found" (bool), "patient_id" (str if found), "name", "phone"
    """
    # Clean inputs
    name = str(name).strip()
    phone = str(phone).strip()
    date_of_birth = str(date_of_birth).strip()
    
    try:
        return run_async_safely(_verify_patient_async, name, phone, date_of_birth, session_maker_param=True)
    except Exception as e:
        import traceback
        return {
            "found": False,
            "error": f"Exception in verify_patient: {str(e)}\n{traceback.format_exc()}"
        }


async def _create_patient_async(
    name: str, phone: str, date_of_birth: str,
    email: Optional[str] = None, gender: Optional[str] = None,
    blood_group: Optional[str] = None,
    session_maker=None
) -> dict:
    """Async implementation of create_patient."""
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            # First check if patient already exists (by phone)
            existing = await session.execute(
                select(Patient).where(Patient.phone_number == phone.strip())
            )
            existing_patient = existing.scalar_one_or_none()
            
            if existing_patient:
                # Patient already exists, return existing patient info
                return {
                    "patient_id": str(existing_patient.patient_id),
                    "name": existing_patient.name,
                    "status": "already_exists",
                    "message": "Patient with this phone number already exists"
                }
            
            # Parse date
            try:
                dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
            except ValueError:
                try:
                    dob = datetime.strptime(date_of_birth, "%m/%d/%Y").date()
                except ValueError:
                    try:
                        dob = datetime.strptime(date_of_birth, "%d/%m/%Y").date()
                    except ValueError:
                        return {"status": "error", "error": f"Invalid date format: {date_of_birth}. Use YYYY-MM-DD"}
            
            patient = Patient(
                name=name.strip().title(), 
                phone_number=phone.strip(), 
                date_of_birth=dob,
                email=email.strip() if email else None, 
                gender=gender, 
                blood_group=blood_group
            )
            session.add(patient)
            await session.commit()
            await session.refresh(patient)
            return {
                "patient_id": str(patient.patient_id),
                "name": patient.name,
                "status": "created"
            }
        except Exception as e:
            await session.rollback()
            import traceback
            return {"status": "error", "error": f"{str(e)}\n{traceback.format_exc()}"}


@tool
def create_patient(
    name: str, phone: str, date_of_birth: str,
    email: Optional[str] = None, gender: Optional[str] = None,
    blood_group: Optional[str] = None
) -> dict:
    """Create a new patient record."""
    try:
        return run_async_safely(_create_patient_async, name, phone, date_of_birth, email, gender, blood_group, session_maker_param=True)
    except Exception as e:
        import traceback
        return {"status": "error", "error": f"Exception in create_patient: {str(e)}\n{traceback.format_exc()}"}


async def _update_patient_info_async(
    patient_id: str, blood_group: Optional[str] = None, email: Optional[str] = None,
    session_maker=None
) -> dict:
    """Async implementation of update_patient_info."""
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            result = await session.execute(
                select(Patient).where(Patient.patient_id == uuid.UUID(patient_id))
            )
            patient = result.scalar_one_or_none()
            if not patient:
                return {"status": "error", "error": "Patient not found"}
            if blood_group:
                patient.blood_group = blood_group
            if email:
                patient.email = email
            await session.commit()
            return {"status": "updated", "patient_id": patient_id}
        except Exception as e:
            await session.rollback()
            return {"status": "error", "error": str(e)}


@tool
def update_patient_info(patient_id: str, blood_group: Optional[str] = None, email: Optional[str] = None) -> dict:
    """Update patient information."""
    try:
        return run_async_safely(_update_patient_info_async, patient_id, blood_group, email, session_maker_param=True)
    except Exception as e:
        import traceback
        return {"status": "error", "error": f"Exception in update_patient_info: {str(e)}\n{traceback.format_exc()}"}


async def _get_patient_history_async(patient_id: str, session_maker=None) -> dict:
    """Async implementation of get_patient_history."""
    if session_maker is None:
        from backend.src.database.connection import async_session_maker
        session_maker = async_session_maker
    
    async with session_maker() as session:
        try:
            result = await session.execute(
                select(Patient).where(Patient.patient_id == uuid.UUID(patient_id))
            )
            patient = result.scalar_one_or_none()
            if not patient:
                return {"error": "Patient not found"}
            
            history_result = await session.execute(
                select(PatientHistory)
                .where(PatientHistory.patient_id == uuid.UUID(patient_id))
                .order_by(PatientHistory.visit_date.desc())
            )
            history_records = history_result.scalars().all()
            
            return {
                "patient_id": str(patient.patient_id),
                "name": patient.name,
                "age": (datetime.now().date() - patient.date_of_birth).days // 365,
                "gender": patient.gender,
                "blood_group": patient.blood_group,
                "medical_history": patient.medical_history or {},
                "history_records": [
                    {
                        "visit_date": str(record.visit_date),
                        "service_type": record.service_type,
                        "diagnosis": record.diagnosis,
                        "treatment": record.treatment,
                        "prescriptions": record.prescriptions,
                        "test_results": record.test_results,
                        "notes": record.notes
                    }
                    for record in history_records
                ]
            }
        except Exception as e:
            return {"error": str(e)}


@tool
def get_patient_history(patient_id: str) -> dict:
    """Get complete patient history including past visits, diagnoses, and treatments."""
    try:
        return run_async_safely(_get_patient_history_async, patient_id, session_maker_param=True)
    except Exception as e:
        import traceback
        return {"error": f"Exception in get_patient_history: {str(e)}\n{traceback.format_exc()}"}


@tool
def validate_required_fields(collected_info: dict) -> dict:
    """Validate that required fields are present."""
    required = ["name", "phone", "date_of_birth"]
    missing = [field for field in required if not collected_info.get(field)]
    return {
        "all_present": len(missing) == 0,
        "missing_fields": missing
    }



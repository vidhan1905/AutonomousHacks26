"""
Insert generated JSON data into the database.

This script reads JSON files from backend/src/data/generated/ and inserts
them into the database in the correct dependency order. It is idempotent
and can be run multiple times safely.
"""

import json
import uuid
import asyncio
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional, List
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from dotenv import load_dotenv
import os

# Import all models
from backend.src.database.models import (
    Patient, Admin, ServicePerson, Conversation,
    Ticket, Appointment, PatientHistory, TicketUpdate,
    DoctorExpertise, DoctorCaseHistory, TicketAssignment, PatientHistorySummary
)

# Import password hashing function
from backend.src.services.auth_service import get_password_hash

load_dotenv()

# Get DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/hospital_ai_assistant")

# Validate DATABASE_URL format - must be a proper PostgreSQL connection string
is_valid = (
    DATABASE_URL.startswith(("postgresql://", "postgresql+asyncpg://", "postgres://")) and
    "@" in DATABASE_URL and
    "/" in DATABASE_URL.split("@")[-1]  # Must have database name after @
)

if not is_valid:
    print("=" * 70)
    print("ERROR: Invalid DATABASE_URL format!")
    print("=" * 70)
    print(f"Current DATABASE_URL: {DATABASE_URL}")
    print()
    print("DATABASE_URL must be in one of these formats:")
    print("  postgresql+asyncpg://user:password@host:port/database")
    print("  postgresql://user:password@host:port/database")
    print()
    print("Example:")
    print("  postgresql+asyncpg://postgres:postgres@localhost:5432/hospital_ai_assistant")
    print()
    print("Common issues:")
    print("  - Missing protocol (postgresql:// or postgresql+asyncpg://)")
    print("  - Missing username:password@")
    print("  - Missing database name after /")
    print()
    print("To fix:")
    print("  1. Check your .env file in the project root")
    print("  2. Or unset the environment variable:")
    print("     PowerShell: Remove-Item Env:\\DATABASE_URL")
    print("     Then the script will use the default connection string")
    print("=" * 70)
    sys.exit(1)

DATA_DIR = project_root / "backend" / "src" / "data" / "generated"


def parse_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    """Convert string UUID to UUID object."""
    if value is None:
        return None
    return uuid.UUID(value)


def parse_date(value: Optional[str]) -> Optional[date]:
    """Convert ISO date string to date object."""
    if value is None:
        return None
    if isinstance(value, str):
        # Handle both "YYYY-MM-DD" and "YYYY-MM-DDTHH:MM:SS" formats
        try:
            # Try parsing as date first
            if len(value) == 10:  # "YYYY-MM-DD"
                return datetime.strptime(value, "%Y-%m-%d").date()
            else:
                # Has time component, parse as datetime then extract date
                value_clean = value.replace('Z', '').replace('+00:00', '').rstrip()
                return datetime.fromisoformat(value_clean).date()
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Unable to parse date: {value}") from e
    return value


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Convert ISO datetime string to datetime object."""
    if value is None:
        return None
    if isinstance(value, str):
        # Remove timezone info if present (we'll store as naive datetime)
        # Handle formats: "2026-01-10T20:16:40.555238", "2026-01-10T20:16:40.555238Z", "2026-01-10T20:16:40"
        value = value.replace('Z', '').replace('+00:00', '').rstrip()
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            # Try parsing without microseconds
            try:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                # Try parsing date only
                try:
                    return datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    raise ValueError(f"Unable to parse datetime: {value}")
    return value


async def check_exists(session: AsyncSession, model_class, primary_key_value: uuid.UUID) -> bool:
    """Check if a record with the given primary key exists."""
    # Get the primary key column name
    primary_key_cols = list(model_class.__table__.primary_key.columns)
    if not primary_key_cols:
        return False
    primary_key_name = primary_key_cols[0].name
    stmt = select(model_class).where(getattr(model_class, primary_key_name) == primary_key_value)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def insert_patients(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> int:
    """Insert patient records."""
    inserted = 0
    skipped = 0
    
    for record in data:
        patient_id = parse_uuid(record["patient_id"])
        
        if skip_existing and await check_exists(session, Patient, patient_id):
            skipped += 1
            continue
        
        # Hash password if provided
        password_hash = None
        if "password" in record and record["password"]:
            password_hash = get_password_hash(record["password"])
        
        patient = Patient(
            patient_id=patient_id,
            name=record["name"],
            phone_number=record["phone_number"],
            email=record.get("email"),
            date_of_birth=parse_date(record["date_of_birth"]),
            gender=record.get("gender"),
            address=record.get("address"),
            emergency_contact=record.get("emergency_contact"),
            blood_group=record.get("blood_group"),
            medical_history=record.get("medical_history"),
            password=password_hash,
            created_at=parse_datetime(record.get("created_at")),
            updated_at=parse_datetime(record.get("updated_at"))
        )
        
        session.add(patient)
        inserted += 1
    
    await session.commit()
    return inserted, skipped


async def insert_admins(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> tuple:
    """Insert admin records."""
    inserted = 0
    skipped = 0
    
    for record in data:
        admin_id = parse_uuid(record["admin_id"])
        
        if skip_existing and await check_exists(session, Admin, admin_id):
            skipped += 1
            continue
        
        # Hash password if provided (using SHA256)
        password_hash = None
        if "password" in record and record["password"]:
            password_hash = get_password_hash(record["password"])
        elif "password_hash" in record and record["password_hash"]:
            # Backward compatibility: if password_hash exists, use it directly
            password_hash = record["password_hash"]
        
        admin = Admin(
            admin_id=admin_id,
            username=record["username"],
            email=record["email"],
            password_hash=password_hash,
            role=record["role"],
            is_active=record.get("is_active", True),
            created_at=parse_datetime(record.get("created_at"))
        )
        
        session.add(admin)
        inserted += 1
    
    await session.commit()
    return inserted, skipped


async def insert_service_persons(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> tuple:
    """Insert service person records."""
    inserted = 0
    skipped = 0
    
    for record in data:
        service_person_id = parse_uuid(record["service_person_id"])
        
        if skip_existing and await check_exists(session, ServicePerson, service_person_id):
            skipped += 1
            continue
        
        # Hash password if provided (using SHA256)
        password_hash = None
        if "password" in record and record["password"]:
            password_hash = get_password_hash(record["password"])
        elif "password_hash" in record and record["password_hash"]:
            # Backward compatibility: if password_hash exists, use it directly
            password_hash = record["password_hash"]
        
        service_person = ServicePerson(
            service_person_id=service_person_id,
            username=record["username"],
            email=record["email"],
            password_hash=password_hash,
            name=record["name"],
            service_type=record["service_type"],
            specialization=record.get("specialization"),
            is_active=record.get("is_active", True),
            current_workload=record.get("current_workload", 0),
            max_workload=record.get("max_workload", 10),
            max_daily_appointments=record.get("max_daily_appointments", 15),
            workload_updated_at=parse_datetime(record.get("workload_updated_at")),
            is_available=record.get("is_available", True),
            created_at=parse_datetime(record.get("created_at"))
        )
        
        session.add(service_person)
        inserted += 1
    
    await session.commit()
    return inserted, skipped


async def insert_doctor_expertise(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> tuple:
    """Insert doctor expertise records."""
    inserted = 0
    skipped = 0
    
    for record in data:
        expertise_id = parse_uuid(record["expertise_id"])
        
        if skip_existing and await check_exists(session, DoctorExpertise, expertise_id):
            skipped += 1
            continue
        
        # Certifications are already in correct format (dates as strings in JSON)
        # No need to parse/convert them
        
        expertise = DoctorExpertise(
            expertise_id=expertise_id,
            service_person_id=parse_uuid(record["service_person_id"]),
            specialization_area=record["specialization_area"],
            years_of_experience=record["years_of_experience"],
            certifications=record.get("certifications", []),
            education=record.get("education", []),
            languages_spoken=record.get("languages_spoken", []),
            is_primary_specialization=record.get("is_primary_specialization", False),
            created_at=parse_datetime(record.get("created_at")),
            updated_at=parse_datetime(record.get("updated_at"))
        )
        
        session.add(expertise)
        inserted += 1
    
    await session.commit()
    return inserted, skipped


async def insert_conversations(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> tuple:
    """Insert conversation records."""
    inserted = 0
    skipped = 0
    
    for record in data:
        conversation_id = parse_uuid(record["conversation_id"])
        
        if skip_existing and await check_exists(session, Conversation, conversation_id):
            skipped += 1
            continue
        
        conversation = Conversation(
            conversation_id=conversation_id,
            patient_id=parse_uuid(record["patient_id"]),
            status=record["status"],
            started_at=parse_datetime(record.get("started_at")),
            ended_at=parse_datetime(record.get("ended_at")),
            summary=record.get("summary"),
            llm_model=record.get("llm_model")
        )
        
        session.add(conversation)
        inserted += 1
    
    await session.commit()
    return inserted, skipped


# Message model removed - messages are now handled by LangGraph checkpointer
# async def insert_messages(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> tuple:
#     """Insert message records."""
#     pass


async def insert_tickets(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> tuple:
    """Insert ticket records."""
    inserted = 0
    skipped = 0
    
    for record in data:
        ticket_id = parse_uuid(record["ticket_id"])
        
        if skip_existing and await check_exists(session, Ticket, ticket_id):
            skipped += 1
            continue
        
        ticket = Ticket(
            ticket_id=ticket_id,
            conversation_id=parse_uuid(record["conversation_id"]),
            patient_id=parse_uuid(record["patient_id"]),
            service_type=record["service_type"],
            status=record["status"],
            priority=record["priority"],
            assigned_to=parse_uuid(record.get("assigned_to")),
            description=record.get("description"),
            patient_details=record.get("patient_details"),
            past_history_summary=record.get("past_history_summary"),
            llm_summary=record.get("llm_summary"),
            current_symptoms=record.get("current_symptoms"),
            created_at=parse_datetime(record.get("created_at")),
            assigned_at=parse_datetime(record.get("assigned_at")),
            completed_at=parse_datetime(record.get("completed_at")),
            assignment_status=record.get("assignment_status", "unassigned"),
            offered_to_count=record.get("offered_to_count", 0),
            accepted_by=parse_uuid(record.get("accepted_by")),
            accepted_at=parse_datetime(record.get("accepted_at"))
        )
        
        session.add(ticket)
        inserted += 1
    
    await session.commit()
    return inserted, skipped


async def insert_ticket_assignments(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> tuple:
    """Insert ticket assignment records."""
    inserted = 0
    skipped = 0
    
    for record in data:
        assignment_id = parse_uuid(record["assignment_id"])
        
        if skip_existing and await check_exists(session, TicketAssignment, assignment_id):
            skipped += 1
            continue
        
        assignment = TicketAssignment(
            assignment_id=assignment_id,
            ticket_id=parse_uuid(record["ticket_id"]),
            service_person_id=parse_uuid(record["service_person_id"]),
            rank=record["rank"],
            status=record["status"],
            assigned_at=parse_datetime(record.get("assigned_at")),
            responded_at=parse_datetime(record.get("responded_at")),
            response_notes=record.get("response_notes"),
            expires_at=parse_datetime(record.get("expires_at")),
            created_at=parse_datetime(record.get("created_at"))
        )
        
        session.add(assignment)
        inserted += 1
    
    await session.commit()
    return inserted, skipped


async def insert_appointments(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> tuple:
    """Insert appointment records."""
    inserted = 0
    skipped = 0
    
    for record in data:
        appointment_id = parse_uuid(record["appointment_id"])
        
        if skip_existing and await check_exists(session, Appointment, appointment_id):
            skipped += 1
            continue
        
        appointment = Appointment(
            appointment_id=appointment_id,
            ticket_id=parse_uuid(record.get("ticket_id")),
            patient_id=parse_uuid(record["patient_id"]),
            service_person_id=parse_uuid(record.get("service_person_id")),
            appointment_type=record["appointment_type"],
            scheduled_date=parse_datetime(record["scheduled_date"]),
            status=record["status"],
            notes=record.get("notes"),
            created_at=parse_datetime(record.get("created_at"))
        )
        
        session.add(appointment)
        inserted += 1
    
    await session.commit()
    return inserted, skipped


async def insert_patient_history(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> tuple:
    """Insert patient history records."""
    inserted = 0
    skipped = 0
    
    for record in data:
        history_id = parse_uuid(record["history_id"])
        
        if skip_existing and await check_exists(session, PatientHistory, history_id):
            skipped += 1
            continue
        
        history = PatientHistory(
            history_id=history_id,
            patient_id=parse_uuid(record["patient_id"]),
            visit_date=parse_date(record["visit_date"]),
            service_type=record["service_type"],
            diagnosis=record.get("diagnosis"),
            treatment=record.get("treatment"),
            prescriptions=record.get("prescriptions"),
            test_results=record.get("test_results"),
            notes=record.get("notes"),
            created_at=parse_datetime(record.get("created_at"))
        )
        
        session.add(history)
        inserted += 1
    
    await session.commit()
    return inserted, skipped


async def insert_doctor_case_history(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> tuple:
    """Insert doctor case history records."""
    inserted = 0
    skipped = 0
    
    for record in data:
        case_id = parse_uuid(record["case_id"])
        
        if skip_existing and await check_exists(session, DoctorCaseHistory, case_id):
            skipped += 1
            continue
        
        case = DoctorCaseHistory(
            case_id=case_id,
            service_person_id=parse_uuid(record["service_person_id"]),
            ticket_id=parse_uuid(record.get("ticket_id")),
            patient_id=parse_uuid(record["patient_id"]),
            service_type=record["service_type"],
            diagnosis_category=record.get("diagnosis_category"),
            case_complexity=record["case_complexity"],
            outcome=record["outcome"],
            completion_date=parse_date(record.get("completion_date")),
            patient_satisfaction_score=record.get("patient_satisfaction_score"),
            notes=record.get("notes"),
            created_at=parse_datetime(record.get("created_at"))
        )
        
        session.add(case)
        inserted += 1
    
    await session.commit()
    return inserted, skipped


async def insert_ticket_updates(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> tuple:
    """Insert ticket update records."""
    inserted = 0
    skipped = 0
    
    for record in data:
        update_id = parse_uuid(record["update_id"])
        
        if skip_existing and await check_exists(session, TicketUpdate, update_id):
            skipped += 1
            continue
        
        update = TicketUpdate(
            update_id=update_id,
            ticket_id=parse_uuid(record["ticket_id"]),
            updated_by=parse_uuid(record["updated_by"]),
            update_type=record["update_type"],
            old_value=record.get("old_value"),
            new_value=record.get("new_value"),
            comment=record.get("comment"),
            created_at=parse_datetime(record.get("created_at"))
        )
        
        session.add(update)
        inserted += 1
    
    await session.commit()
    return inserted, skipped


async def insert_patient_history_summaries(session: AsyncSession, data: List[Dict[str, Any]], skip_existing: bool = True) -> tuple:
    """Insert patient history summary records."""
    inserted = 0
    skipped = 0
    
    for record in data:
        summary_id = parse_uuid(record["summary_id"])
        
        if skip_existing and await check_exists(session, PatientHistorySummary, summary_id):
            skipped += 1
            continue
        
        summary = PatientHistorySummary(
            summary_id=summary_id,
            patient_id=parse_uuid(record["patient_id"]),
            summary_text=record["summary_text"],
            summary_version=record["summary_version"],
            generated_by=record["generated_by"],
            ticket_id=parse_uuid(record.get("ticket_id")),
            includes_history_until=parse_date(record.get("includes_history_until")),
            created_at=parse_datetime(record.get("created_at"))
        )
        
        session.add(summary)
        inserted += 1
    
    await session.commit()
    return inserted, skipped


def load_json_file(filename: str) -> List[Dict[str, Any]]:
    """Load JSON data from file."""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


async def main():
    """Main function to insert all data."""
    print("=" * 70)
    print("Inserting Generated Data into Database")
    print("=" * 70)
    # Show database info (hide password)
    if '@' in DATABASE_URL:
        db_info = DATABASE_URL.split('@')[1]
    else:
        db_info = DATABASE_URL
    print(f"Database: {db_info}")
    print(f"Data directory: {DATA_DIR}")
    print()
    
    # Create async engine and session
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session_maker() as session:
            # Insert in dependency order
            print("1. Inserting patients...")
            patients_data = load_json_file("patients.json")
            inserted, skipped = await insert_patients(session, patients_data)
            print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(patients_data)}")
            print()
            
            print("2. Inserting admins...")
            admins_data = load_json_file("admins.json")
            inserted, skipped = await insert_admins(session, admins_data)
            print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(admins_data)}")
            print()
            
            print("3. Inserting service persons...")
            service_persons_data = load_json_file("service_persons.json")
            inserted, skipped = await insert_service_persons(session, service_persons_data)
            print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(service_persons_data)}")
            print()
            
            print("4. Inserting doctor expertise...")
            expertise_data = load_json_file("doctor_expertise.json")
            inserted, skipped = await insert_doctor_expertise(session, expertise_data)
            print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(expertise_data)}")
            print()
            
            print("5. Inserting conversations...")
            conversations_data = load_json_file("conversations.json")
            inserted, skipped = await insert_conversations(session, conversations_data)
            print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(conversations_data)}")
            print()
            
            # Messages are now handled by LangGraph checkpointer, not stored in database
            # print("6. Inserting messages...")
            # messages_data = load_json_file("messages.json")
            # inserted, skipped = await insert_messages(session, messages_data)
            # print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(messages_data)}")
            # print()
            
            print("6. Inserting tickets...")
            tickets_data = load_json_file("tickets.json")
            inserted, skipped = await insert_tickets(session, tickets_data)
            print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(tickets_data)}")
            print()
            
            print("7. Inserting ticket assignments...")
            assignments_data = load_json_file("ticket_assignments.json")
            inserted, skipped = await insert_ticket_assignments(session, assignments_data)
            print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(assignments_data)}")
            print()
            
            print("8. Inserting appointments...")
            appointments_data = load_json_file("appointments.json")
            inserted, skipped = await insert_appointments(session, appointments_data)
            print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(appointments_data)}")
            print()
            
            print("9. Inserting patient history...")
            history_data = load_json_file("patient_history.json")
            inserted, skipped = await insert_patient_history(session, history_data)
            print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(history_data)}")
            print()
            
            print("10. Inserting doctor case history...")
            case_history_data = load_json_file("doctor_case_history.json")
            inserted, skipped = await insert_doctor_case_history(session, case_history_data)
            print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(case_history_data)}")
            print()
            
            print("11. Inserting ticket updates...")
            updates_data = load_json_file("ticket_updates.json")
            inserted, skipped = await insert_ticket_updates(session, updates_data)
            print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(updates_data)}")
            print()
            
            print("12. Inserting patient history summaries...")
            summaries_data = load_json_file("patient_history_summaries.json")
            inserted, skipped = await insert_patient_history_summaries(session, summaries_data)
            print(f"   ✓ Inserted: {inserted}, Skipped: {skipped}, Total: {len(summaries_data)}")
            print()
            
            print("=" * 70)
            print("Data insertion completed successfully!")
            print("=" * 70)
    
    except Exception as e:
        print(f"\n❌ Error during insertion: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

"""Generate synthetic patient data for the hospital system."""
import asyncio
import random
import sys
from pathlib import Path
from datetime import datetime, timedelta
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib
import uuid

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.src.database.connection import async_session_maker, engine, Base
from backend.src.database.models import (
    Patient, ServicePerson, Admin, PatientHistory, Appointment, Ticket
)

fake = Faker()

SERVICE_TYPES = [
    "general_consultation", "emergency", "cardiology", "neurology",
    "orthopedics", "pediatrics", "gynecology", "dermatology",
    "mental_health", "physical_therapy", "surgery_consultation",
    "blood_test", "lab_test", "imaging", "pain_management"
]

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

GENDERS = ["M", "F", "Other"]


def get_password_hash(password: str) -> str:
    """Simple hash for synthetic data generation (not for production use)."""
    return hashlib.sha256(f"salt_{password}".encode()).hexdigest()


async def create_patients(count: int = 500) -> list[Patient]:
    """Create synthetic patients."""
    patients = []
    async with async_session_maker() as session:
        for _ in range(count):
            dob = fake.date_of_birth(minimum_age=18, maximum_age=80)
            patient = Patient(
                name=fake.name(),
                phone_number=fake.phone_number(),
                email=fake.email(),
                date_of_birth=dob,
                gender=random.choice(GENDERS),
                address=fake.address(),
                emergency_contact={
                    "name": fake.name(),
                    "phone": fake.phone_number(),
                    "relation": random.choice(["Spouse", "Parent", "Sibling", "Friend"])
                },
                blood_group=random.choice(BLOOD_GROUPS),
                medical_history={
                    "allergies": random.sample(
                        ["penicillin", "aspirin", "contrast_dye", "latex", "nuts"],
                        random.randint(0, 2)
                    ),
                    "chronic_conditions": random.sample(
                        ["diabetes", "hypertension", "asthma", "arthritis"],
                        random.randint(0, 2)
                    ),
                    "medications": random.sample(
                        ["metformin", "lisinopril", "aspirin", "atorvastatin"],
                        random.randint(0, 2)
                    )
                }
            )
            patients.append(patient)
            session.add(patient)
        
        await session.commit()
        print(f"Created {count} patients")
        return patients


async def create_service_persons() -> list[ServicePerson]:
    """Create synthetic service persons."""
    service_persons = []
    async with async_session_maker() as session:
        # Create doctors for each service type
        for service_type in SERVICE_TYPES:
            for i in range(random.randint(2, 5)):
                username = f"{service_type}_{i+1}"
                service_person = ServicePerson(
                    username=username,
                    email=f"{username}@hospital.com",
                    password_hash=get_password_hash("password123"),
                    name=fake.name(),
                    service_type=service_type,
                    specialization=fake.job() if service_type != "general_consultation" else None,
                    is_active=True
                )
                service_persons.append(service_person)
                session.add(service_person)
        
        await session.commit()
        print(f"Created {len(service_persons)} service persons")
        return service_persons


async def create_admins() -> list[Admin]:
    """Create synthetic admins."""
    admins = []
    async with async_session_maker() as session:
        for i in range(3):
            admin = Admin(
                username=f"admin_{i+1}",
                email=f"admin_{i+1}@hospital.com",
                password_hash=get_password_hash("admin123"),
                role="admin" if i < 2 else "super_admin",
                is_active=True
            )
            admins.append(admin)
            session.add(admin)
        
        await session.commit()
        print(f"Created {len(admins)} admins")
        return admins


async def create_patient_history(patients: list[Patient], service_persons: list[ServicePerson]):
    """Create historical records for patients."""
    async with async_session_maker() as session:
        count = 0
        for patient in patients[:len(patients)//2]:  # Only for half the patients
            # Create 1-5 historical visits per patient
            for _ in range(random.randint(1, 5)):
                visit_date = fake.date_between(
                    start_date='-2y',
                    end_date='today'
                )
                
                service_type = random.choice(SERVICE_TYPES)
                history = PatientHistory(
                    patient_id=patient.patient_id,
                    visit_date=visit_date,
                    service_type=service_type,
                    diagnosis=fake.sentence(nb_words=5),
                    treatment=fake.sentence(nb_words=8),
                    prescriptions={
                        "medications": random.sample(
                            ["ibuprofen", "amoxicillin", "metformin"],
                            random.randint(0, 2)
                        )
                    },
                    test_results={
                        "blood_pressure": f"{random.randint(100, 140)}/{random.randint(60, 90)}",
                        "heart_rate": random.randint(60, 100)
                    },
                    notes=fake.text(max_nb_chars=200)
                )
                session.add(history)
                count += 1
        
        await session.commit()
        print(f"Created {count} patient history records")


async def create_past_appointments(patients: list[Patient], service_persons: list[ServicePerson]):
    """Create past appointments."""
    async with async_session_maker() as session:
        count = 0
        for patient in patients[:len(patients)//3]:  # Only for third of patients
            for _ in range(random.randint(1, 3)):
                scheduled_date = fake.date_time_between(
                    start_date='-1y',
                    end_date='-1d'
                )
                service_person = random.choice(service_persons)
                
                appointment = Appointment(
                    patient_id=patient.patient_id,
                    service_person_id=service_person.service_person_id,
                    appointment_type=random.choice(["consultation", "follow_up", "procedure"]),
                    scheduled_date=scheduled_date,
                    status=random.choice(["completed", "cancelled", "no_show"]),
                    notes=fake.text(max_nb_chars=100)
                )
                session.add(appointment)
                count += 1
        
        await session.commit()
        print(f"Created {count} past appointments")


async def main():
    """Main function to generate all synthetic data."""
    print("Starting synthetic data generation...")
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("Database tables created")
    
    # Create data
    patients = await create_patients(500)
    service_persons = await create_service_persons()
    admins = await create_admins()
    await create_patient_history(patients, service_persons)
    await create_past_appointments(patients, service_persons)
    
    print("Synthetic data generation completed!")


if __name__ == "__main__":
    asyncio.run(main())

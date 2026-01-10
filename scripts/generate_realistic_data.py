"""
Generate realistic synthetic data for all database tables.

This script generates data following all category constraints and maintains
proper relationships between tables. Data is saved as JSON files (one per table).
"""

import json
import random
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from faker import Faker

# Add project root to path
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.src.data.categories import (
    # Patient demographics
    GENDER_CATEGORIES,
    BLOOD_GROUP_CATEGORIES,
    EMERGENCY_CONTACT_RELATIONSHIP_CATEGORIES,
    CHRONIC_CONDITION_CATEGORIES,
    ALLERGY_CATEGORIES,
    SURGERY_CATEGORIES,
    # Service types
    SERVICE_TYPE_CATEGORIES,
    SERVICE_TYPE_TO_SPECIALIZATION,
    get_specializations_for_service_type,
    # Status categories
    TICKET_STATUS_CATEGORIES,
    TICKET_ASSIGNMENT_STATUS_CATEGORIES,
    TICKET_ASSIGNMENT_RECORD_STATUS_CATEGORIES,
    APPOINTMENT_STATUS_CATEGORIES,
    CONVERSATION_STATUS_CATEGORIES,
    # Medical categories
    DIAGNOSIS_CATEGORIES,
    TREATMENT_CATEGORIES,
    CASE_OUTCOME_CATEGORIES,
    # Other categories
    APPOINTMENT_TYPE_CATEGORIES,
    TICKET_UPDATE_TYPE_CATEGORIES,
    MESSAGE_SENDER_TYPE_CATEGORIES,
    HISTORY_SUMMARY_GENERATED_BY_CATEGORIES,
    ADMIN_ROLE_CATEGORIES,
    SYMPTOM_CATEGORIES,
    SYMPTOM_DURATION_CATEGORIES,
    SYMPTOM_SEVERITY_CATEGORIES,
    PRESCRIPTION_FREQUENCY_CATEGORIES,
    TEST_TYPE_CATEGORIES,
    CERTIFICATION_CATEGORIES,
    CERTIFICATION_ISSUING_BODY_CATEGORIES,
    EDUCATION_DEGREE_CATEGORIES,
    EDUCATION_COUNTRY_CATEGORIES,
    LANGUAGE_CATEGORIES,
    # Constraints
    PATIENT_AGE_MIN,
    PATIENT_AGE_MAX,
    DOCTOR_MIN_AGE,
    TEMPERATURE_MIN,
    TEMPERATURE_MAX,
    PULSE_MIN,
    PULSE_MAX,
    RESPIRATORY_RATE_MIN,
    RESPIRATORY_RATE_MAX,
    BLOOD_PRESSURE_SYSTOLIC_MIN,
    BLOOD_PRESSURE_SYSTOLIC_MAX,
    BLOOD_PRESSURE_DIASTOLIC_MIN,
    BLOOD_PRESSURE_DIASTOLIC_MAX,
    SATISFACTION_VALUES,
)

# Initialize Faker with Indian locale
fake = Faker('en_IN')
fake_en = Faker()  # For some English-specific data

# Output directory
OUTPUT_DIR = project_root / "backend" / "src" / "data" / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Common medication names (free-form, but realistic)
COMMON_MEDICATIONS = [
    "Paracetamol 500mg", "Ibuprofen 400mg", "Metformin 500mg", "Atenolol 25mg",
    "Amlodipine 5mg", "Losartan 50mg", "Omeprazole 20mg", "Cetirizine 10mg",
    "Salbutamol 100mcg", "Insulin Glargine 100IU/ml", "Levothyroxine 50mcg",
    "Furosemide 40mg", "Warfarin 5mg", "Amoxicillin 500mg", "Azithromycin 500mg",
    "Atorvastatin 10mg", "Aspirin 75mg", "Clopidogrel 75mg", "Pantoprazole 40mg"
]

# Indian city names
INDIAN_CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata", "Pune",
    "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Kanpur", "Nagpur", "Indore",
    "Thane", "Bhopal", "Visakhapatnam", "Patna", "Vadodara", "Ghaziabad"
]

# Indian states
INDIAN_STATES = [
    "Maharashtra", "Delhi", "Karnataka", "Telangana", "Tamil Nadu", "West Bengal",
    "Gujarat", "Rajasthan", "Uttar Pradesh", "Madhya Pradesh", "Andhra Pradesh",
    "Bihar", "Punjab", "Haryana", "Kerala", "Odisha", "Assam", "Jharkhand"
]


def get_password_hash(password: str) -> str:
    """Generate password hash using SHA256 (for admins and service_persons only).
    
    Note: This uses SHA256 for backward compatibility with existing data.
    Patients use bcrypt via auth_service.get_password_hash() during insertion.
    """
    import hashlib
    return hashlib.sha256(f"salt_{password}".encode()).hexdigest()


def generate_indian_phone() -> str:
    """Generate 10-digit Indian mobile number (starts with 6-9)."""
    first_digit = random.choice(['6', '7', '8', '9'])
    remaining = ''.join([str(random.randint(0, 9)) for _ in range(9)])
    return f"{first_digit}{remaining}"


def generate_indian_address() -> str:
    """Generate Indian address."""
    street = fake.street_address()
    city = random.choice(INDIAN_CITIES)
    state = random.choice(INDIAN_STATES)
    pincode = fake.postcode()
    return f"{street}, {city}, {state} - {pincode}"


def generate_patients(count: int = 600) -> List[Dict[str, Any]]:
    """Generate patient data."""
    patients = []
    today = date.today()
    
    for i in range(count):
        # Generate age and date of birth
        age = random.randint(PATIENT_AGE_MIN, PATIENT_AGE_MAX)
        dob = today - timedelta(days=age * 365 + random.randint(0, 364))
        
        gender = random.choice(GENDER_CATEGORIES)
        blood_group = random.choice(BLOOD_GROUP_CATEGORIES)
        
        # Medical history
        chronic_conditions = random.sample(
            [c for c in CHRONIC_CONDITION_CATEGORIES if c != "none"],
            random.randint(0, 3)
        ) or ["none"]
        
        allergies = random.sample(
            [a for a in ALLERGY_CATEGORIES if a != "none"],
            random.randint(0, 2)
        ) or ["none"]
        
        surgeries = random.sample(
            [s for s in SURGERY_CATEGORIES if s != "none"],
            random.randint(0, 2)
        ) or ["none"]
        
        # Medications (free-form)
        num_meds = random.randint(0, 3)
        medications = random.sample(COMMON_MEDICATIONS, min(num_meds, len(COMMON_MEDICATIONS)))
        
        # Emergency contact
        emergency_contact = {
            "name": fake.name(),
            "relationship": random.choice(EMERGENCY_CONTACT_RELATIONSHIP_CATEGORIES),
            "phone": generate_indian_phone(),
            "email": fake.email()
        }
        
        patient = {
            "patient_id": str(uuid.uuid4()),
            "name": fake.name(),
            "phone_number": generate_indian_phone(),
            "email": fake.email(),
            "date_of_birth": dob.isoformat(),
            "gender": gender,
            "address": generate_indian_address(),
            "emergency_contact": emergency_contact,
            "blood_group": blood_group,
            "medical_history": {
                "chronic_conditions": chronic_conditions,
                "allergies": allergies,
                "surgeries": surgeries,
                "medications": medications
            },
            "password": fake.password(length=12, special_chars=False)[:72],  # Bcrypt max is 72 bytes
            "created_at": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        patients.append(patient)
    
    return patients


def generate_admins(count: int = 5) -> List[Dict[str, Any]]:
    """Generate admin data."""
    admins = []
    
    for i in range(count):
        admin = {
            "admin_id": str(uuid.uuid4()),
            "username": f"admin_{i+1}",
            "email": f"admin_{i+1}@hospital.com",
            "password": "admin123",  # Plain text - will be hashed with bcrypt during insertion
            "role": "super_admin" if i == 0 else "admin",
            "is_active": True,
            "created_at": (datetime.now() - timedelta(days=random.randint(30, 365))).isoformat()
        }
        admins.append(admin)
    
    return admins


def generate_service_persons() -> List[Dict[str, Any]]:
    """Generate service person (doctor) data.
    
    Generates 11-12 doctors per service type.
    For each service type, 4-6 doctors will have high current workload (busy).
    """
    service_persons = []
    counter = {}
    
    # Generate 11-12 doctors per service type
    for service_type in SERVICE_TYPE_CATEGORIES:
        num_doctors = random.randint(11, 12)
        specializations = get_specializations_for_service_type(service_type)
        
        # Determine how many doctors should be busy (4-6)
        num_busy_doctors = random.randint(4, 6)
        
        # Create list to track which doctors will be busy
        busy_indices = set(random.sample(range(num_doctors), min(num_busy_doctors, num_doctors)))
        
        for i in range(num_doctors):
            if service_type not in counter:
                counter[service_type] = 0
            counter[service_type] += 1
            
            username = f"{service_type}_{counter[service_type]}"
            specialization = random.choice(specializations) if specializations else None
            
            max_workload = random.randint(5, 15)
            max_daily = random.randint(10, 20)
            
            # Determine if this doctor should be busy
            is_busy = i in busy_indices
            
            if is_busy:
                # Busy doctors: current_workload is 80-100% of max_workload
                workload_percentage = random.uniform(0.80, 1.0)
                current_workload = int(max_workload * workload_percentage)
                # Ensure at least 80% of max, but not exceeding max
                current_workload = min(current_workload, max_workload)
                # Make sure it's at least 1 if max_workload is small
                current_workload = max(1, current_workload)
                is_available = False  # Busy doctors are not available
            else:
                # Normal doctors: current_workload is 0-50% of max_workload
                workload_percentage = random.uniform(0.0, 0.5)
                current_workload = int(max_workload * workload_percentage)
                is_available = current_workload < max_workload and random.choice([True, True, False])
            
            service_person = {
                "service_person_id": str(uuid.uuid4()),
                "username": username,
                "email": f"{username}@hospital.com",
                "password": "password123",  # Plain text - will be hashed with bcrypt during insertion
                "name": fake.name(),
                "service_type": service_type,
                "specialization": specialization,
                "is_active": random.choice([True, True, True, False]),  # 75% active
                "current_workload": current_workload,
                "max_workload": max_workload,
                "max_daily_appointments": max_daily,
                "workload_updated_at": (datetime.now() - timedelta(hours=random.randint(1, 24))).isoformat() if random.random() > 0.3 else None,
                "is_available": is_available,
                "created_at": (datetime.now() - timedelta(days=random.randint(30, 730))).isoformat()
            }
            service_persons.append(service_person)
    
    return service_persons


def generate_doctor_expertise(service_persons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate doctor expertise records."""
    expertise_records = []
    
    for doctor in service_persons:
        service_type = doctor["service_type"]
        specializations = get_specializations_for_service_type(service_type)
        
        if not specializations:
            continue
        
        # Each doctor has 1-2 expertise records
        num_expertise = random.randint(1, 2)
        selected_specs = random.sample(specializations, min(num_expertise, len(specializations)))
        
        has_primary = False
        for idx, spec in enumerate(selected_specs):
            # Calculate doctor age (assume 25-60 years old)
            doctor_age = random.randint(25, 60)
            years_exp = random.randint(0, min(30, doctor_age - 23))
            
            # Certifications
            num_certs = random.randint(1, 3)
            certifications = []
            for _ in range(num_certs):
                cert_date = date.today() - timedelta(days=random.randint(365, 3650))
                cert = {
                    "certification_name": random.choice(CERTIFICATION_CATEGORIES),
                    "issuing_body": random.choice(CERTIFICATION_ISSUING_BODY_CATEGORIES),
                    "issue_date": cert_date.isoformat(),
                    "expiry_date": (cert_date + timedelta(days=365*5)).isoformat() if random.random() > 0.5 else None
                }
                certifications.append(cert)
            
            # Education
            num_edu = random.randint(1, 2)
            education = []
            for _ in range(num_edu):
                edu = {
                    "degree": random.choice(EDUCATION_DEGREE_CATEGORIES),
                    "institution": f"{fake_en.company()} Medical College",
                    "year": random.randint(1990, 2020),
                    "country": random.choice(EDUCATION_COUNTRY_CATEGORIES)
                }
                education.append(edu)
            
            # Languages (2-4 languages)
            num_langs = random.randint(2, 4)
            languages = random.sample(LANGUAGE_CATEGORIES, min(num_langs, len(LANGUAGE_CATEGORIES)))
            
            is_primary = not has_primary and (idx == 0 or random.random() > 0.5)
            if is_primary:
                has_primary = True
            
            expertise = {
                "expertise_id": str(uuid.uuid4()),
                "service_person_id": doctor["service_person_id"],
                "specialization_area": spec,
                "years_of_experience": years_exp,
                "certifications": certifications,
                "education": education,
                "languages_spoken": languages,
                "is_primary_specialization": is_primary,
                "created_at": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            expertise_records.append(expertise)
    
    return expertise_records


def generate_conversations(patients: List[Dict[str, Any]], count: int = 400) -> List[Dict[str, Any]]:
    """Generate conversation data."""
    conversations = []
    
    # Some patients have multiple conversations
    patient_ids = [p["patient_id"] for p in patients]
    extended_patient_ids = patient_ids + random.choices(patient_ids, k=count - len(patients))
    random.shuffle(extended_patient_ids)
    
    for i in range(count):
        patient_id = extended_patient_ids[i]
        status = random.choice(CONVERSATION_STATUS_CATEGORIES)
        
        started_at = datetime.now() - timedelta(days=random.randint(1, 90))
        ended_at = None
        if status in ["completed", "escalated"]:
            ended_at = started_at + timedelta(minutes=random.randint(5, 120))
        
        conversation = {
            "conversation_id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "status": status,
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat() if ended_at else None,
            "summary": fake.text(max_nb_chars=200) if status == "completed" else None,
            "llm_model": "gpt-4" if random.random() > 0.5 else None
        }
        conversations.append(conversation)
    
    return conversations


def generate_messages(conversations: List[Dict[str, Any]], patients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate message data."""
    messages = []
    patient_dict = {p["patient_id"]: p for p in patients}
    
    for conv in conversations:
        # Generate 3-8 messages per conversation
        num_messages = random.randint(3, 8)
        patient_id = conv["patient_id"]
        
        base_time = datetime.fromisoformat(conv["started_at"].replace('Z', '+00:00'))
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=None)
        
        for i in range(num_messages):
            # Alternate between patient and LLM
            sender_type = "patient" if i % 2 == 0 else "llm"
            sender_id = patient_id if sender_type == "patient" else None
            
            # Generate realistic content
            if sender_type == "patient":
                content = random.choice([
                    "I have been experiencing chest pain for the past 2 days",
                    "I need to schedule an appointment for a follow-up",
                    "I have a fever and cough",
                    "Can you help me with my medication refill?",
                    "I'm having severe headache",
                    "I need emergency care immediately"
                ])
            else:
                content = random.choice([
                    "I understand your concern. Let me help you with that.",
                    "Based on your symptoms, I recommend consulting a doctor.",
                    "I can help you schedule an appointment.",
                    "Please provide more details about your symptoms."
                ])
            
            message_time = base_time + timedelta(minutes=i * 2 + random.randint(0, 5))
            
            message = {
                "message_id": str(uuid.uuid4()),
                "conversation_id": conv["conversation_id"],
                "sender_type": sender_type,
                "sender_id": sender_id,
                "content": content,
                "message_metadata": None,
                "created_at": message_time.isoformat()
            }
            messages.append(message)
    
    return messages


def generate_tickets(conversations: List[Dict[str, Any]], patients: List[Dict[str, Any]], 
                     service_persons: List[Dict[str, Any]], count: int = 250) -> List[Dict[str, Any]]:
    """Generate ticket data."""
    tickets = []
    patient_dict = {p["patient_id"]: p for p in patients}
    service_person_by_type = {}
    for sp in service_persons:
        if sp["service_type"] not in service_person_by_type:
            service_person_by_type[sp["service_type"]] = []
        service_person_by_type[sp["service_type"]].append(sp)
    
    # Select conversations that will have tickets
    ticket_conversations = random.sample(conversations, min(count, len(conversations)))
    
    for i, conv in enumerate(ticket_conversations):
        patient_id = conv["patient_id"]
        patient = patient_dict[patient_id]
        
        # Determine service type
        service_type = random.choice(SERVICE_TYPE_CATEGORIES)
        
        # Priority based on service type
        if service_type == "emergency":
            priority = random.choice([1, 2])
        else:
            priority = random.choice([2, 3, 4, 5])
        
        # Status and assignment
        status = random.choice(TICKET_STATUS_CATEGORIES)
        assignment_status = random.choice(TICKET_ASSIGNMENT_STATUS_CATEGORIES)
        
        assigned_to = None
        accepted_by = None
        assigned_at = None
        accepted_at = None
        
        if status in ["assigned", "in_progress", "completed"]:
            if service_type in service_person_by_type:
                assigned_to = random.choice(service_person_by_type[service_type])["service_person_id"]
                assigned_at = datetime.now() - timedelta(hours=random.randint(1, 48))
        
        if assignment_status == "accepted":
            if service_type in service_person_by_type:
                # When accepted, set both accepted_by and assigned_to to the same person
                accepted_person = random.choice(service_person_by_type[service_type])
                accepted_by = accepted_person["service_person_id"]
                accepted_at = datetime.now() - timedelta(hours=random.randint(1, 24))
                # Ensure assigned_to is also set when ticket is accepted
                if assigned_to is None:
                    assigned_to = accepted_by
                    assigned_at = accepted_at
        
        # Calculate age from DOB
        dob = date.fromisoformat(patient["date_of_birth"])
        age = (date.today() - dob).days // 365
        
        # Symptoms
        num_symptoms = random.randint(1, 3)
        symptoms_list = random.sample(SYMPTOM_CATEGORIES, min(num_symptoms, len(SYMPTOM_CATEGORIES)))
        
        # Vital signs
        temperature = round(random.uniform(TEMPERATURE_MIN, TEMPERATURE_MAX), 1)
        systolic = random.randint(BLOOD_PRESSURE_SYSTOLIC_MIN, BLOOD_PRESSURE_SYSTOLIC_MAX)
        diastolic = random.randint(BLOOD_PRESSURE_DIASTOLIC_MIN, min(systolic - 10, BLOOD_PRESSURE_DIASTOLIC_MAX))
        pulse = random.randint(PULSE_MIN, PULSE_MAX)
        resp_rate = random.randint(RESPIRATORY_RATE_MIN, RESPIRATORY_RATE_MAX)
        
        ticket = {
            "ticket_id": str(uuid.uuid4()),
            "conversation_id": conv["conversation_id"],
            "patient_id": patient_id,
            "service_type": service_type,
            "status": status,
            "priority": priority,
            "assigned_to": assigned_to,
            "description": fake.text(max_nb_chars=300),
            "patient_details": {
                "age": age,
                "gender": patient["gender"],
                "chief_complaint": random.choice([
                    "Chest pain", "Fever", "Headache", "Abdominal pain", "Shortness of breath"
                ]),
                "vital_signs": {
                    "temperature": temperature,
                    "blood_pressure": f"{systolic}/{diastolic} mmHg",
                    "pulse": pulse,
                    "respiratory_rate": resp_rate
                }
            },
            "past_history_summary": fake.text(max_nb_chars=200) if random.random() > 0.5 else None,
            "llm_summary": fake.text(max_nb_chars=200) if random.random() > 0.5 else None,
            "current_symptoms": {
                "symptoms": symptoms_list,
                "duration": random.choice(SYMPTOM_DURATION_CATEGORIES),
                "severity": random.choice(SYMPTOM_SEVERITY_CATEGORIES)
            },
            "created_at": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
            "assigned_at": assigned_at.isoformat() if assigned_at else None,
            "completed_at": (datetime.now() - timedelta(hours=random.randint(1, 12))).isoformat() if status == "completed" else None,
            "assignment_status": assignment_status,
            "offered_to_count": random.randint(0, 5) if assignment_status in ["offered", "accepted"] else 0,
            "accepted_by": accepted_by,
            "accepted_at": accepted_at.isoformat() if accepted_at else None
        }
        tickets.append(ticket)
    
    return tickets


def generate_ticket_assignments(tickets: List[Dict[str, Any]], service_persons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate ticket assignment data."""
    assignments = []
    service_person_by_type = {}
    for sp in service_persons:
        if sp["service_type"] not in service_person_by_type:
            service_person_by_type[sp["service_type"]] = []
        service_person_by_type[sp["service_type"]].append(sp)
    
    for ticket in tickets:
        service_type = ticket["service_type"]
        if service_type not in service_person_by_type:
            continue
        
        # Generate 2-3 assignments per ticket
        num_assignments = random.randint(2, 3)
        available_doctors = service_person_by_type[service_type].copy()
        random.shuffle(available_doctors)
        
        has_accepted = False
        for rank in range(1, min(num_assignments + 1, len(available_doctors) + 1)):
            doctor = available_doctors[rank - 1]
            
            # Status logic
            if not has_accepted and random.random() > 0.6:
                status = "accepted"
                has_accepted = True
                responded_at = datetime.now() - timedelta(hours=random.randint(1, 12))
            else:
                status = random.choice(["pending", "rejected", "expired"])
                responded_at = datetime.now() - timedelta(hours=random.randint(1, 24)) if status != "pending" else None
            
            assigned_at = datetime.now() - timedelta(hours=random.randint(12, 48))
            expires_at = assigned_at + timedelta(hours=24) if status == "pending" else None
            
            assignment = {
                "assignment_id": str(uuid.uuid4()),
                "ticket_id": ticket["ticket_id"],
                "service_person_id": doctor["service_person_id"],
                "rank": rank,
                "status": status,
                "assigned_at": assigned_at.isoformat(),
                "responded_at": responded_at.isoformat() if responded_at else None,
                "response_notes": fake.text(max_nb_chars=100) if responded_at else None,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "created_at": assigned_at.isoformat()
            }
            assignments.append(assignment)
    
    return assignments


def generate_appointments(patients: List[Dict[str, Any]], tickets: List[Dict[str, Any]], 
                          service_persons: List[Dict[str, Any]], count: int = 200) -> List[Dict[str, Any]]:
    """Generate appointment data."""
    appointments = []
    service_person_by_type = {}
    for sp in service_persons:
        if sp["service_type"] not in service_person_by_type:
            service_person_by_type[sp["service_type"]] = []
        service_person_by_type[sp["service_type"]].append(sp)
    
    # Some appointments linked to tickets, some independent
    ticket_appointments = random.sample(tickets, min(count // 2, len(tickets)))
    independent_count = count - len(ticket_appointments)
    
    # Ticket-linked appointments
    for ticket in ticket_appointments:
        service_type = ticket["service_type"]
        if service_type in service_person_by_type:
            service_person = random.choice(service_person_by_type[service_type])
            
            scheduled_date = datetime.now() + timedelta(days=random.randint(1, 30))
            status = random.choice(APPOINTMENT_STATUS_CATEGORIES)
            
            appointment = {
                "appointment_id": str(uuid.uuid4()),
                "ticket_id": ticket["ticket_id"],
                "patient_id": ticket["patient_id"],
                "service_person_id": service_person["service_person_id"],
                "appointment_type": random.choice(APPOINTMENT_TYPE_CATEGORIES),
                "scheduled_date": scheduled_date.isoformat(),
                "status": status,
                "notes": fake.text(max_nb_chars=150) if random.random() > 0.5 else None,
                "created_at": (datetime.now() - timedelta(days=random.randint(1, 7))).isoformat()
            }
            appointments.append(appointment)
    
    # Independent appointments
    for _ in range(independent_count):
        patient = random.choice(patients)
        service_type = random.choice(SERVICE_TYPE_CATEGORIES)
        
        if service_type in service_person_by_type:
            service_person = random.choice(service_person_by_type[service_type])
            
            scheduled_date = datetime.now() + timedelta(days=random.randint(1, 60))
            
            appointment = {
                "appointment_id": str(uuid.uuid4()),
                "ticket_id": None,
                "patient_id": patient["patient_id"],
                "service_person_id": service_person["service_person_id"],
                "appointment_type": random.choice(APPOINTMENT_TYPE_CATEGORIES),
                "scheduled_date": scheduled_date.isoformat(),
                "status": random.choice(APPOINTMENT_STATUS_CATEGORIES),
                "notes": fake.text(max_nb_chars=150) if random.random() > 0.5 else None,
                "created_at": (datetime.now() - timedelta(days=random.randint(1, 14))).isoformat()
            }
            appointments.append(appointment)
    
    return appointments


def generate_patient_history(patients: List[Dict[str, Any]], count: int = 600) -> List[Dict[str, Any]]:
    """Generate patient history records."""
    history_records = []
    
    # Distribute history across patients (2-3 visits per patient on average)
    patient_ids = [p["patient_id"] for p in patients]
    extended_patient_ids = patient_ids + random.choices(patient_ids, k=count - len(patients))
    random.shuffle(extended_patient_ids)
    
    for i in range(count):
        patient_id = extended_patient_ids[i]
        visit_date = date.today() - timedelta(days=random.randint(1, 730))  # Past 2 years
        service_type = random.choice(SERVICE_TYPE_CATEGORIES)
        
        # Diagnosis and treatment
        diagnosis = random.choice(DIAGNOSIS_CATEGORIES)
        treatment = random.choice(TREATMENT_CATEGORIES)
        
        # Prescriptions
        num_prescriptions = random.randint(0, 3)
        prescriptions = []
        for _ in range(num_prescriptions):
            prescription = {
                "medication_name": random.choice(COMMON_MEDICATIONS),
                "dosage": f"{random.randint(1, 10) * 50}mg",
                "frequency": random.choice(PRESCRIPTION_FREQUENCY_CATEGORIES),
                "duration": random.choice(["7 days", "14 days", "30 days", "ongoing"])
            }
            prescriptions.append(prescription)
        
        # Test results
        num_tests = random.randint(0, 2)
        test_results = []
        for _ in range(num_tests):
            test_type = random.choice(TEST_TYPE_CATEGORIES)
            test_result = {
                "test_name": f"{test_type.replace('_', ' ').title()}",
                "test_type": test_type,
                "result": str(random.randint(70, 150)) if test_type == "blood_test" else "Normal",
                "unit": "mg/dL" if test_type == "blood_test" else None,
                "reference_range": "70-100 mg/dL" if test_type == "blood_test" else "Normal"
            }
            test_results.append(test_result)
        
        history = {
            "history_id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "visit_date": visit_date.isoformat(),
            "service_type": service_type,
            "diagnosis": diagnosis,
            "treatment": treatment,
            "prescriptions": prescriptions,
            "test_results": test_results,
            "notes": fake.text(max_nb_chars=200) if random.random() > 0.5 else None,
            "created_at": (datetime.now() - timedelta(days=random.randint(1, 730))).isoformat()
        }
        history_records.append(history)
    
    return history_records


def generate_doctor_case_history(service_persons: List[Dict[str, Any]], patients: List[Dict[str, Any]], 
                                  tickets: List[Dict[str, Any]], count: int = 400) -> List[Dict[str, Any]]:
    """Generate doctor case history."""
    case_history = []
    service_person_by_type = {}
    for sp in service_persons:
        if sp["service_type"] not in service_person_by_type:
            service_person_by_type[sp["service_type"]] = []
        service_person_by_type[sp["service_type"]].append(sp)
    
    # Distribute cases across doctors
    for _ in range(count):
        service_type = random.choice(SERVICE_TYPE_CATEGORIES)
        if service_type not in service_person_by_type:
            continue
        
        doctor = random.choice(service_person_by_type[service_type])
        patient = random.choice(patients)
        
        # Link to ticket if available
        matching_tickets = [t for t in tickets if t["service_type"] == service_type]
        ticket = random.choice(matching_tickets) if matching_tickets else None
        
        # Complexity based on service type
        if service_type == "emergency":
            complexity = random.choice([3, 4, 5])
        else:
            complexity = random.choice([1, 2, 3, 4])
        
        outcome = random.choice(CASE_OUTCOME_CATEGORIES)
        completion_date = date.today() - timedelta(days=random.randint(1, 365)) if outcome != "ongoing" else None
        
        case = {
            "case_id": str(uuid.uuid4()),
            "service_person_id": doctor["service_person_id"],
            "ticket_id": ticket["ticket_id"] if ticket else None,
            "patient_id": patient["patient_id"],
            "service_type": service_type,
            "diagnosis_category": random.choice(DIAGNOSIS_CATEGORIES),
            "case_complexity": complexity,
            "outcome": outcome,
            "completion_date": completion_date.isoformat() if completion_date else None,
            "patient_satisfaction_score": random.choice(SATISFACTION_VALUES) if outcome == "successful" and random.random() > 0.3 else None,
            "notes": fake.text(max_nb_chars=200) if random.random() > 0.5 else None,
            "created_at": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat()
        }
        case_history.append(case)
    
    return case_history


def generate_ticket_updates(tickets: List[Dict[str, Any]], service_persons: List[Dict[str, Any]], 
                            admins: List[Dict[str, Any]], count: int = 300) -> List[Dict[str, Any]]:
    """Generate ticket update records."""
    updates = []
    
    # Select tickets for updates
    ticket_updates = random.sample(tickets, min(count, len(tickets)))
    all_updaters = [sp["service_person_id"] for sp in service_persons] + [a["admin_id"] for a in admins]
    
    for ticket in ticket_updates:
        num_updates = random.randint(1, 2)
        
        for _ in range(num_updates):
            updated_by = random.choice(all_updaters)
            update_type = random.choice(TICKET_UPDATE_TYPE_CATEGORIES)
            
            if update_type == "status_change":
                old_value = ticket["status"]
                new_value = random.choice([s for s in TICKET_STATUS_CATEGORIES if s != old_value])
            elif update_type == "assignment":
                old_value = "unassigned"
                new_value = "assigned"
            else:
                old_value = None
                new_value = None
            
            update = {
                "update_id": str(uuid.uuid4()),
                "ticket_id": ticket["ticket_id"],
                "updated_by": updated_by,
                "update_type": update_type,
                "old_value": old_value,
                "new_value": new_value,
                "comment": fake.text(max_nb_chars=100) if random.random() > 0.5 else None,
                "created_at": (datetime.now() - timedelta(hours=random.randint(1, 48))).isoformat()
            }
            updates.append(update)
    
    return updates


def generate_patient_history_summaries(patients: List[Dict[str, Any]], tickets: List[Dict[str, Any]], 
                                       count: int = 150) -> List[Dict[str, Any]]:
    """Generate patient history summary records."""
    summaries = []
    
    # Select patients for summaries
    summary_patients = random.sample(patients, min(count, len(patients)))
    patient_versions = {}
    
    for patient in summary_patients:
        patient_id = patient["patient_id"]
        if patient_id not in patient_versions:
            patient_versions[patient_id] = 0
        patient_versions[patient_id] += 1
        
        # Link to ticket if available
        patient_tickets = [t for t in tickets if t["patient_id"] == patient_id]
        ticket = random.choice(patient_tickets) if patient_tickets and random.random() > 0.5 else None
        
        summary = {
            "summary_id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "summary_text": fake.text(max_nb_chars=500),
            "summary_version": patient_versions[patient_id],
            "generated_by": random.choice(HISTORY_SUMMARY_GENERATED_BY_CATEGORIES),
            "ticket_id": ticket["ticket_id"] if ticket else None,
            "includes_history_until": (date.today() - timedelta(days=random.randint(1, 90))).isoformat() if random.random() > 0.5 else None,
            "created_at": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat()
        }
        summaries.append(summary)
    
    return summaries


def save_json(data: List[Dict[str, Any]], filename: str):
    """Save data to JSON file."""
    filepath = OUTPUT_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(data)} records to {filename}")


def main():
    """Main function to generate all data."""
    print("=" * 60)
    print("Generating Realistic Healthcare Data")
    print("=" * 60)
    print()
    
    # Generate in dependency order
    print("Generating patients...")
    patients = generate_patients(300)
    save_json(patients, "patients.json")
    
    print("Generating admins...")
    admins = generate_admins(5)
    save_json(admins, "admins.json")
    
    print("Generating service persons...")
    service_persons = generate_service_persons()
    save_json(service_persons, "service_persons.json")
    
    print("Generating doctor expertise...")
    doctor_expertise = generate_doctor_expertise(service_persons)
    save_json(doctor_expertise, "doctor_expertise.json")
    
    print("Generating conversations...")
    conversations = generate_conversations(patients, 400)
    save_json(conversations, "conversations.json")
    
    # Messages are now handled by LangGraph checkpointer, not generated as JSON
    # print("Generating messages...")
    # messages = generate_messages(conversations, patients)
    # save_json(messages, "messages.json")
    
    print("Generating tickets...")
    tickets = generate_tickets(conversations, patients, service_persons, 250)
    save_json(tickets, "tickets.json")
    
    print("Generating ticket assignments...")
    ticket_assignments = generate_ticket_assignments(tickets, service_persons)
    save_json(ticket_assignments, "ticket_assignments.json")
    
    print("Generating appointments...")
    appointments = generate_appointments(patients, tickets, service_persons, 200)
    save_json(appointments, "appointments.json")
    
    print("Generating patient history...")
    patient_history = generate_patient_history(patients, 600)
    save_json(patient_history, "patient_history.json")
    
    print("Generating doctor case history...")
    doctor_case_history = generate_doctor_case_history(service_persons, patients, tickets, 400)
    save_json(doctor_case_history, "doctor_case_history.json")
    
    print("Generating ticket updates...")
    ticket_updates = generate_ticket_updates(tickets, service_persons, admins, 300)
    save_json(ticket_updates, "ticket_updates.json")
    
    print("Generating patient history summaries...")
    patient_history_summaries = generate_patient_history_summaries(patients, tickets, 150)
    save_json(patient_history_summaries, "patient_history_summaries.json")
    
    print()
    print("=" * 60)
    print("Data generation completed!")
    print(f"All JSON files saved to: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()

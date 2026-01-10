"""Validate generated data against category constraints."""
import json
import re
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.src.data.categories import (
    SERVICE_TYPE_CATEGORIES,
    TICKET_STATUS_CATEGORIES,
    GENDER_CATEGORIES,
    BLOOD_GROUP_CATEGORIES,
    DIAGNOSIS_CATEGORIES,
    SYMPTOM_CATEGORIES,
    get_specializations_for_service_type,
)
from backend.src.data.validators import (
    validate_phone_number,
    validate_emergency_priority,
    validate_specialization_service_type_match,
)

DATA_DIR = project_root / "backend" / "src" / "data" / "generated"


def validate_patients():
    """Validate patient data."""
    with open(DATA_DIR / "patients.json") as f:
        patients = json.load(f)
    
    errors = []
    for patient in patients:
        # Validate phone number
        is_valid, error = validate_phone_number(patient["phone_number"])
        if not is_valid:
            errors.append(f"Patient {patient['patient_id']}: {error}")
        
        # Validate gender
        if patient["gender"] not in GENDER_CATEGORIES:
            errors.append(f"Patient {patient['patient_id']}: Invalid gender {patient['gender']}")
        
        # Validate blood group
        if patient["blood_group"] not in BLOOD_GROUP_CATEGORIES:
            errors.append(f"Patient {patient['patient_id']}: Invalid blood_group {patient['blood_group']}")
    
    print(f"Validated {len(patients)} patients")
    if errors:
        print(f"Found {len(errors)} errors")
        for error in errors[:5]:
            print(f"  - {error}")
    else:
        print("  All patients valid!")
    return len(errors) == 0


def validate_tickets():
    """Validate ticket data."""
    with open(DATA_DIR / "tickets.json") as f:
        tickets = json.load(f)
    
    errors = []
    for ticket in tickets:
        # Validate service type
        if ticket["service_type"] not in SERVICE_TYPE_CATEGORIES:
            errors.append(f"Ticket {ticket['ticket_id']}: Invalid service_type {ticket['service_type']}")
        
        # Validate status
        if ticket["status"] not in TICKET_STATUS_CATEGORIES:
            errors.append(f"Ticket {ticket['ticket_id']}: Invalid status {ticket['status']}")
        
        # Validate emergency priority rule
        is_valid, error = validate_emergency_priority(ticket["service_type"], ticket["priority"])
        if not is_valid:
            errors.append(f"Ticket {ticket['ticket_id']}: {error}")
        
        # Validate symptoms
        if ticket.get("current_symptoms"):
            for symptom in ticket["current_symptoms"].get("symptoms", []):
                if symptom not in SYMPTOM_CATEGORIES and symptom != "other":
                    errors.append(f"Ticket {ticket['ticket_id']}: Invalid symptom {symptom}")
    
    print(f"Validated {len(tickets)} tickets")
    if errors:
        print(f"Found {len(errors)} errors")
        for error in errors[:5]:
            print(f"  - {error}")
    else:
        print("  All tickets valid!")
    return len(errors) == 0


def validate_service_persons():
    """Validate service person data."""
    with open(DATA_DIR / "service_persons.json") as f:
        service_persons = json.load(f)
    
    errors = []
    for sp in service_persons:
        # Validate service type
        if sp["service_type"] not in SERVICE_TYPE_CATEGORIES:
            errors.append(f"ServicePerson {sp['service_person_id']}: Invalid service_type {sp['service_type']}")
        
        # Validate specialization matches service type
        if sp.get("specialization"):
            is_valid, error = validate_specialization_service_type_match(sp["specialization"], sp["service_type"])
            if not is_valid:
                errors.append(f"ServicePerson {sp['service_person_id']}: {error}")
        
        # Validate workload
        if sp["current_workload"] > sp["max_workload"]:
            errors.append(f"ServicePerson {sp['service_person_id']}: current_workload exceeds max_workload")
    
    print(f"Validated {len(service_persons)} service persons")
    if errors:
        print(f"Found {len(errors)} errors")
        for error in errors[:5]:
            print(f"  - {error}")
    else:
        print("  All service persons valid!")
    return len(errors) == 0


def main():
    """Main validation function."""
    print("=" * 60)
    print("Validating Generated Data")
    print("=" * 60)
    print()
    
    all_valid = True
    all_valid &= validate_patients()
    print()
    all_valid &= validate_service_persons()
    print()
    all_valid &= validate_tickets()
    print()
    
    print("=" * 60)
    if all_valid:
        print("All data validation passed!")
    else:
        print("Some validation errors found. Please review.")
    print("=" * 60)


if __name__ == "__main__":
    main()

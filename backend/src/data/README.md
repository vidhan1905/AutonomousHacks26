# Healthcare Database Categories & Constraints Documentation

This directory contains the category definitions and validation functions for the hospital AI platform database schema.

## Files

- `categories.py` - All category definitions (enum-like values)
- `validators.py` - Validation functions that enforce constraints
- `README.md` - This documentation file

## Overview

All categories are **STRICT constraints** - no values outside the defined lists are allowed. These categories are designed to be:

- Realistic for Indian hospitals
- Non-diagnostic (high-level medical categories only)
- Finite and closed (NO free-text)
- Reusable across multiple tables

## Service Type to Specialization Mappings

The following table shows which specialization areas are valid for each service type:

| Service Type | Valid Specialization Areas |
|-------------|---------------------------|
| `general_consultation` | `general_medicine`, `family_medicine`, `internal_medicine` |
| `emergency` | `emergency_medicine`, `trauma_care`, `critical_care` |
| `cardiology` | `cardiac_surgery`, `interventional_cardiology`, `cardiac_electrophysiology` |
| `orthopedics` | `joint_replacement`, `sports_medicine`, `spine_surgery`, `trauma_orthopedics` |
| `pediatrics` | `pediatric_cardiology`, `pediatric_oncology`, `neonatology`, `pediatric_surgery` |
| `gynecology` | `obstetrics`, `reproductive_medicine`, `gynecological_oncology` |
| `dermatology` | `cosmetic_dermatology`, `dermatopathology`, `pediatric_dermatology` |
| `ophthalmology` | `retina`, `cornea`, `glaucoma`, `pediatric_ophthalmology` |
| `ent` | `otology`, `rhinology`, `laryngology`, `head_neck_surgery` |
| `neurology` | `stroke`, `epilepsy`, `movement_disorders`, `neurocritical_care` |
| `psychiatry` | `adult_psychiatry`, `child_psychiatry`, `addiction_psychiatry` |
| `oncology` | `medical_oncology`, `surgical_oncology`, `radiation_oncology` |
| `urology` | `urologic_oncology`, `pediatric_urology`, `reconstructive_urology` |
| `gastroenterology` | `hepatology`, `endoscopy`, `inflammatory_bowel_disease` |
| `pulmonology` | `critical_care_pulmonology`, `sleep_medicine`, `interventional_pulmonology` |
| `endocrinology` | `diabetes`, `thyroid_disorders`, `reproductive_endocrinology` |
| `radiology` | `diagnostic_radiology`, `interventional_radiology`, `nuclear_medicine` |
| `pathology` | `clinical_pathology`, `anatomic_pathology`, `forensic_pathology` |
| `anesthesiology` | `pain_management`, `critical_care_anesthesia`, `pediatric_anesthesia` |

### Usage

```python
from backend.src.data.categories import get_specializations_for_service_type, is_valid_specialization_for_service_type

# Get valid specializations for a service type
specializations = get_specializations_for_service_type("cardiology")
# Returns: ['cardiac_surgery', 'interventional_cardiology', 'cardiac_electrophysiology']

# Check if a specialization is valid for a service type
is_valid = is_valid_specialization_for_service_type("cardiac_surgery", "cardiology")
# Returns: True
```

## Cross-Table Category Relationships

### Service Type Usage

The `service_type` category is used in multiple tables and must be consistent:

- `service_persons.service_type` - Defines what type of service the doctor provides
- `tickets.service_type` - Defines what type of service the ticket requires
- `patient_history.service_type` - Defines what type of service was provided
- `doctor_case_history.service_type` - Defines what type of service was handled

**Rule**: When assigning a ticket to a doctor, `tickets.service_type` must match `service_persons.service_type`.

### Status Field Relationships

Different status fields are used in different contexts:

#### Ticket Status Flow
```
open → offered → assigned → in_progress → completed
  ↓                                    ↓
cancelled                          cancelled
```

#### Ticket Assignment Status Flow
```
unassigned → offered → accepted
              ↓          ↓
         rejected_all  (locked)
```

#### Ticket Assignment Record Status
- `pending` - Doctor has been offered the ticket, awaiting response
- `accepted` - Doctor accepted the ticket (only one per ticket)
- `rejected` - Doctor rejected the ticket
- `expired` - Offer expired without response

### Priority and Complexity Relationships

#### Emergency Rules
- If `tickets.service_type = "emergency"`:
  - `tickets.priority` MUST be 1 or 2
  - `doctor_case_history.case_complexity` MUST be 3, 4, or 5

#### Non-Emergency Rules
- If `tickets.service_type != "emergency"`:
  - `tickets.priority` CANNOT be 1 (critical)
  - `doctor_case_history.case_complexity` typically 1, 2, or 3

### Diagnosis Category to Service Type Alignment

While not strictly enforced, diagnosis categories should align with service types:

| Service Type | Typical Diagnosis Categories |
|-------------|----------------------------|
| `cardiology` | `cardiovascular` |
| `orthopedics` | `musculoskeletal`, `trauma_injury` |
| `pediatrics` | `fever_infection`, `respiratory_issue` |
| `gynecology` | `genitourinary` |
| `dermatology` | `dermatological` |
| `ophthalmology` | `ophthalmic` |
| `ent` | `ent_related` |
| `neurology` | `neurological` |
| `psychiatry` | `mental_health` |
| `oncology` | Various (depends on cancer type) |
| `gastroenterology` | `gastrointestinal` |
| `pulmonology` | `respiratory_issue` |
| `endocrinology` | `endocrine_metabolic` |
| `emergency` | `trauma_injury`, `cardiovascular`, `respiratory_issue` |

## Validation Rules Summary

### Patient Validation
- **Age**: 0-100 years
- **Phone Number**: Exactly 10 digits, starting with 6-9 (India format)
- **Date of Birth**: Must match calculated age
- **Gender**: One of 4 values: `male`, `female`, `other`, `prefer_not_to_say`
- **Blood Group**: One of 8 standard types: `A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-`

### Doctor Validation
- **Age**: Minimum 23 years (after MBBS completion)
- **Experience**: 0-50 years
- **Experience-Age Rule**: `years_of_experience <= (doctor_age - 23)`
- **Specialization**: Must be valid for `service_type`

### Workload Validation
- **Current Workload**: 0 to `max_workload`
- **Max Workload**: 1-50 (default: 10)
- **Max Daily Appointments**: 1-50 (default: 15)
- **Rule**: `current_workload` cannot exceed `max_workload`
- **Rule**: Daily appointment count cannot exceed `max_daily_appointments`

### Ticket Validation
- **Priority**: 1-5 (integer)
- **Emergency Priority Rule**: Emergency tickets must have priority 1 or 2
- **Non-Emergency Priority Rule**: Non-emergency tickets cannot have priority 1
- **Assignment Rank**: Must be unique per ticket, sequential starting from 1
- **Assignment Acceptance**: Only one assignment per ticket can be accepted

### Vital Signs Validation
- **Temperature**: 95.0-105.0°F (35.0-40.5°C)
- **Pulse**: 40-150 bpm
- **Respiratory Rate**: 10-30 per minute
- **Blood Pressure**: Format "XXX/YY mmHg", systolic 70-200, diastolic 40-120, diastolic < systolic

### Date Validation
- **Scheduled Date**: Must be >= current date (future appointments)
- **Completion Date**: Must be >= `created_at` date
- **Expires At**: Must be > `assigned_at` (for ticket assignments)
- **Responded At**: Must be >= `assigned_at` (if not NULL)

## JSON Field Structures

### Emergency Contact
```json
{
  "name": "string",
  "relationship": "spouse|parent|child|sibling|relative|friend|guardian|other",
  "phone": "10-digit-number",
  "email": "string (optional)"
}
```

### Current Symptoms
```json
{
  "symptoms": ["fever", "cough", ...],
  "duration": "acute|subacute|chronic",
  "severity": "mild|moderate|severe"
}
```

### Medical History
```json
{
  "chronic_conditions": ["hypertension", "diabetes", ...],
  "allergies": ["medication", "food", ...],
  "surgeries": ["cardiac", "orthopedic", ...],
  "medications": ["metformin 500mg", "atenolol 25mg", ...]  // Free-form: current/ongoing medications
}
```

**Note**: `medications` in medical_history are **free-form strings** (not controlled categories). These represent medications the patient is currently taking or has been on long-term. This allows for any medication name (generic or brand) as prescribed by doctors.

### Prescriptions
```json
[
  {
    "medication_name": "string (free-form)",  // Any medication name (generic or brand)
    "dosage": "Xmg|Xml|X units",
    "frequency": "once_daily|twice_daily|...",
    "duration": "X days|X weeks|X months|ongoing"
  }
]
```

**Note**: `medication_name` in prescriptions is **free-form** (not controlled categories). This allows doctors to prescribe any medication as needed for the specific visit.

### Test Results
```json
[
  {
    "test_name": "string",
    "test_type": "blood_test|urine_test|imaging|ecg|biopsy|culture|other",
    "result": "string or number",
    "unit": "string",
    "reference_range": "string"
  }
]
```

### Patient Details (Vital Signs)
```json
{
  "age": 0-100,
  "gender": "male|female|other|prefer_not_to_say",
  "chief_complaint": "string",
  "vital_signs": {
    "temperature": 95.0-105.0,
    "blood_pressure": "XXX/YY mmHg",
    "pulse": 40-150,
    "respiratory_rate": 10-30
  }
}
```

### Certifications
```json
[
  {
    "certification_name": "mbbs|md|ms|dm|mch|dnb|frcs|usmle|plab|other",
    "issuing_body": "mci|state_medical_council|international_board|university|other",
    "issue_date": "YYYY-MM-DD",
    "expiry_date": "YYYY-MM-DD (optional)"
  }
]
```

### Education
```json
[
  {
    "degree": "mbbs|md|ms|dm|mch|dnb|bds|bams|bhms|bpt|other",
    "institution": "string",
    "year": 1900-2024,
    "country": "india|usa|uk|australia|canada|other"
  }
]
```

### Languages Spoken
```json
["hindi", "english", "tamil", ...]
```

## Usage Examples

### Validating a Category
```python
from backend.src.data.validators import validate_service_type, validate_gender

# Validate service type
is_valid, error = validate_service_type("cardiology")
if not is_valid:
    print(f"Error: {error}")

# Validate gender
is_valid, error = validate_gender("male")
if not is_valid:
    print(f"Error: {error}")
```

### Validating Business Rules
```python
from backend.src.data.validators import validate_emergency_priority, validate_specialization_service_type_match

# Validate emergency priority rule
is_valid, error = validate_emergency_priority("emergency", 1)
if not is_valid:
    print(f"Error: {error}")

# Validate specialization-service type match
is_valid, error = validate_specialization_service_type_match("cardiac_surgery", "cardiology")
if not is_valid:
    print(f"Error: {error}")
```

### Validating Complex Data
```python
from backend.src.data.validators import validate_phone_number, validate_age_date_of_birth_match
from datetime import date

# Validate phone number
is_valid, error = validate_phone_number("9876543210")
if not is_valid:
    print(f"Error: {error}")

# Validate age and date of birth match
dob = date(1990, 1, 1)
age = 34
is_valid, error = validate_age_date_of_birth_match(age, dob)
if not is_valid:
    print(f"Error: {error}")
```

## Important Notes

1. **Strict Enforcement**: All categories are HARD constraints. Values outside the defined lists are invalid.

2. **India-Specific**: Phone numbers, languages, and medical education follow India standards.

3. **Non-Diagnostic**: Diagnosis categories are high-level only. No specific disease names are allowed.

4. **Reusability**: Categories are defined once and reused across multiple tables.

5. **Validation**: All rules must be enforced during data generation and insertion.

6. **Future-Proof**: When adding new categories, update both `categories.py` and `validators.py`, and document here.

## Category Count Summary

- **Service Types**: 19
- **Specialization Areas**: 60+ (mapped to service types)
- **Status Categories**: 20+ (across different tables)
- **Medical Categories**: 17 (diagnosis), 8 (treatment), 9 (chronic conditions)
- **Demographic Categories**: 4 (gender), 8 (blood group)
- **Scale Values**: 3 scales (priority, complexity, satisfaction) with 5 values each
- **JSON Structures**: 8+ complex structures with nested categories

Total: **100+ controlled category values** across the entire schema.

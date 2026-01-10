"""
Healthcare Database Categories and Constraints Definition

This module defines all controlled categories (enum-like values) and validation rules
for the hospital AI platform database schema. These categories are STRICT constraints
and must be enforced during data generation and insertion.

All categories are designed to be:
- Realistic for Indian hospitals
- Non-diagnostic (high-level medical categories only)
- Finite and closed (NO free-text)
- Reusable across multiple tables
"""

from typing import Dict, List, Set, Optional
from datetime import date, datetime


# ============================================================================
# PATIENT DEMOGRAPHICS & MEDICAL DATA
# ============================================================================

GENDER_CATEGORIES: List[str] = [
    "male",
    "female",
    "other",
    "prefer_not_to_say"
]

BLOOD_GROUP_CATEGORIES: List[str] = [
    "A+",
    "A-",
    "B+",
    "B-",
    "AB+",
    "AB-",
    "O+",
    "O-"
]

EMERGENCY_CONTACT_RELATIONSHIP_CATEGORIES: List[str] = [
    "spouse",
    "parent",
    "child",
    "sibling",
    "relative",
    "friend",
    "guardian",
    "other"
]

CHRONIC_CONDITION_CATEGORIES: List[str] = [
    "hypertension",
    "diabetes",
    "asthma",
    "heart_disease",
    "arthritis",
    "thyroid",
    "kidney_disease",
    "liver_disease",
    "none"
]

ALLERGY_CATEGORIES: List[str] = [
    "medication",
    "food",
    "environmental",
    "latex",
    "none"
]

SURGERY_CATEGORIES: List[str] = [
    "cardiac",
    "orthopedic",
    "abdominal",
    "neurological",
    "ophthalmic",
    "dental",
    "none"
]

# Note: Medications are NOT controlled categories - they should be free-form strings
# This allows for any medication name (generic or brand) as prescribed by doctors
# Used in:
# - patients.medical_history.medications (current/ongoing medications)
# - patient_history.prescriptions (visit-specific prescriptions)


# ============================================================================
# SERVICE TYPES & SPECIALIZATIONS
# ============================================================================

SERVICE_TYPE_CATEGORIES: List[str] = [
    "general_consultation",
    "emergency",
    "cardiology",
    "orthopedics",
    "pediatrics",
    "gynecology",
    "dermatology",
    "ophthalmology",
    "ent",  # Ear, Nose, Throat
    "neurology",
    "psychiatry",
    "oncology",
    "urology",
    "gastroenterology",
    "pulmonology",
    "endocrinology",
    "radiology",
    "pathology",
    "anesthesiology"
]

# Mapping of service_type to valid specialization_area values
SERVICE_TYPE_TO_SPECIALIZATION: Dict[str, List[str]] = {
    "general_consultation": [
        "general_medicine",
        "family_medicine",
        "internal_medicine"
    ],
    "emergency": [
        "emergency_medicine",
        "trauma_care",
        "critical_care"
    ],
    "cardiology": [
        "cardiac_surgery",
        "interventional_cardiology",
        "cardiac_electrophysiology"
    ],
    "orthopedics": [
        "joint_replacement",
        "sports_medicine",
        "spine_surgery",
        "trauma_orthopedics"
    ],
    "pediatrics": [
        "pediatric_cardiology",
        "pediatric_oncology",
        "neonatology",
        "pediatric_surgery"
    ],
    "gynecology": [
        "obstetrics",
        "reproductive_medicine",
        "gynecological_oncology"
    ],
    "dermatology": [
        "cosmetic_dermatology",
        "dermatopathology",
        "pediatric_dermatology"
    ],
    "ophthalmology": [
        "retina",
        "cornea",
        "glaucoma",
        "pediatric_ophthalmology"
    ],
    "ent": [
        "otology",
        "rhinology",
        "laryngology",
        "head_neck_surgery"
    ],
    "neurology": [
        "stroke",
        "epilepsy",
        "movement_disorders",
        "neurocritical_care"
    ],
    "psychiatry": [
        "adult_psychiatry",
        "child_psychiatry",
        "addiction_psychiatry"
    ],
    "oncology": [
        "medical_oncology",
        "surgical_oncology",
        "radiation_oncology"
    ],
    "urology": [
        "urologic_oncology",
        "pediatric_urology",
        "reconstructive_urology"
    ],
    "gastroenterology": [
        "hepatology",
        "endoscopy",
        "inflammatory_bowel_disease"
    ],
    "pulmonology": [
        "critical_care_pulmonology",
        "sleep_medicine",
        "interventional_pulmonology"
    ],
    "endocrinology": [
        "diabetes",
        "thyroid_disorders",
        "reproductive_endocrinology"
    ],
    "radiology": [
        "diagnostic_radiology",
        "interventional_radiology",
        "nuclear_medicine"
    ],
    "pathology": [
        "clinical_pathology",
        "anatomic_pathology",
        "forensic_pathology"
    ],
    "anesthesiology": [
        "pain_management",
        "critical_care_anesthesia",
        "pediatric_anesthesia"
    ]
}

# Flattened list of all specialization areas
ALL_SPECIALIZATION_AREAS: List[str] = [
    spec for specs in SERVICE_TYPE_TO_SPECIALIZATION.values() for spec in specs
]


# ============================================================================
# TICKET & APPOINTMENT STATUS
# ============================================================================

TICKET_STATUS_CATEGORIES: List[str] = [
    "open",
    "assigned",
    "in_progress",
    "completed",
    "cancelled",
    "offered"
]

TICKET_ASSIGNMENT_STATUS_CATEGORIES: List[str] = [
    "unassigned",
    "offered",
    "accepted",
    "rejected_all"
]

TICKET_ASSIGNMENT_RECORD_STATUS_CATEGORIES: List[str] = [
    "pending",
    "accepted",
    "rejected",
    "expired"
]

APPOINTMENT_STATUS_CATEGORIES: List[str] = [
    "scheduled",
    "completed",
    "cancelled",
    "no_show"
]

CONVERSATION_STATUS_CATEGORIES: List[str] = [
    "active",
    "completed",
    "escalated"
]


# ============================================================================
# PRIORITY & COMPLEXITY SCALES
# ============================================================================

# Ticket Priority: 1-5 scale
PRIORITY_SCALE: Dict[int, str] = {
    1: "Critical/Emergency (life-threatening)",
    2: "High (urgent, needs immediate attention)",
    3: "Medium (moderate urgency)",
    4: "Low (routine)",
    5: "Very Low (non-urgent)"
}

PRIORITY_VALUES: List[int] = [1, 2, 3, 4, 5]

# Case Complexity: 1-5 scale
COMPLEXITY_SCALE: Dict[int, str] = {
    1: "Simple (routine checkup, minor issue)",
    2: "Low (standard consultation, common condition)",
    3: "Medium (requires investigation, moderate condition)",
    4: "High (complex diagnosis, multiple systems involved)",
    5: "Critical (life-threatening, multi-organ involvement)"
}

COMPLEXITY_VALUES: List[int] = [1, 2, 3, 4, 5]

# Patient Satisfaction Score: 1-5 scale
SATISFACTION_SCALE: Dict[int, str] = {
    1: "Very Dissatisfied",
    2: "Dissatisfied",
    3: "Neutral",
    4: "Satisfied",
    5: "Very Satisfied"
}

SATISFACTION_VALUES: List[int] = [1, 2, 3, 4, 5]


# ============================================================================
# DIAGNOSIS & MEDICAL CATEGORIES
# ============================================================================

DIAGNOSIS_CATEGORIES: List[str] = [
    "fever_infection",
    "respiratory_issue",
    "cardiovascular",
    "gastrointestinal",
    "neurological",
    "musculoskeletal",
    "dermatological",
    "endocrine_metabolic",
    "genitourinary",
    "ophthalmic",
    "ent_related",
    "mental_health",
    "trauma_injury",
    "preventive_care",
    "routine_checkup",
    "chronic_disease_management",
    "other"
]

TREATMENT_CATEGORIES: List[str] = [
    "medication_prescribed",
    "surgery_performed",
    "therapy_recommended",
    "lifestyle_modification",
    "observation_monitoring",
    "referral_made",
    "procedure_performed",
    "no_treatment_needed"
]


# ============================================================================
# OUTCOME & RESULTS
# ============================================================================

CASE_OUTCOME_CATEGORIES: List[str] = [
    "successful",
    "ongoing",
    "referred",
    "cancelled"
]

APPOINTMENT_TYPE_CATEGORIES: List[str] = [
    "consultation",
    "follow_up",
    "procedure"
]

TICKET_UPDATE_TYPE_CATEGORIES: List[str] = [
    "status_change",
    "assignment",
    "comment"
]

MESSAGE_SENDER_TYPE_CATEGORIES: List[str] = [
    "patient",
    "llm"
]

HISTORY_SUMMARY_GENERATED_BY_CATEGORIES: List[str] = [
    "llm",
    "doctor",
    "system"
]

ADMIN_ROLE_CATEGORIES: List[str] = [
    "admin",
    "super_admin"
]


# ============================================================================
# JSON FIELD STRUCTURES - SYMPTOMS
# ============================================================================

SYMPTOM_CATEGORIES: List[str] = [
    "fever",
    "cough",
    "headache",
    "chest_pain",
    "abdominal_pain",
    "nausea",
    "dizziness",
    "fatigue",
    "rash",
    "joint_pain",
    "shortness_of_breath",
    "bleeding",
    "other"
]

SYMPTOM_DURATION_CATEGORIES: List[str] = [
    "acute",      # < 1 week
    "subacute",   # 1-4 weeks
    "chronic"     # > 4 weeks
]

SYMPTOM_SEVERITY_CATEGORIES: List[str] = [
    "mild",
    "moderate",
    "severe"
]


# ============================================================================
# JSON FIELD STRUCTURES - PRESCRIPTIONS
# ============================================================================

PRESCRIPTION_FREQUENCY_CATEGORIES: List[str] = [
    "once_daily",
    "twice_daily",
    "thrice_daily",
    "four_times_daily",
    "as_needed",
    "weekly",
    "monthly"
]


# ============================================================================
# JSON FIELD STRUCTURES - TEST RESULTS
# ============================================================================

TEST_TYPE_CATEGORIES: List[str] = [
    "blood_test",
    "urine_test",
    "imaging",
    "ecg",
    "biopsy",
    "culture",
    "other"
]


# ============================================================================
# JSON FIELD STRUCTURES - VITAL SIGNS
# ============================================================================

# Temperature range: 95.0-105.0°F (35.0-40.5°C)
TEMPERATURE_MIN: float = 95.0
TEMPERATURE_MAX: float = 105.0

# Pulse range: 40-150 bpm
PULSE_MIN: int = 40
PULSE_MAX: int = 150

# Respiratory rate range: 10-30 per minute
RESPIRATORY_RATE_MIN: int = 10
RESPIRATORY_RATE_MAX: int = 30

# Blood pressure format: "XXX/YY mmHg"
# Systolic: 70-200, Diastolic: 40-120
BLOOD_PRESSURE_SYSTOLIC_MIN: int = 70
BLOOD_PRESSURE_SYSTOLIC_MAX: int = 200
BLOOD_PRESSURE_DIASTOLIC_MIN: int = 40
BLOOD_PRESSURE_DIASTOLIC_MAX: int = 120


# ============================================================================
# JSON FIELD STRUCTURES - DOCTOR QUALIFICATIONS
# ============================================================================

CERTIFICATION_CATEGORIES: List[str] = [
    "mbbs",
    "md",
    "ms",
    "dm",
    "mch",
    "dnb",
    "frcs",
    "usmle",
    "plab",
    "other"
]

CERTIFICATION_ISSUING_BODY_CATEGORIES: List[str] = [
    "mci",  # Medical Council of India
    "state_medical_council",
    "international_board",
    "university",
    "other"
]

EDUCATION_DEGREE_CATEGORIES: List[str] = [
    "mbbs",
    "md",
    "ms",
    "dm",
    "mch",
    "dnb",
    "bds",
    "bams",
    "bhms",
    "bpt",
    "other"
]

EDUCATION_COUNTRY_CATEGORIES: List[str] = [
    "india",
    "usa",
    "uk",
    "australia",
    "canada",
    "other"
]

LANGUAGE_CATEGORIES: List[str] = [
    "hindi",
    "english",
    "tamil",
    "telugu",
    "kannada",
    "malayalam",
    "marathi",
    "gujarati",
    "bengali",
    "punjabi",
    "urdu",
    "odia",
    "assamese",
    "other"
]


# ============================================================================
# VALIDATION CONSTRAINTS
# ============================================================================

# Patient age range
PATIENT_AGE_MIN: int = 0
PATIENT_AGE_MAX: int = 100

# Phone number pattern (India mobile): ^[6-9]\d{9}$
PHONE_NUMBER_PATTERN: str = r"^[6-9]\d{9}$"

# Doctor experience range
DOCTOR_EXPERIENCE_MIN: int = 0
DOCTOR_EXPERIENCE_MAX: int = 50
DOCTOR_MIN_AGE: int = 23  # After MBBS completion

# Workload constraints
WORKLOAD_MIN: int = 0
WORKLOAD_MAX: int = 50
MAX_WORKLOAD_DEFAULT: int = 10
MAX_DAILY_APPOINTMENTS_DEFAULT: int = 15


# ============================================================================
# CATEGORY CONTROL LEVELS
# ============================================================================

# Strict categories: Cannot be extended without code changes
# These are core to system functionality and business logic
STRICT_CATEGORIES: Dict[str, List[str]] = {
    "service_type": SERVICE_TYPE_CATEGORIES,
    "gender": GENDER_CATEGORIES,
    "blood_group": BLOOD_GROUP_CATEGORIES,
    "specialization_area": ALL_SPECIALIZATION_AREAS,
}

# Controlled categories: Can be extended via config/admin in future
# These are workflow states that need consistency but may need extension
# Note: New statuses can be added (e.g., "on_hold", "rescheduled") but must be
# added to this list and validated consistently across the codebase
CONTROLLED_CATEGORIES: Dict[str, List[str]] = {
    "ticket_status": TICKET_STATUS_CATEGORIES,
    "ticket_assignment_status": TICKET_ASSIGNMENT_STATUS_CATEGORIES,
    "ticket_assignment_record_status": TICKET_ASSIGNMENT_RECORD_STATUS_CATEGORIES,
    "appointment_status": APPOINTMENT_STATUS_CATEGORIES,
    "conversation_status": CONVERSATION_STATUS_CATEGORIES,
    "case_outcome": CASE_OUTCOME_CATEGORIES,
    "appointment_type": APPOINTMENT_TYPE_CATEGORIES,
    "ticket_update_type": TICKET_UPDATE_TYPE_CATEGORIES,
    "message_sender_type": MESSAGE_SENDER_TYPE_CATEGORIES,
    "history_summary_generated_by": HISTORY_SUMMARY_GENERATED_BY_CATEGORIES,
    "admin_role": ADMIN_ROLE_CATEGORIES,
}

# Flexible categories: Suggested values with "other" fallback
# These can accept custom values but have recommended categories
# Note: All flexible categories include "other" as a fallback option
FLEXIBLE_CATEGORIES: Dict[str, List[str]] = {
    "diagnosis_category": DIAGNOSIS_CATEGORIES,  # Has "other" as fallback
    "treatment_category": TREATMENT_CATEGORIES,
    "chronic_condition": CHRONIC_CONDITION_CATEGORIES,
    "allergy": ALLERGY_CATEGORIES,
    "surgery": SURGERY_CATEGORIES,
    "symptom": SYMPTOM_CATEGORIES,  # Has "other" as fallback
    "test_type": TEST_TYPE_CATEGORIES,  # Has "other" as fallback
}

# Supporting categories: Used in JSON structures and nested data
SUPPORTING_CATEGORIES: Dict[str, List[str]] = {
    "emergency_contact_relationship": EMERGENCY_CONTACT_RELATIONSHIP_CATEGORIES,
    "symptom_duration": SYMPTOM_DURATION_CATEGORIES,
    "symptom_severity": SYMPTOM_SEVERITY_CATEGORIES,
    "prescription_frequency": PRESCRIPTION_FREQUENCY_CATEGORIES,
    "certification": CERTIFICATION_CATEGORIES,
    "certification_issuing_body": CERTIFICATION_ISSUING_BODY_CATEGORIES,
    "education_degree": EDUCATION_DEGREE_CATEGORIES,
    "education_country": EDUCATION_COUNTRY_CATEGORIES,
    "language": LANGUAGE_CATEGORIES,
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_specializations_for_service_type(service_type: str) -> List[str]:
    """Get valid specialization areas for a given service type."""
    return SERVICE_TYPE_TO_SPECIALIZATION.get(service_type, [])


def is_valid_specialization_for_service_type(specialization: str, service_type: str) -> bool:
    """Check if a specialization is valid for a given service type."""
    return specialization in SERVICE_TYPE_TO_SPECIALIZATION.get(service_type, [])


def get_category_level(category_name: str) -> Optional[str]:
    """
    Get the control level for a category.
    
    Returns:
        "strict", "controlled", "flexible", "supporting", or None if not found
    """
    if category_name in STRICT_CATEGORIES:
        return "strict"
    elif category_name in CONTROLLED_CATEGORIES:
        return "controlled"
    elif category_name in FLEXIBLE_CATEGORIES:
        return "flexible"
    elif category_name in SUPPORTING_CATEGORIES:
        return "supporting"
    return None


def is_category_extensible(category_name: str) -> bool:
    """
    Check if a category can be extended without code changes.
    
    Returns:
        True if category is flexible or controlled (can be extended),
        False if strict (requires code changes)
    """
    level = get_category_level(category_name)
    return level in ["flexible", "controlled"]


def get_all_categories() -> Dict[str, List[str]]:
    """Get all category definitions as a dictionary."""
    all_cats = {}
    all_cats.update(STRICT_CATEGORIES)
    all_cats.update(CONTROLLED_CATEGORIES)
    all_cats.update(FLEXIBLE_CATEGORIES)
    all_cats.update(SUPPORTING_CATEGORIES)
    return all_cats


def get_categories_by_level(level: str) -> Dict[str, List[str]]:
    """
    Get all categories for a specific control level.
    
    Args:
        level: One of "strict", "controlled", "flexible", "supporting"
    
    Returns:
        Dictionary of category_name -> category_list
    """
    level_map = {
        "strict": STRICT_CATEGORIES,
        "controlled": CONTROLLED_CATEGORIES,
        "flexible": FLEXIBLE_CATEGORIES,
        "supporting": SUPPORTING_CATEGORIES,
    }
    return level_map.get(level, {})

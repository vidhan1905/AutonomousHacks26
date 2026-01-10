"""
Healthcare Database Validation Functions

This module provides validation functions that enforce all category constraints
and business rules for the hospital AI platform database schema.

All validation functions return (is_valid: bool, error_message: Optional[str])

Category Control Levels:
- STRICT: Cannot be extended without code changes (service_type, gender, blood_group)
- CONTROLLED: Can be extended via config/admin (status fields, workflow states)
- FLEXIBLE: Suggested values with "other" fallback (diagnosis, symptoms)
- SUPPORTING: Used in JSON structures (frequencies, durations, etc.)
"""

import re
from typing import Optional, Tuple, Dict, Any, List
from datetime import date, datetime, timedelta

from .categories import (
    # Categories
    GENDER_CATEGORIES,
    BLOOD_GROUP_CATEGORIES,
    EMERGENCY_CONTACT_RELATIONSHIP_CATEGORIES,
    SERVICE_TYPE_CATEGORIES,
    TICKET_STATUS_CATEGORIES,
    TICKET_ASSIGNMENT_STATUS_CATEGORIES,
    TICKET_ASSIGNMENT_RECORD_STATUS_CATEGORIES,
    APPOINTMENT_STATUS_CATEGORIES,
    CONVERSATION_STATUS_CATEGORIES,
    DIAGNOSIS_CATEGORIES,
    TREATMENT_CATEGORIES,
    CASE_OUTCOME_CATEGORIES,
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
    # Category levels
    STRICT_CATEGORIES,
    CONTROLLED_CATEGORIES,
    FLEXIBLE_CATEGORIES,
    get_category_level,
    is_category_extensible,
    # Constraints
    PATIENT_AGE_MIN,
    PATIENT_AGE_MAX,
    PHONE_NUMBER_PATTERN,
    DOCTOR_EXPERIENCE_MIN,
    DOCTOR_EXPERIENCE_MAX,
    DOCTOR_MIN_AGE,
    WORKLOAD_MIN,
    WORKLOAD_MAX,
    MAX_WORKLOAD_DEFAULT,
    MAX_DAILY_APPOINTMENTS_DEFAULT,
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
    PRIORITY_VALUES,
    COMPLEXITY_VALUES,
    SATISFACTION_VALUES,
    # Functions
    get_specializations_for_service_type,
    is_valid_specialization_for_service_type
)


# ============================================================================
# CATEGORY VALIDATION FUNCTIONS
# ============================================================================

def validate_category(value: Any, allowed_categories: List[str], field_name: str, allow_other: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Generic category validation function.
    
    Args:
        value: The value to validate
        allowed_categories: List of allowed category values
        field_name: Name of the field being validated (for error messages)
        allow_other: If True, allows "other" as a fallback value (for flexible categories)
    
    Returns:
        (is_valid: bool, error_message: Optional[str])
    """
    if value not in allowed_categories:
        if allow_other and value == "other":
            return True, None
        return False, f"{field_name} must be one of {allowed_categories}, got: {value}"
    return True, None


def validate_gender(gender: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate gender category."""
    if gender is None:
        return True, None  # Gender is nullable
    return validate_category(gender, GENDER_CATEGORIES, "gender")


def validate_blood_group(blood_group: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate blood group category."""
    if blood_group is None:
        return True, None  # Blood group is nullable
    return validate_category(blood_group, BLOOD_GROUP_CATEGORIES, "blood_group")


def validate_service_type(service_type: str) -> Tuple[bool, Optional[str]]:
    """
    Validate service type category (STRICT - core business logic).
    
    Note: This is a STRICT category - cannot be extended without code changes.
    Service types are core to matching doctors to patients/tickets.
    """
    return validate_category(service_type, SERVICE_TYPE_CATEGORIES, "service_type")


def validate_ticket_status(status: str) -> Tuple[bool, Optional[str]]:
    """
    Validate ticket status category (CONTROLLED - workflow state).
    
    Note: This is a CONTROLLED category - can be extended in future.
    Current values: open, assigned, in_progress, completed, cancelled, offered
    Future extensions: on_hold, rescheduled, etc. (must be added to categories.py)
    
    IMPORTANT: Ensure API routes use categories from categories.py, not hardcoded lists.
    See: backend/src/api/routes/tickets.py line 199 (needs update to include "offered")
    """
    return validate_category(status, TICKET_STATUS_CATEGORIES, "ticket_status")


def validate_ticket_assignment_status(status: str) -> Tuple[bool, Optional[str]]:
    """Validate ticket assignment status category."""
    return validate_category(status, TICKET_ASSIGNMENT_STATUS_CATEGORIES, "ticket_assignment_status")


def validate_ticket_assignment_record_status(status: str) -> Tuple[bool, Optional[str]]:
    """Validate ticket assignment record status category."""
    return validate_category(status, TICKET_ASSIGNMENT_RECORD_STATUS_CATEGORIES, "ticket_assignment_record_status")


def validate_appointment_status(status: str) -> Tuple[bool, Optional[str]]:
    """Validate appointment status category."""
    return validate_category(status, APPOINTMENT_STATUS_CATEGORIES, "appointment_status")


def validate_conversation_status(status: str) -> Tuple[bool, Optional[str]]:
    """Validate conversation status category."""
    return validate_category(status, CONVERSATION_STATUS_CATEGORIES, "conversation_status")


def validate_diagnosis_category(diagnosis: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate diagnosis category (FLEXIBLE - allows "other" as fallback).
    
    Note: This is a flexible category, so "other" is allowed as a fallback
    for cases that don't fit the standard categories.
    """
    if diagnosis is None:
        return True, None  # Diagnosis is nullable
    return validate_category(diagnosis, DIAGNOSIS_CATEGORIES, "diagnosis_category", allow_other=True)


def validate_treatment_category(treatment: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate treatment category."""
    if treatment is None:
        return True, None  # Treatment is nullable
    return validate_category(treatment, TREATMENT_CATEGORIES, "treatment_category")


def validate_case_outcome(outcome: str) -> Tuple[bool, Optional[str]]:
    """Validate case outcome category."""
    return validate_category(outcome, CASE_OUTCOME_CATEGORIES, "case_outcome")


def validate_appointment_type(appointment_type: str) -> Tuple[bool, Optional[str]]:
    """Validate appointment type category."""
    return validate_category(appointment_type, APPOINTMENT_TYPE_CATEGORIES, "appointment_type")


def validate_ticket_update_type(update_type: str) -> Tuple[bool, Optional[str]]:
    """Validate ticket update type category."""
    return validate_category(update_type, TICKET_UPDATE_TYPE_CATEGORIES, "ticket_update_type")


def validate_message_sender_type(sender_type: str) -> Tuple[bool, Optional[str]]:
    """Validate message sender type category."""
    return validate_category(sender_type, MESSAGE_SENDER_TYPE_CATEGORIES, "message_sender_type")


def validate_history_summary_generated_by(generated_by: str) -> Tuple[bool, Optional[str]]:
    """Validate history summary generated_by category."""
    return validate_category(generated_by, HISTORY_SUMMARY_GENERATED_BY_CATEGORIES, "history_summary_generated_by")


def validate_admin_role(role: str) -> Tuple[bool, Optional[str]]:
    """Validate admin role category."""
    return validate_category(role, ADMIN_ROLE_CATEGORIES, "admin_role")


# ============================================================================
# SCALE VALIDATION FUNCTIONS
# ============================================================================

def validate_priority(priority: int) -> Tuple[bool, Optional[str]]:
    """Validate ticket priority (1-5 scale)."""
    if not isinstance(priority, int):
        return False, f"priority must be an integer, got: {type(priority)}"
    if priority not in PRIORITY_VALUES:
        return False, f"priority must be between 1 and 5, got: {priority}"
    return True, None


def validate_complexity(complexity: int) -> Tuple[bool, Optional[str]]:
    """Validate case complexity (1-5 scale)."""
    if not isinstance(complexity, int):
        return False, f"complexity must be an integer, got: {type(complexity)}"
    if complexity not in COMPLEXITY_VALUES:
        return False, f"complexity must be between 1 and 5, got: {complexity}"
    return True, None


def validate_satisfaction_score(score: Optional[int]) -> Tuple[bool, Optional[str]]:
    """Validate patient satisfaction score (1-5 scale, nullable)."""
    if score is None:
        return True, None  # Satisfaction score is nullable
    if not isinstance(score, int):
        return False, f"satisfaction_score must be an integer or None, got: {type(score)}"
    if score not in SATISFACTION_VALUES:
        return False, f"satisfaction_score must be between 1 and 5, got: {score}"
    return True, None


# ============================================================================
# PATIENT VALIDATION FUNCTIONS
# ============================================================================

def validate_phone_number(phone: str) -> Tuple[bool, Optional[str]]:
    """Validate phone number (10 digits, India format)."""
    if not isinstance(phone, str):
        return False, f"phone_number must be a string, got: {type(phone)}"
    
    # Remove any whitespace
    phone = phone.strip()
    
    # Check pattern: ^[6-9]\d{9}$
    pattern = re.compile(PHONE_NUMBER_PATTERN)
    if not pattern.match(phone):
        return False, f"phone_number must be exactly 10 digits starting with 6-9, got: {phone}"
    
    return True, None


def validate_patient_age(age: int) -> Tuple[bool, Optional[str]]:
    """Validate patient age (0-100 years)."""
    if not isinstance(age, int):
        return False, f"age must be an integer, got: {type(age)}"
    if age < PATIENT_AGE_MIN or age > PATIENT_AGE_MAX:
        return False, f"age must be between {PATIENT_AGE_MIN} and {PATIENT_AGE_MAX}, got: {age}"
    return True, None


def validate_date_of_birth(dob: date, max_age: int = PATIENT_AGE_MAX) -> Tuple[bool, Optional[str]]:
    """Validate date of birth."""
    if not isinstance(dob, date):
        return False, f"date_of_birth must be a date object, got: {type(dob)}"
    
    today = date.today()
    
    # Must be in the past
    if dob >= today:
        return False, f"date_of_birth must be in the past, got: {dob}"
    
    # Must not be more than max_age years ago
    max_date = today - timedelta(days=max_age * 365)
    if dob < max_date:
        return False, f"date_of_birth must not be more than {max_age} years ago, got: {dob}"
    
    return True, None


def validate_age_date_of_birth_match(age: int, dob: date) -> Tuple[bool, Optional[str]]:
    """Validate that age matches date of birth."""
    today = date.today()
    calculated_age = (today - dob).days // 365
    
    if calculated_age != age:
        return False, f"age ({age}) does not match date_of_birth ({dob}), calculated age: {calculated_age}"
    
    return True, None


# ============================================================================
# DOCTOR VALIDATION FUNCTIONS
# ============================================================================

def validate_doctor_experience(years: int) -> Tuple[bool, Optional[str]]:
    """Validate doctor years of experience (0-50 years)."""
    if not isinstance(years, int):
        return False, f"years_of_experience must be an integer, got: {type(years)}"
    if years < DOCTOR_EXPERIENCE_MIN or years > DOCTOR_EXPERIENCE_MAX:
        return False, f"years_of_experience must be between {DOCTOR_EXPERIENCE_MIN} and {DOCTOR_EXPERIENCE_MAX}, got: {years}"
    return True, None


def validate_doctor_age_experience_match(age: int, years_of_experience: int) -> Tuple[bool, Optional[str]]:
    """Validate that doctor age and experience are logically consistent."""
    if years_of_experience > 0 and age < DOCTOR_MIN_AGE:
        return False, f"doctor must be at least {DOCTOR_MIN_AGE} years old if years_of_experience > 0, got age: {age}"
    
    max_experience = age - DOCTOR_MIN_AGE
    if years_of_experience > max_experience:
        return False, f"years_of_experience ({years_of_experience}) cannot exceed (age - {DOCTOR_MIN_AGE}), got age: {age}"
    
    return True, None


def validate_specialization_service_type_match(specialization: str, service_type: str) -> Tuple[bool, Optional[str]]:
    """Validate that specialization is valid for the service type."""
    if not is_valid_specialization_for_service_type(specialization, service_type):
        valid_specs = get_specializations_for_service_type(service_type)
        return False, f"specialization '{specialization}' is not valid for service_type '{service_type}'. Valid specializations: {valid_specs}"
    return True, None


# ============================================================================
# WORKLOAD VALIDATION FUNCTIONS
# ============================================================================

def validate_workload(current_workload: int, max_workload: int) -> Tuple[bool, Optional[str]]:
    """Validate workload constraints."""
    if not isinstance(current_workload, int) or not isinstance(max_workload, int):
        return False, "workload values must be integers"
    
    if current_workload < WORKLOAD_MIN:
        return False, f"current_workload must be >= {WORKLOAD_MIN}, got: {current_workload}"
    
    if max_workload < 1 or max_workload > WORKLOAD_MAX:
        return False, f"max_workload must be between 1 and {WORKLOAD_MAX}, got: {max_workload}"
    
    if current_workload > max_workload:
        return False, f"current_workload ({current_workload}) cannot exceed max_workload ({max_workload})"
    
    return True, None


def validate_daily_appointments(daily_count: int, max_daily: int) -> Tuple[bool, Optional[str]]:
    """Validate daily appointment count."""
    if not isinstance(daily_count, int) or not isinstance(max_daily, int):
        return False, "appointment count values must be integers"
    
    if daily_count < 0:
        return False, f"daily_count must be >= 0, got: {daily_count}"
    
    if max_daily < 1 or max_daily > WORKLOAD_MAX:
        return False, f"max_daily_appointments must be between 1 and {WORKLOAD_MAX}, got: {max_daily}"
    
    if daily_count > max_daily:
        return False, f"daily_count ({daily_count}) cannot exceed max_daily_appointments ({max_daily})"
    
    return True, None


# ============================================================================
# TICKET VALIDATION FUNCTIONS
# ============================================================================

def validate_emergency_priority(service_type: str, priority: int) -> Tuple[bool, Optional[str]]:
    """Validate that emergency tickets have appropriate priority."""
    if service_type == "emergency":
        if priority not in [1, 2]:
            return False, f"emergency tickets must have priority 1 or 2, got: {priority}"
    else:
        if priority == 1:
            return False, f"non-emergency tickets cannot have priority 1, got service_type: {service_type}, priority: {priority}"
    
    return True, None


def validate_emergency_complexity(service_type: str, complexity: int) -> Tuple[bool, Optional[str]]:
    """Validate that emergency cases have appropriate complexity."""
    if service_type == "emergency":
        if complexity not in [3, 4, 5]:
            return False, f"emergency cases must have complexity 3, 4, or 5, got: {complexity}"
    return True, None


def validate_ticket_assignment_rank(rank: int, ticket_id: str, existing_assignments: List[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    """Validate ticket assignment rank (must be unique per ticket, sequential)."""
    if not isinstance(rank, int):
        return False, f"rank must be an integer, got: {type(rank)}"
    
    if rank < 1:
        return False, f"rank must be >= 1, got: {rank}"
    
    # Check for duplicate ranks
    existing_ranks = [a.get("rank") for a in existing_assignments if a.get("ticket_id") == ticket_id]
    if rank in existing_ranks:
        return False, f"rank {rank} already exists for ticket {ticket_id}"
    
    # Check for gaps (ranks should be sequential starting from 1)
    if existing_ranks:
        max_rank = max(existing_ranks)
        if rank > max_rank + 1:
            return False, f"rank {rank} creates a gap. Expected next rank: {max_rank + 1}"
    
    return True, None


def validate_ticket_assignment_acceptance(ticket_id: str, assignment_status: str, assignments: List[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    """Validate that only one assignment per ticket can be accepted."""
    accepted_count = sum(1 for a in assignments if a.get("ticket_id") == ticket_id and a.get("status") == "accepted")
    
    if assignment_status == "accepted":
        if accepted_count > 0:
            return False, f"ticket {ticket_id} already has an accepted assignment"
    
    if ticket_id in [a.get("ticket_id") for a in assignments]:
        ticket_assignments = [a for a in assignments if a.get("ticket_id") == ticket_id]
        if assignment_status == "accepted" and any(a.get("status") == "accepted" for a in ticket_assignments if a.get("assignment_id") != assignments[-1].get("assignment_id")):
            return False, f"only one assignment per ticket can be accepted"
    
    return True, None


# ============================================================================
# VITAL SIGNS VALIDATION FUNCTIONS
# ============================================================================

def validate_temperature(temp: float) -> Tuple[bool, Optional[str]]:
    """Validate body temperature (95.0-105.0°F)."""
    if not isinstance(temp, (int, float)):
        return False, f"temperature must be a number, got: {type(temp)}"
    if temp < TEMPERATURE_MIN or temp > TEMPERATURE_MAX:
        return False, f"temperature must be between {TEMPERATURE_MIN} and {TEMPERATURE_MAX}°F, got: {temp}"
    return True, None


def validate_pulse(pulse: int) -> Tuple[bool, Optional[str]]:
    """Validate pulse rate (40-150 bpm)."""
    if not isinstance(pulse, int):
        return False, f"pulse must be an integer, got: {type(pulse)}"
    if pulse < PULSE_MIN or pulse > PULSE_MAX:
        return False, f"pulse must be between {PULSE_MIN} and {PULSE_MAX} bpm, got: {pulse}"
    return True, None


def validate_respiratory_rate(rate: int) -> Tuple[bool, Optional[str]]:
    """Validate respiratory rate (10-30 per minute)."""
    if not isinstance(rate, int):
        return False, f"respiratory_rate must be an integer, got: {type(rate)}"
    if rate < RESPIRATORY_RATE_MIN or rate > RESPIRATORY_RATE_MAX:
        return False, f"respiratory_rate must be between {RESPIRATORY_RATE_MIN} and {RESPIRATORY_RATE_MAX} per minute, got: {rate}"
    return True, None


def validate_blood_pressure(bp: str) -> Tuple[bool, Optional[str]]:
    """Validate blood pressure format (XXX/YY mmHg)."""
    if not isinstance(bp, str):
        return False, f"blood_pressure must be a string, got: {type(bp)}"
    
    # Parse format: "XXX/YY mmHg" or "XXX/YY"
    parts = bp.replace("mmHg", "").strip().split("/")
    if len(parts) != 2:
        return False, f"blood_pressure must be in format 'XXX/YY mmHg', got: {bp}"
    
    try:
        systolic = int(parts[0].strip())
        diastolic = int(parts[1].strip())
    except ValueError:
        return False, f"blood_pressure must contain numeric values, got: {bp}"
    
    if systolic < BLOOD_PRESSURE_SYSTOLIC_MIN or systolic > BLOOD_PRESSURE_SYSTOLIC_MAX:
        return False, f"systolic pressure must be between {BLOOD_PRESSURE_SYSTOLIC_MIN} and {BLOOD_PRESSURE_SYSTOLIC_MAX}, got: {systolic}"
    
    if diastolic < BLOOD_PRESSURE_DIASTOLIC_MIN or diastolic > BLOOD_PRESSURE_DIASTOLIC_MAX:
        return False, f"diastolic pressure must be between {BLOOD_PRESSURE_DIASTOLIC_MIN} and {BLOOD_PRESSURE_DIASTOLIC_MAX}, got: {diastolic}"
    
    if diastolic >= systolic:
        return False, f"diastolic pressure ({diastolic}) must be less than systolic pressure ({systolic})"
    
    return True, None


# ============================================================================
# JSON FIELD VALIDATION FUNCTIONS
# ============================================================================

def validate_emergency_contact(contact: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate emergency contact JSON structure."""
    if not isinstance(contact, dict):
        return False, "emergency_contact must be a dictionary"
    
    required_fields = ["name", "relationship", "phone"]
    for field in required_fields:
        if field not in contact:
            return False, f"emergency_contact missing required field: {field}"
    
    # Validate relationship
    is_valid, error = validate_category(contact["relationship"], EMERGENCY_CONTACT_RELATIONSHIP_CATEGORIES, "emergency_contact.relationship")
    if not is_valid:
        return False, error
    
    # Validate phone
    is_valid, error = validate_phone_number(contact["phone"])
    if not is_valid:
        return False, f"emergency_contact.phone: {error}"
    
    return True, None


def validate_symptoms_json(symptoms: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate current_symptoms JSON structure.
    
    Note: Symptoms is a FLEXIBLE category - allows "other" as fallback.
    """
    if not isinstance(symptoms, dict):
        return False, "current_symptoms must be a dictionary"
    
    if "symptoms" not in symptoms:
        return False, "current_symptoms missing required field: symptoms"
    
    if not isinstance(symptoms["symptoms"], list):
        return False, "current_symptoms.symptoms must be an array"
    
    # Validate each symptom (flexible - allows "other")
    for symptom in symptoms["symptoms"]:
        is_valid, error = validate_category(symptom, SYMPTOM_CATEGORIES, "symptom", allow_other=True)
        if not is_valid:
            return False, error
    
    # Validate duration if present
    if "duration" in symptoms:
        is_valid, error = validate_category(symptoms["duration"], SYMPTOM_DURATION_CATEGORIES, "symptom.duration")
        if not is_valid:
            return False, error
    
    # Validate severity if present
    if "severity" in symptoms:
        is_valid, error = validate_category(symptoms["severity"], SYMPTOM_SEVERITY_CATEGORIES, "symptom.severity")
        if not is_valid:
            return False, error
    
    return True, None


def validate_languages_array(languages: List[str]) -> Tuple[bool, Optional[str]]:
    """Validate languages_spoken JSON array."""
    if not isinstance(languages, list):
        return False, "languages_spoken must be an array"
    
    for lang in languages:
        is_valid, error = validate_category(lang, LANGUAGE_CATEGORIES, "language")
        if not is_valid:
            return False, error
    
    return True, None


# ============================================================================
# DATE & TIMESTAMP VALIDATION FUNCTIONS
# ============================================================================

def validate_date_order(earlier_date: date, later_date: date, field_names: Tuple[str, str]) -> Tuple[bool, Optional[str]]:
    """Validate that one date is before or equal to another."""
    if earlier_date > later_date:
        return False, f"{field_names[0]} ({earlier_date}) must be <= {field_names[1]} ({later_date})"
    return True, None


def validate_scheduled_date(scheduled_date: datetime) -> Tuple[bool, Optional[str]]:
    """Validate that scheduled_date is in the future."""
    now = datetime.now()
    if scheduled_date < now:
        return False, f"scheduled_date must be >= current time, got: {scheduled_date}"
    return True, None


def validate_expires_at(assigned_at: datetime, expires_at: Optional[datetime]) -> Tuple[bool, Optional[str]]:
    """Validate that expires_at is after assigned_at."""
    if expires_at is None:
        return True, None  # expires_at is nullable
    
    if expires_at <= assigned_at:
        return False, f"expires_at ({expires_at}) must be > assigned_at ({assigned_at})"
    return True, None

# Generated Healthcare Data

This directory contains realistic synthetic data for all database tables, generated according to the category constraints defined in `categories.py`.

## Generated Files

All data is stored as JSON files (one per table):

1. **patients.json** - 300 patient records
2. **admins.json** - 5 admin records
3. **service_persons.json** - 68 doctor/service person records
4. **doctor_expertise.json** - 102 expertise records
5. **conversations.json** - 400 conversation records
6. **messages.json** - 2,218 message records
7. **tickets.json** - 250 ticket records
8. **ticket_assignments.json** - 625 assignment records
9. **appointments.json** - 200 appointment records
10. **patient_history.json** - 600 history records
11. **doctor_case_history.json** - 400 case history records
12. **ticket_updates.json** - 376 update records
13. **patient_history_summaries.json** - 150 summary records

## Data Characteristics

### Compliance
- All category values follow strict constraints from `categories.py`
- All validation rules enforced (emergency priority, phone format, etc.)
- All relationships maintained (foreign keys reference existing records)

### Indian Context
- Indian names (using Faker with 'en_IN' locale)
- Indian addresses (cities, states)
- 10-digit phone numbers (starting with 6-9)
- Indian medical education and certifications

### Realistic Scenarios
- Mix of emergency and routine cases
- Patients with varying medical history (some extensive, some minimal)
- Doctors with different workload levels
- Realistic appointment scheduling
- Proper ticket assignment workflows

## Usage

To regenerate data:
```bash
uv run python scripts/generate_realistic_data.py
```

To use this data for database insertion, create a script that:
1. Reads each JSON file
2. Validates data using `validators.py`
3. Inserts into database using SQLAlchemy models

## Data Validation

All data has been generated following:
- Category constraints from `backend/src/data/categories.py`
- Validation rules from `backend/src/data/validators.py`
- Business logic rules (emergency priority, workload limits, etc.)

## Notes

- Phone numbers: All follow Indian format (10 digits, starts with 6-9)
- Dates: Realistic date ranges (past for history, future for appointments)
- Relationships: All foreign keys reference existing records
- Categories: All enum values from defined category lists
- Medications: Free-form (not controlled categories)

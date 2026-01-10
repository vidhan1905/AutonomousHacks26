# Database Insertion Script

## Overview

The `insert_generated_data.py` script inserts all generated JSON data into the PostgreSQL database. It is **idempotent** and can be run multiple times safely.

## Features

- ✅ **Idempotent**: Checks if records exist before inserting (skips duplicates)
- ✅ **Proper dependency order**: Inserts tables in correct order to maintain foreign key relationships
- ✅ **Data type conversion**: Automatically converts:
  - String UUIDs → UUID objects
  - ISO date strings → date objects
  - ISO datetime strings → datetime objects
  - JSON fields → Python dicts/lists
- ✅ **Error handling**: Comprehensive error handling with detailed tracebacks
- ✅ **Progress feedback**: Shows insertion progress for each table

## Usage

```bash
# Make sure database is initialized first
uv run python scripts/init_db.py

# Insert all generated data
uv run python scripts/insert_generated_data.py
```

## Prerequisites

1. **Database must exist**: Run `scripts/init_db.py` first to create database and tables
2. **JSON files must exist**: Ensure `backend/src/data/generated/` contains all 13 JSON files
3. **Environment variables**: Set `DATABASE_URL` in `.env` file or environment

## Insertion Order

The script inserts data in the following dependency order:

1. **patients** (base table)
2. **admins** (independent)
3. **service_persons** (base for doctors)
4. **doctor_expertise** (depends on service_persons)
5. **conversations** (depends on patients)
6. **messages** (depends on conversations)
7. **tickets** (depends on patients, conversations, service_persons)
8. **ticket_assignments** (depends on tickets, service_persons)
9. **appointments** (depends on patients, tickets, service_persons)
10. **patient_history** (depends on patients)
11. **doctor_case_history** (depends on service_persons, patients, tickets)
12. **ticket_updates** (depends on tickets)
13. **patient_history_summaries** (depends on patients, tickets)

## Data Validation

The script performs automatic data type conversion:
- **UUIDs**: Converts string UUIDs from JSON to UUID objects
- **Dates**: Parses ISO date strings ("YYYY-MM-DD") to date objects
- **Datetimes**: Parses ISO datetime strings with various formats
- **JSON fields**: Passes through dict/list structures as-is

## Idempotency

The script checks if each record already exists (by primary key) before inserting:
- **First run**: Inserts all records
- **Subsequent runs**: Skips existing records, only inserts new ones
- **Output**: Shows count of inserted vs skipped records

## Error Handling

If an error occurs:
- Full error message and traceback are displayed
- Database connection is properly closed
- Partial inserts are rolled back (each table commits independently)

## Output Example

```
======================================================================
Inserting Generated Data into Database
======================================================================
Database URL: localhost:5432/hospital_ai_assistant
Data directory: .../backend/src/data/generated

1. Inserting patients...
   ✓ Inserted: 300, Skipped: 0, Total: 300

2. Inserting admins...
   ✓ Inserted: 5, Skipped: 0, Total: 5

...

======================================================================
Data insertion completed successfully!
======================================================================
```

## Notes

- The script uses async SQLAlchemy for database operations
- Each table is committed independently (batch commits)
- Foreign key constraints are automatically validated by PostgreSQL
- If a foreign key reference is missing, PostgreSQL will raise an error

## Troubleshooting

**Error: "Data file not found"**
- Ensure JSON files exist in `backend/src/data/generated/`
- Run `scripts/generate_realistic_data.py` first to generate data

**Error: "relation does not exist"**
- Run `scripts/init_db.py` first to create database tables

**Error: "foreign key constraint violation"**
- This should not happen if insertion order is correct
- Check that all referenced records exist in parent tables

**Error: "duplicate key value"**
- The script should skip duplicates automatically
- If this occurs, there may be an issue with the idempotency check

# Schema Validation and Error Handling Improvements

## Overview
This document summarizes the improvements made to SQL query validation, error handling, and diagnostic logging to distinguish between legitimate "no results" scenarios and schema/query issues.

## Key Improvements

### 1. Doctor Query Schema Validation

#### Files Modified:
- `backend/src/agents/tools/doctor_tools.py`

#### Changes:
- Added schema validation before executing queries to catch missing columns/attributes early
- Enhanced error handling to distinguish between:
  - **Schema errors** (`status: "schema_error"`): Column/attribute doesn't exist
  - **Query errors** (`status: "error"`): Database connection or query execution issues
  - **No results** (`status: "success"` with empty list): Legitimate case where no doctors match criteria

#### Diagnostic Information:
When no doctors are found, the system now provides detailed diagnostics:
```python
{
    "status": "success",
    "doctors": [],
    "count": 0,
    "diagnostic": {
        "total_with_service_type": 10,
        "active_count": 8,
        "available_count": 5,
        "workload_ok_count": 0,
        "workload_details": [...],
        "reason": "All 5 available doctors have reached max workload"
    }
}
```

This helps identify:
- How many doctors exist for the service type
- How many are active
- How many are available
- How many have workload capacity
- Why no doctors were returned (specific filter that eliminated all results)

### 2. Patient History Query Schema Validation

#### Files Modified:
- `backend/src/agents/tools/patient_tools.py`

#### Changes:
- Added schema validation for both `Patient` and `PatientHistory` models
- Returns `status: "schema_error"` if model columns don't exist
- Returns `status: "partial_success"` if patient found but history query fails

### 3. Ticket Query Improvements

#### Files Modified:
- `backend/src/api/routes/tickets.py`

#### Changes:
- Added error handling with `AttributeError` catching for schema issues
- Updated ticket listing to check both `assigned_to` and `accepted_by` for service persons
- Added fallback handling for `assignment_status` column (backwards compatibility)
- Improved accept/reject logic to verify ticket is assigned/offered to the service person

### 4. Workflow Agent Error Handling

#### Files Modified:
- `backend/src/agents/workflow_agent.py`
- `backend/src/agents/conversation_agent.py`

#### Changes:
- Updated `find_doctors_node` to handle `schema_error` status separately from "no doctors found"
- Updated `inform_no_doctors_node` to provide different messages for schema errors vs legitimate "no doctors" cases
- Enhanced `fetch_history_node` to handle schema errors in patient history queries
- Fixed field name inconsistency: `patient_history.get("history")` → `patient_history.get("history_records")`

### 5. Service Types Query Validation

#### Files Modified:
- `backend/src/agents/tools/doctor_tools.py`

#### Changes:
- Added schema validation in `_get_available_service_types_async`
- Raises exceptions for schema errors (distinguished from empty results)
- Improved logging to identify schema issues vs no service types available

## How to Identify Schema Issues

### In Logs:
Look for these log patterns:
- `[SCHEMA ERROR]`: Indicates a schema/column issue
- `[QUERY RESULT]`: Normal query execution with result count
- `[DIAGNOSTIC]`: Detailed breakdown of why no results were found

### In API Responses:

#### Schema Error:
```json
{
    "status": "schema_error",
    "error": "ServicePerson model attribute may not exist. Check if columns (is_active, is_available, current_workload, max_workload) exist.",
    "diagnostic": "Schema validation failed - check ServicePerson model columns"
}
```

#### No Results (Legitimate):
```json
{
    "status": "success",
    "doctors": [],
    "count": 0,
    "diagnostic": {
        "reason": "All 5 available doctors have reached max workload",
        "total_with_service_type": 10,
        "active_count": 8,
        "available_count": 5,
        "workload_ok_count": 0
    }
}
```

## Field Name Consistency Fixes

### Fixed Issues:
1. **Patient History Field**: 
   - ❌ Wrong: `patient_history.get("history")`
   - ✅ Correct: `patient_history.get("history_records")`
   
   Fixed in:
   - `backend/src/agents/conversation_agent.py`
   - `backend/src/agents/tools/doctor_tools.py`

2. **Result Status Checking**:
   - Added explicit `status` field checks alongside `error` field checks
   - Handles both old format (`error` field) and new format (`status` field)

## Query Validation Summary

### Validated Queries:
1. ✅ `ServicePerson` queries (doctor availability)
2. ✅ `Patient` queries (patient lookup and history)
3. ✅ `PatientHistory` queries (medical history)
4. ✅ `Ticket` queries (ticket listing and updates)
5. ✅ Service type enumeration queries

### Schema Fields Verified:
- **ServicePerson**: `is_active`, `is_available`, `current_workload`, `max_workload`, `service_type`
- **Ticket**: `assignment_status`, `accepted_by`, `offered_to_count`, `status`, `assigned_to`
- **Patient**: `patient_id`, `name`, `phone_number`, `date_of_birth`, `gender`, `blood_group`, `emergency_contact`
- **PatientHistory**: `visit_date`, `service_type`, `diagnosis`, `treatment`, `prescriptions`

## Best Practices Implemented

1. **Early Schema Validation**: Test queries with minimal data before full query execution
2. **Detailed Diagnostics**: Provide breakdown of filter stages when no results found
3. **Clear Error Messages**: Distinguish schema errors from data issues
4. **Backwards Compatibility**: Fallback handling for missing optional fields
5. **Comprehensive Logging**: Log schema errors with full stack traces for debugging

## Testing Recommendations

To verify schema alignment:
1. Check logs for `[SCHEMA ERROR]` messages when queries fail
2. Verify diagnostic information provides actionable insights
3. Test with empty database (should show "no results" not "schema error")
4. Test with missing columns (should show "schema error" with specific column names)
5. Monitor `[QUERY RESULT]` logs to understand filter effectiveness

## Migration Notes

If you encounter schema errors:
1. Check the `diagnostic` field in the error response
2. Verify the mentioned columns exist in `backend/src/database/models.py`
3. Run database migrations if schema was updated
4. Check that SQLAlchemy model definitions match actual database schema

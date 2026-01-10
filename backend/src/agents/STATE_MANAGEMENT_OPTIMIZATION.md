# State Management Optimization

## Overview

The state management has been optimized to use:
1. **PostgresSaver Checkpointer**: Direct state persistence in PostgreSQL
2. **Pydantic Models**: Type-safe state validation
3. **HITL (Human In The Loop)**: Validation before SQL execution
4. **Field Validation**: Questions asked before proceeding

## Key Changes

### 1. Pydantic Models for State (`state_models.py`)

Instead of plain TypedDict, we now use Pydantic models for validation:

```python
from backend.src.agents.state_models import (
    PatientInfo,
    AppointmentPreferences,
    HITLState,
    AgentState  # TypedDict compatible with LangGraph
)
```

**Benefits:**
- Type validation at runtime
- Automatic serialization/deserialization
- Clear field documentation
- Built-in validation methods

### 2. PostgresSaver Checkpointer (`checkpointer.py`)

State is now persisted directly to PostgreSQL using LangGraph's PostgresSaver:

```python
from backend.src.agents.checkpointer import get_checkpointer

# In your route handler:
checkpointer = await get_checkpointer()
config = {"configurable": {"thread_id": conversation_id}}
final_state = await graph.ainvoke(initial_state, config=config)
```

**Benefits:**
- Automatic state persistence
- Thread-based state management
- No manual state reconstruction needed
- Built-in checkpointing for recovery

### 3. HITL Validation (`validation.py`)

Before any SQL execution, fields are validated and questions asked if missing:

```python
from backend.src.agents.validation import validate_before_sql_execution

# Before tool call:
can_proceed, question_msg = validate_before_sql_execution(state, "verify_patient")
if not can_proceed:
    # Ask user for missing information
    state.messages.append(question_msg)
    return state  # Wait for user input
```

**Benefits:**
- No incomplete data in database
- Better user experience
- Clear error messages
- Prevents invalid SQL queries

### 4. Updated Workflow

The workflow now:
1. Validates required fields before SQL execution
2. Asks questions if fields are missing
3. Waits for user input (HITL flag)
4. Proceeds only when all validations pass

## Migration Steps

### Step 1: Install Dependencies

```bash
uv pip install langgraph-checkpoint-postgres
```

### Step 2: Setup Checkpointer Tables

Run the setup script:

```python
from backend.src.agents.checkpointer import setup_checkpointer_tables
await setup_checkpointer_tables()
```

Or manually create tables using Alembic migration.

### Step 3: Update Conversation Routes

Replace old state management:

```python
# OLD WAY:
initial_state: AgentState = {
    "conversation_id": conversation_id,
    "patient_verified": False,
    # ... manual state construction
}
final_state = await graph.ainvoke(initial_state, config={"recursion_limit": 100})

# NEW WAY:
from backend.src.agents.state_models import create_initial_state
from backend.src.agents.checkpointer import get_checkpointer

checkpointer = await get_checkpointer()
initial_state = create_initial_state(conversation_id, patient_id)
config = {
    "configurable": {"thread_id": conversation_id},
    "recursion_limit": 100
}
final_state = await graph.ainvoke(initial_state, config=config)
```

### Step 4: Update Graph Creation

Use checkpointer in graph compilation:

```python
from backend.src.agents.conversation_agent_optimized import get_graph

graph = await get_graph()  # Automatically uses checkpointer
```

## State Structure

### Old Structure (TypedDict only)
```python
AgentState = TypedDict({
    "patient_verified": bool,
    "collected_info": dict,  # No validation
    # ...
})
```

### New Structure (Pydantic + TypedDict)
```python
# TypedDict for LangGraph compatibility
AgentState = TypedDict({
    "patient_verified": bool,
    "patient_info": dict,  # Validated PatientInfo model
    "hitl": dict,  # HITLState with validation flags
    # ...
})

# Pydantic models for validation
class PatientInfo(BaseModel):
    name: Optional[str]
    phone: Optional[str]
    date_of_birth: Optional[str]
    def is_complete(self) -> bool: ...
```

## HITL Workflow

```
User Message
    ↓
Validate Required Fields
    ↓
[Missing Fields?]
    ├─ YES → Set HITL flag → Ask Questions → Wait for Input
    └─ NO → Proceed with SQL Execution
```

## Example Usage

```python
# Check if validation is needed
if state.requires_user_input():
    # State is waiting for user response
    return state  # Don't proceed

# Validate before SQL
can_proceed, question = validate_before_verification(state)
if not can_proceed:
    state.hitl.is_waiting_for_input = True
    state.messages.append(question)
    return state

# All validations pass - proceed
result = await verify_patient(...)
```

## Benefits Summary

1. **Type Safety**: Pydantic models catch errors at runtime
2. **State Persistence**: Automatic checkpointing with PostgresSaver
3. **Better UX**: Questions asked before errors occur
4. **Validation**: No invalid data in database
5. **Maintainability**: Clear structure and documentation

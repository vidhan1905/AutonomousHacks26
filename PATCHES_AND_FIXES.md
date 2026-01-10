# Patches and Fixes Applied to Hospital AI Assistant System

This document catalogs all patches, workarounds, and fixes applied during development.

---

## 1. Async Event Loop Conflict Patch

**Issue**: `asyncio.run()` creates a new event loop, which conflicts when called from FastAPI's async context, causing errors when LangGraph tools try to access the database.

**Location**: 
- `backend/src/agents/tools/patient_tools.py`
- `backend/src/agents/tools/ticket_tools.py`
- `backend/src/agents/tools/appointment_tools.py`
- `backend/src/agents/tools/doctor_tools.py`

**Patch Applied**: Created `run_async_safely()` helper function that:
- Runs async functions in a separate thread with its own event loop
- Uses `ThreadPoolExecutor` to avoid event loop conflicts
- Creates a fresh `async_session_maker` for each new event loop via `create_async_session_maker()`
- Wraps all async tool functions with this pattern

**Code Pattern**:
```python
def run_async_safely(async_func, *args, session_maker_param=False, **kwargs):
    """Run an async function safely from a sync context using a thread pool."""
    def run_in_thread():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            from backend.src.database.connection import create_async_session_maker
            if session_maker_param:
                fresh_session_maker = create_async_session_maker()
                kwargs['session_maker'] = fresh_session_maker
            return new_loop.run_until_complete(async_func(*args, **kwargs))
        finally:
            new_loop.close()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        return future.result(timeout=10)  # or 30 for LLM calls
```

**Files Modified**:
- All tool files now use this pattern instead of direct async calls

---

## 2. SQLAlchemy Refresh Error Fix

**Issue**: After committing a conversation, the object becomes detached from the session, causing `refresh()` to fail with `InvalidRequestError`.

**Location**: `backend/src/api/routes/conversations.py` (line 58-63)

**Patch Applied**: 
- Removed the `refresh()` call after commit
- Instead, query the conversation again to get fresh data from database
- This ensures we get the `started_at` timestamp without refresh errors

**Before**:
```python
await db.commit()
db.refresh(conversation)  # This fails!
```

**After**:
```python
await db.commit()
# Query the conversation again to get the started_at timestamp
# (refresh can fail if object is detached after commit)
result = await db.execute(
    select(Conversation).where(Conversation.conversation_id == uuid.UUID(conversation_id))
)
conversation = result.scalar_one()
```

---

## 3. Metadata Column Name Conflict Fix

**Issue**: `metadata` is a reserved word in SQLAlchemy, causing conflicts when used as a column name.

**Location**: `backend/src/database/models.py` (Message model, line 93)

**Patch Applied**: Renamed `metadata` column to `message_metadata` to avoid SQLAlchemy conflicts.

**Before**:
```python
metadata = Column(JSON, nullable=True)
```

**After**:
```python
message_metadata = Column(JSON, nullable=True)  # Renamed from metadata to avoid SQLAlchemy conflict
```

---

## 4. Recursion Limit Increase Patch

**Issue**: LangGraph agent was hitting recursion limit of 25, causing "Recursion limit reached without hitting a stop condition" errors during complex conversations.

**Location**: 
- `backend/src/api/routes/conversations.py` (line 223)
- `backend/src/agents/conversation_agent.py` (line 173-175, 196)

**Patch Applied**:
1. Increased recursion limit from 25 to 100 when invoking the graph
2. Added loop detection in `should_continue()` to count consecutive tool messages
3. If more than 3 tool messages in a row, force termination to prevent infinite loops

**Code**:
```python
# In send_message endpoint
config = {"recursion_limit": 100}  # Increased to handle complex flows
final_state = await graph.ainvoke(initial_state, config=config)

# In should_continue function
# Count tool messages to prevent infinite loops
tool_message_count = sum(1 for msg in reversed(messages[-5:]) if isinstance(msg, ToolMessage))
if tool_message_count > 3:  # Reduced threshold for faster termination
    return "end"
```

---

## 5. Patient Verification State Persistence Fix

**Issue**: Conversation state wasn't persisting between messages. Each message started fresh, so the LLM didn't know the patient was already verified.

**Location**: `backend/src/api/routes/conversations.py` (lines 136-175)

**Patch Applied**: 
- Load previous messages from database to build full conversation history
- Check if verification was completed by examining LLM responses
- Only mark patient as verified if verification happened in the conversation (not just from login)
- Preserve `collected_info` from verified patient records

**Logic**:
```python
# Check if verification has been completed in this conversation
verification_completed = False
if not is_first_message:
    llm_messages = [msg for msg in previous_messages if msg.sender_type == "llm"]
    
    if len(llm_messages) > 0:
        last_llm_msg = llm_messages[-1]
        content_lower = last_llm_msg.content.lower()
        
        # Check if it asks for verification details
        asks_for_verification = any(phrase in content_lower for phrase in [
            "your name", "your phone", "your date of birth", ...
        ])
        
        # If last LLM message doesn't ask for verification, assume it's completed
        if not asks_for_verification:
            verification_completed = True
```

---

## 6. Tool Call Blocking Until Verification Fix

**Issue**: LLM was making database queries (`verify_patient`, `create_patient`, etc.) before collecting required information.

**Location**: `backend/src/agents/conversation_agent.py` (lines 78-127)

**Patch Applied**: 
- Updated `should_continue()` to block tool calls until all verification details are collected
- Only allow `extract_patient_info` on first step
- Block `verify_patient` and `create_patient` until name, phone, and DOB are collected
- Block other tools (like `get_patient_history`, `create_ticket`) until patient is verified

**Logic**:
```python
if not patient_verified:
    has_name = bool(collected_info.get("name"))
    has_phone = bool(collected_info.get("phone"))
    has_dob = bool(collected_info.get("date_of_birth"))
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        tool_names = [tc.get("name") for tc in last_message.tool_calls]
        
        # ALWAYS allow extract_patient_info - it's the first step
        if "extract_patient_info" in tool_names:
            return "tools"  # Allow extraction
        
        # Allow verify_patient or create_patient if we have all info
        if "verify_patient" in tool_names or "create_patient" in tool_names:
            if has_name and has_phone and has_dob:
                return "tools"  # Allow verification
            else:
                return "end"  # Block tool call - we don't have all info yet
        else:
            # Other tools should NOT be called until patient is verified
            return "end"  # Block these tools
```

---

## 7. First Message Verification Prompt Fix

**Issue**: On first message, LLM was giving generic greetings instead of asking for verification details.

**Location**: `backend/src/agents/conversation_agent.py` (lines 814-844)

**Patch Applied**: 
- Check if this is the first message (only patient messages, no previous LLM responses)
- If first message, force LLM to immediately ask for verification details
- Explicit system prompt instructs LLM to ask for name, phone, and DOB before doing anything else

**System Prompt**:
```python
if is_first_message:
    system_prompt = """You are a helpful AI assistant for a hospital call center.

CRITICAL FIRST STEP - YOU MUST DO THIS NOW:
When a patient first contacts you, your FIRST response MUST be to ask for their verification details. Do NOT greet them or ask how you can help until AFTER they provide their information.

Your FIRST message should be:
"Hello! I'm your AI assistant here to help you. To verify your identity and access your medical records, I'll need a few details. Could you please provide me with your:
1. Full name
2. Phone number  
3. Date of birth (in YYYY-MM-DD format, e.g., 1955-02-28)

DO NOT:
- Ask "How can I help you?" or "What can I do for you?" until AFTER verification
- Make any tool calls (verify_patient, create_patient, etc.) until the user provides their information
- Skip asking for verification details
"""
```

---

## 8. Empty LLM Response Fallback Fix

**Issue**: After tool calls, the LLM sometimes returned empty responses, causing blank messages in the chat.

**Location**: `backend/src/api/routes/conversations.py` (lines 226-269)

**Patch Applied**:
- Improved response extraction to find the last AIMessage with actual content
- Skip tool-call-only messages that don't have content
- Added fallback responses based on which tool was called
- Ensure a response is always returned

**Code**:
```python
# Get LLM response - find the last AIMessage with actual content
llm_messages = [msg for msg in final_state["messages"] if isinstance(msg, AIMessage)]
llm_response = None

# Look backwards for the last message with content
for msg in reversed(llm_messages):
    content = getattr(msg, 'content', None) or ""
    if content and str(content).strip():
        has_tool_calls = hasattr(msg, 'tool_calls') and msg.tool_calls
        if not has_tool_calls:
            llm_response = str(content)
            break

# Fallback if no content found
if not llm_response:
    tool_names = [tc.get("name", "") for tc in last_msg.tool_calls if isinstance(tc, dict)]
    if "verify_patient" in tool_names:
        llm_response = "I've verified your identity. How can I assist you today?"
    elif "create_patient" in tool_names:
        llm_response = "I've created your patient record. How can I assist you today?"
    # ... more fallbacks
```

---

## 9. Patient Verification Matching Strategies Fix

**Issue**: Patient verification was failing even when patients existed in the database due to strict matching.

**Location**: `backend/src/agents/tools/patient_tools.py` (lines 68-142)

**Patch Applied**: Implemented multiple matching strategies:
1. **Strategy 1**: Match by phone number first (most reliable, phone is unique)
2. **Strategy 2**: Match by name and DOB if phone format differs
3. **Strategy 3**: Flexible matching with all three fields using ILIKE

**Code**:
```python
# Strategy 1: Try exact match on phone (most reliable, phone is unique)
result = await session.execute(
    select(Patient).where(Patient.phone_number == normalized_phone)
)
patient = result.scalar_one_or_none()

if patient:
    # Verify name and DOB match (with flexible name matching)
    name_matches = (
        patient.name.lower() == normalized_name.lower() or
        normalized_name.lower() in patient.name.lower() or
        patient.name.lower() in normalized_name.lower()
    )
    dob_matches = patient.date_of_birth == dob
    
    if name_matches and dob_matches:
        return {"found": True, "patient_id": str(patient.patient_id), ...}

# Strategy 2: Try matching by name and DOB (in case phone format differs)
# Strategy 3: Try all three together with flexible matching
```

---

## 10. Bcrypt Dependency Removal Patch

**Issue**: Bcrypt was causing version detection issues during synthetic data generation.

**Location**: `scripts/generate_dataset.py` (lines 35-37)

**Patch Applied**: Replaced bcrypt with simple SHA256 hash for synthetic data generation (testing only, not for production).

**Before**:
```python
import bcrypt
def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
```

**After**:
```python
import hashlib
def get_password_hash(password: str) -> str:
    """Simple hash for synthetic data generation (not for production use)."""
    return hashlib.sha256(f"salt_{password}".encode()).hexdigest()
```

**Note**: This is only for synthetic data generation. Production authentication still uses proper password hashing in `auth_service.py`.

---

## 11. Import Path Fix

**Issue**: Extraction tools were importing from `langchain.tools` which may not be available.

**Location**: `backend/src/agents/tools/extraction_tools.py`

**Patch Applied**: Changed import to use `langchain_core.tools` which is the correct package.

**Before**:
```python
from langchain.tools import tool
```

**After**:
```python
from langchain_core.tools import tool
```

---

## 12. Database Creation Script Fix

**Issue**: Database initialization script needed to handle database creation if it doesn't exist.

**Location**: `scripts/init_db.py`

**Patch Applied**: Created script to:
- Parse DATABASE_URL from .env file
- Connect to PostgreSQL using default `postgres` database
- Check if target database exists
- Create database if it doesn't exist
- Test connection to verify it works

**Key Logic**:
```python
# Connect to postgres database to create target database
conn = await asyncpg.connect(
    database='postgres',  # Connect to default database
    user=user,
    password=password,
    host=host,
    port=port
)

# Check if database exists
exists = await conn.fetchval(
    "SELECT 1 FROM pg_database WHERE datname = $1", db_name
)

if not exists:
    # Create database (note: CREATE DATABASE cannot be run in a transaction)
    await conn.execute(f'CREATE DATABASE "{db_name}"')
```

---

## 13. Tool Result Processing Enhancement

**Issue**: Tool results weren't properly updating state, causing issues with patient verification, ticket creation, and doctor ranking.

**Location**: `backend/src/agents/conversation_agent.py` (lines 227-495)

**Patch Applied**: Enhanced `process_tool_results()` to:
- Extract patient info from `verify_patient` and `extract_patient_info` tool results
- Mark patient as verified when verification succeeds
- Detect ticket creation and set `ticket_created = True`
- Process doctor ranking results and store ranked doctors
- Handle error states from tool calls (doctors not found, ranking failed, ticket creation failed)

**Key Features**:
- Multiple passes through messages to extract different types of tool results
- Error state tracking (doctors_found, ranking_success, tickets_creation_success)
- Proper state updates for all workflow steps

---

## 14. Doctor Recommendation Workflow Error Handling

**Issue**: Doctor recommendation workflow had no error handling, causing failures when doctors weren't found or ranking failed.

**Location**: `backend/src/agents/conversation_agent.py` (lines 598-679)

**Patch Applied**: Added comprehensive error handling:
- Check for `doctors_found = False` and inform user politely
- Check for `ranking_success = False` and provide fallback message
- Check for `tickets_creation_success = False` and inform user
- Each error case has a specific system prompt to handle gracefully

**Error Handling Logic**:
```python
# Handle error case: No doctors found
if doctors_found is False:
    system_prompt = f"""...ERROR: No doctors were found for the requested service type.
    
You must inform the patient politely that:
- No doctors are currently available for their requested service type
- They may need to try a different service type or check back later
- You apologize for the inconvenience

Be empathetic and helpful. END after informing the patient.
"""
```

---

## 15. Conversation History Loading Fix

**Issue**: Conversation history wasn't being loaded properly, causing the LLM to lose context between messages.

**Location**: `backend/src/api/routes/conversations.py` (lines 121-185)

**Patch Applied**:
- Load all previous messages from database
- Build full conversation history for the agent
- Convert database messages to LangChain message types (HumanMessage, AIMessage)
- Preserve conversation context across messages

**Code**:
```python
# Load previous messages to maintain conversation context
messages_result = await db.execute(
    select(Message)
    .where(Message.conversation_id == uuid.UUID(conversation_id))
    .order_by(Message.created_at)
)
previous_messages = messages_result.scalars().all()

# Build message history for the agent
message_history = []
for msg in previous_messages:
    if msg.sender_type == "patient":
        message_history.append(HumanMessage(content=msg.content))
    elif msg.sender_type == "llm":
        message_history.append(AIMessage(content=msg.content))

# Add current message
message_history.append(HumanMessage(content=request.content))
```

---

## 16. Service Type Routing Fix

**Issue**: LLM wasn't correctly determining service types from patient requests.

**Location**: `backend/src/agents/conversation_agent.py` (lines 705-720)

**Patch Applied**: Added explicit service type determination logic in system prompt:
- Map keywords to service types (e.g., "broken leg" → "orthopedics")
- Handle emergency cases
- Default to "general_consultation" if unclear

**Service Type Mapping**:
```python
STEP 1: Determine service_type from the request:
   - "broken leg/hand/arm", "fracture", "bone", "orthopedic" → "orthopedics"
   - "heart", "chest pain", "cardiac" → "cardiology"
   - "headache", "neurological", "brain" → "neurology"
   - "blood test", "lab work" → "blood_test"
   - "emergency", "urgent" → "emergency"
   # ... more mappings
```

---

## 17. Date Parsing Enhancement

**Issue**: Natural language dates like "next week" and "tomorrow" weren't being parsed correctly.

**Location**: `backend/src/agents/tools/appointment_tools.py` (lines 94-102)

**Patch Applied**: Added date parsing for common natural language expressions:
- "next week" → 7 days from now
- "tomorrow" → next day
- "today" → current date

**Code**:
```python
# Handle various date formats
if "next week" in preferred_date.lower() or "next week" in (notes or "").lower():
    # Calculate next week's date (7 days from now, same time)
    next_week = datetime.now() + timedelta(days=7)
    preferred_date = next_week.strftime("%Y-%m-%dT10:00:00")
elif "tomorrow" in preferred_date.lower():
    tomorrow = datetime.now() + timedelta(days=1)
    preferred_date = tomorrow.strftime("%Y-%m-%dT10:00:00")
elif "today" in preferred_date.lower():
    preferred_date = datetime.now().strftime("%Y-%m-%dT10:00:00")
```

---

## 18. Fresh Database Connection for Each Event Loop

**Issue**: Database connections were tied to the original event loop, causing errors when running in a new thread.

**Location**: `backend/src/database/connection.py` (lines 17-20)

**Patch Applied**: Created `create_async_session_maker()` function that creates a fresh async session maker for each new event loop.

**Code**:
```python
def create_async_session_maker():
    """Create a fresh async session maker for a new event loop."""
    fresh_engine = create_async_engine(DATABASE_URL, echo=True)
    return async_sessionmaker(fresh_engine, class_=AsyncSession, expire_on_commit=False)
```

This function is called inside `run_async_safely()` to create fresh connections for each new event loop.

---

## Summary of Patches by Category

### Async/Concurrency Issues
1. Async event loop conflict patch (ThreadPoolExecutor workaround)
2. Fresh database connection for each event loop

### Database Issues
3. SQLAlchemy refresh error fix
4. Metadata column name conflict fix
5. Database creation script fix

### LangGraph/Agent Issues
6. Recursion limit increase patch
7. Tool call blocking until verification fix
8. First message verification prompt fix
9. Empty LLM response fallback fix
10. Tool result processing enhancement
11. Conversation history loading fix
12. Service type routing fix

### Patient Verification Issues
13. Patient verification state persistence fix
14. Patient verification matching strategies fix

### Data Generation Issues
15. Bcrypt dependency removal patch

### Import/Code Issues
16. Import path fix

### Workflow Issues
17. Doctor recommendation workflow error handling
18. Date parsing enhancement

---

## Technical Debt and Known Issues

1. **ThreadPoolExecutor Workaround**: The `run_async_safely()` pattern is a workaround for async/sync incompatibility. A better solution would be to make the entire LangGraph flow async-native.

2. **Recursion Limit**: The recursion limit of 100 is high. Consider optimizing the workflow to reduce tool call chains.

3. **Password Hashing**: Synthetic data generation uses SHA256 instead of bcrypt. This is acceptable for testing but should be noted.

4. **Error Handling**: Some error cases may not be fully handled. Consider adding more comprehensive error recovery.

5. **State Management**: The state management is complex with many flags. Consider refactoring to a cleaner state machine pattern.

6. **Response Fallbacks**: Fallback responses are hardcoded. Consider making them more dynamic or LLM-generated.

---

## Recommendations for Future Improvements

1. **Refactor to Full Async**: Make LangGraph tools fully async-compatible to remove the ThreadPoolExecutor workaround.

2. **State Machine Pattern**: Refactor the agent state management to use a proper state machine pattern for clarity.

3. **Better Error Recovery**: Add retry logic and better error recovery mechanisms.

4. **Optimize Tool Chains**: Reduce the number of tool calls in a single conversation turn to lower recursion limit.

5. **Configuration Management**: Move hardcoded values (recursion limit, timeouts, retry counts) to configuration.

6. **Comprehensive Logging**: Add structured logging throughout the agent flow for better debugging.

7. **Testing**: Add unit tests for all patches to prevent regressions.

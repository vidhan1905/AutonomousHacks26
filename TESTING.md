# Testing Guide for Hospital AI Assistant System

This guide provides step-by-step instructions and example inputs to test all features of the Hospital AI Assistant system.

## Quick Reference

### Test Patient Credentials
- **Phone**: `001-852-326-5094x079`
- **Name**: April Maldonado  
- **DOB**: 1955-02-28

### Quick Test Messages

**Initial Verification:**
```
My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28
```

**Schedule Appointment:**
```
I'd like to schedule an appointment for next week for my follow-up.
```

**Request Service:**
```
I need a blood test done. I've been feeling tired lately.
```

**Emergency:**
```
I'm having severe abdominal pain. I need emergency care.
```

## Prerequisites

1. **Database Setup**: Ensure PostgreSQL is running and the database is initialized
   ```bash
   # Initialize database
   uv run python scripts/init_db.py
   
   # Run migrations
   uv run alembic upgrade head
   
   # Generate synthetic data
   uv run python scripts/generate_dataset.py
   ```

2. **Backend Server**: Start the FastAPI backend
   ```bash
   uv run uvicorn backend.src.main:app --reload --port 8000
   ```

3. **Frontend Server**: Start the React frontend (in a separate terminal)
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Environment Variables**: Ensure `.env` file is configured with:
   - `DATABASE_URL`
   - `OPENAI_API_KEY`
   - `JWT_SECRET_KEY`

## Test Accounts

### Patient Login
- **Phone**: `001-852-326-5094x079`
- **Name**: April Maldonado
- **DOB**: 1955-02-28

### Service Person Login
- **Username**: `blood_test_1` (or any service type)
- **Password**: `password123`

### Admin Login
- **Username**: `admin_1`
- **Password**: `admin123`

## Testing Scenarios

### Scenario 1: New Patient Registration and Verification

**Step 1: Login as Patient**
- Go to login page
- Select "Patient" user type
- Enter phone: `001-852-326-5094x079`
- Click Login

**Step 2: Start Conversation**
- Click "New Conversation" or select an existing conversation
- Send initial message: `Hi`

**Expected Response**: 
- LLM greets you and asks for your information

**Step 3: Provide Patient Information**
- Send: `My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28`

**Expected Response**:
- Patient is verified
- Medical history is retrieved and displayed
- Summary of past visits shown
- LLM asks how it can help

---

### Scenario 2: Schedule an Appointment

**Prerequisites**: Patient must be verified (complete Scenario 1 first)

**Input**: 
```
I'd like to schedule an appointment for next week for my follow-up.
```

**Expected Behavior**:
- LLM recognizes you're already verified
- Uses `schedule_appointment` tool
- Schedules appointment for next week
- Confirms appointment details

**Alternative Inputs**:
- `Can I book an appointment with a doctor?`
- `I want to schedule a consultation for tomorrow`
- `Book me an appointment for next Monday`

---

### Scenario 3: Request a Service (Create Ticket)

**Prerequisites**: Patient must be verified

**Input**: 
```
I need a blood test done. I've been feeling tired lately.
```

**Expected Behavior**:
- LLM understands you need a service (not an appointment)
- Uses `create_ticket` tool with:
  - Service type: `blood_test`
  - Patient details (blood group, history)
  - Current symptoms
  - LLM-generated summary
- Ticket is created and visible in dashboard

**Alternative Inputs**:
- `I need a lab test to check my cholesterol`
- `Can you help me get an imaging scan? I've been having headaches`
- `I want to see a cardiologist about my chest pain`

---

### Scenario 4: Emergency Service Request

**Input**:
```
I'm having severe abdominal pain. I think I need emergency care.
```

**Expected Behavior**:
- Creates ticket with `service_type: emergency`
- High priority assigned
- Comprehensive patient information included
- Ticket appears in emergency service person dashboard

---

### Scenario 5: Multiple Services

**Input**:
```
I need both a blood test and an imaging scan. I've been having headaches and dizziness.
```

**Expected Behavior**:
- LLM may create multiple tickets or ask for clarification
- Each service gets its own ticket
- Symptoms are recorded

---

### Scenario 6: Specific Department Consultation

**Input**:
```
I need to see a neurologist about my migraines.
```

**Expected Behavior**:
- Creates ticket with `service_type: neurology`
- May also schedule appointment
- Patient history relevant to neurology is included

---

### Scenario 7: Follow-up on Previous Visit

**Input**:
```
I want to follow up on my previous emergency visit from November. The pain has returned.
```

**Expected Behavior**:
- LLM references your past history
- Creates appropriate ticket or appointment
- Links to previous visit information

---

### Scenario 8: General Health Concern

**Input**:
```
I've been experiencing dizziness and fatigue for the past few days. What should I do?
```

**Expected Behavior**:
- LLM discusses symptoms
- May create ticket for appropriate service
- Provides helpful guidance
- Schedules appointment if needed

---

## Testing Service Person Dashboard

### Login as Service Person

1. **Login**:
   - Select "Service Person" user type
   - Username: `blood_test_1` (or any service type)
   - Password: `password123`

2. **View Tickets**:
   - Dashboard shows all open tickets
   - Filter by service type
   - See patient details, history, and LLM summary

3. **Test Ticket Actions**:
   - Assign ticket to yourself
   - Update ticket status (in_progress, completed)
   - Add comments/updates

**Example Ticket Details You Should See**:
- Patient name, phone, blood group
- Past history summary
- LLM-generated summary
- Current symptoms
- Service type

---

## Testing Admin Dashboard

### Login as Admin

1. **Login**:
   - Select "Admin" user type
   - Username: `admin_1`
   - Password: `admin123`

2. **View All Tickets**:
   - See all tickets across all services
   - Filter and manage tickets
   - Assign tickets to service persons

---

## Expected Tool Calls

When testing, check the backend logs to see which tools the LLM calls:

### For Appointment Scheduling:
```
schedule_appointment(
    patient_id="...",
    service_type="general_consultation",
    preferred_date="2025-01-17T10:00:00",
    notes="Follow-up appointment"
)
```

### For Service Requests:
```
create_ticket(
    patient_id="...",
    conversation_id="...",
    service_type="blood_test",
    description="Patient needs blood test",
    priority=2,
    patient_details={...},
    past_history_summary="...",
    llm_summary="...",
    current_symptoms={...}
)
```

---

## Common Test Messages

### Verification Messages:
- `My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28`
- `I'm April Maldonado, phone 001-852-326-5094x079, born 1955-02-28`

### Appointment Requests:
- `I'd like to schedule an appointment for next week`
- `Can I book a consultation?`
- `I want to see a doctor tomorrow`
- `Schedule me for a follow-up next Monday`

### Service Requests:
- `I need a blood test`
- `Can you help me get a lab test?`
- `I want an imaging scan`
- `I need to see a cardiologist`

### Emergency:
- `I'm having severe pain, I need emergency care`
- `This is an emergency, I need help now`

### General Questions:
- `What services are available?`
- `Tell me about my past visits`
- `What's my medical history?`

---

## Troubleshooting

### Issue: LLM asks for verification again
**Solution**: Check that conversation state is being preserved. Ensure previous messages are loaded.

### Issue: Wrong tool called (appointment vs ticket)
**Solution**: Check system prompt - it should distinguish between "schedule/appointment" (use schedule_appointment) vs "need/test/service" (use create_ticket).

### Issue: Date parsing fails
**Solution**: Check appointment tool - it should handle "next week", "tomorrow", etc.

### Issue: Patient not found
**Solution**: 
- Verify patient exists in database
- Check phone number format matches exactly
- Verify date format is YYYY-MM-DD

### Issue: Async errors
**Solution**: Ensure all tools use `run_async_safely` helper function.

---

## Verification Checklist

After testing, verify:

- [ ] Patient can login with phone number
- [ ] Patient verification works correctly
- [ ] Medical history is retrieved and displayed
- [ ] Appointments can be scheduled
- [ ] Tickets are created for services
- [ ] Service persons can see tickets
- [ ] Tickets include comprehensive patient information
- [ ] LLM doesn't ask for verification after first verification
- [ ] Conversation history is maintained across messages
- [ ] Different service types work correctly

---

## Example Complete Flow

1. **Login**: Patient ? Phone: `001-852-326-5094x079`
2. **Start Chat**: Click "New Conversation"
3. **Greet**: Send `Hi`
4. **Provide Info**: Send `My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28`
5. **Verify**: Should see medical history summary
6. **Request Service**: Send `I need a blood test done`
7. **Check Dashboard**: Ticket should appear in patient dashboard
8. **Login as Service Person**: Username `blood_test_1`, Password `password123`
9. **View Ticket**: Should see ticket with all patient details
10. **Update Status**: Change status to "in_progress" or "completed"

---

## Notes

- The LLM extracts information from natural language - be flexible with phrasing
- Dates can be in various formats: "1955-02-28", "02/28/1955", "next week", "tomorrow"
- Phone numbers should match database format exactly
- Patient verification happens once per conversation
- Each conversation maintains its own state

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

**Doctor Recommendation (NEW):**
```
My leg is broken, I need urgent help
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
- Medical history is retrieved and displayed in chat
- Summary of past visits shown (last 10 records)
- LLM asks: "What help do you need today?"

---

### Scenario 2: Doctor Recommendation System (NEW FEATURE)

**Prerequisites**: Patient must be verified (complete Scenario 1 first)

**Step 1: After Verification and History Display**
- After providing patient info, you should see your medical history displayed
- LLM asks: "What help do you need today?"

**Step 2: Request Help with a Medical Issue**
**Input**: 
```
My leg is broken, I need urgent help
```

**Expected Behavior**:
1. **Service Type Determination**:
   - LLM determines service type: `orthopedics` (from "broken leg")
   - Other examples:
     - "chest pain" → `cardiology`
     - "headache" → `neurology`
     - "blood test" → `blood_test`
     - "emergency" → `emergency`

2. **Doctor Query**:
   - System queries `get_service_persons_by_type(service_type="orthopedics")`
   - Returns list of available doctors for that service type

3. **Doctor Ranking**:
   - LLM ranks top 5 doctors using `rank_doctors_with_llm`
   - Ranking considers:
     - Patient's medical history
     - Current symptoms/request
     - Doctor specialization match
   - Each doctor gets a rank (1-5) and reasoning

4. **Ticket Creation**:
   - System creates tickets for ALL 5 ranked doctors using `create_multiple_tickets`
   - Each ticket includes:
     - Patient details (blood group, etc.)
     - Past history summary
     - LLM-generated summary
     - Ranking reason for that doctor
   - Tickets are assigned to respective doctors

5. **Frontend Display**:
   - Doctor recommendation cards appear in chat
   - Each card shows:
     - Doctor name
     - Rank badge (1-5, with labels like "Best Match", "Excellent")
     - Specialization
     - Ranking reason
     - Ticket ID
   - Cards displayed in responsive grid layout

**Alternative Test Inputs**:
```
I'm having chest pain and need to see a cardiologist
```
- Expected: `cardiology` service type, cardiology doctors ranked

```
I need help with my mental health, I've been feeling depressed
```
- Expected: `mental_health` service type, mental health specialists ranked

```
I have a skin rash that won't go away
```
- Expected: `dermatology` service type, dermatologists ranked

```
I need urgent surgery consultation
```
- Expected: `surgery_consultation` service type, surgeons ranked

**Verification Steps**:
1. Check backend logs for tool calls:
   - `get_service_persons_by_type`
   - `rank_doctors_with_llm`
   - `create_multiple_tickets`

2. Check database:
   - 5 tickets should be created
   - Each ticket assigned to different doctor
   - All tickets have same `service_type`
   - Tickets include patient details and history

3. Check frontend:
   - Doctor cards display correctly
   - Rank badges show proper colors
   - Ticket IDs are visible
   - Cards are responsive (test on mobile)

4. Check Service Person Dashboard:
   - Login as a doctor from the ranked list
   - Should see ticket assigned to them
   - Ticket includes ranking reason and patient history

---

### Scenario 3: Schedule an Appointment

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

### Scenario 4: Request a Service (Create Ticket)

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

### Scenario 5: Emergency Service Request

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

### Scenario 6: Multiple Services

**Input**:
```
I need both a blood test and an imaging scan. I've been having headaches and dizziness.
```

**Expected Behavior**:
- LLM may create multiple tickets or ask for clarification
- Each service gets its own ticket
- Symptoms are recorded

---

### Scenario 7: Specific Department Consultation

**Input**:
```
I need to see a neurologist about my migraines.
```

**Expected Behavior**:
- Creates ticket with `service_type: neurology`
- May also schedule appointment
- Patient history relevant to neurology is included

---

### Scenario 8: Follow-up on Previous Visit

**Input**:
```
I want to follow up on my previous emergency visit from November. The pain has returned.
```

**Expected Behavior**:
- LLM references your past history
- Creates appropriate ticket or appointment
- Links to previous visit information

---

### Scenario 9: General Health Concern

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

### For Doctor Recommendation Flow:
```
# Step 1: Get patient history (after verification)
get_patient_history(patient_id="...")

# Step 2: Determine service type and query doctors
get_service_persons_by_type(service_type="orthopedics")

# Step 3: Rank doctors using LLM
rank_doctors_with_llm(
    patient_history={...},
    user_request="My leg is broken, I need urgent help",
    doctors=[{doctor_id, name, service_type, specialization}, ...],
    service_type="orthopedics"
)

# Step 4: Create tickets for all 5 ranked doctors
create_multiple_tickets(
    patient_id="...",
    conversation_id="...",
    ranked_doctors=[{doctor_id, name, rank, reason}, ...],
    service_type="orthopedics",
    description="My leg is broken, I need urgent help",
    patient_details={...},
    past_history_summary="...",
    llm_summary="...",
    priority=5
)
```

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

### Doctor Recommendation Requests:
- `My leg is broken, I need urgent help` → orthopedics
- `I'm having chest pain` → cardiology
- `I have severe headaches` → neurology
- `I need mental health support` → mental_health
- `I have a skin condition` → dermatology
- `I need surgery consultation` → surgery_consultation

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

### Basic Functionality:
- [ ] Patient can login with phone number
- [ ] Patient verification works correctly
- [ ] Medical history is retrieved and displayed in chat after verification
- [ ] LLM asks "What help do you need today?" after showing history
- [ ] Appointments can be scheduled
- [ ] Tickets are created for services
- [ ] Service persons can see tickets
- [ ] Tickets include comprehensive patient information
- [ ] LLM doesn't ask for verification after first verification
- [ ] Conversation history is maintained across messages
- [ ] Different service types work correctly

### Doctor Recommendation System (NEW):
- [ ] Patient history is displayed in chat after verification
- [ ] Service type is correctly determined from user request
- [ ] Doctors are queried by service type
- [ ] Top 5 doctors are ranked with LLM
- [ ] Ranking includes clear reasoning for each doctor
- [ ] Tickets are created for all 5 ranked doctors
- [ ] Each ticket is assigned to the respective doctor
- [ ] Doctor recommendation cards display in frontend
- [ ] Cards show rank badges, names, specializations, and reasons
- [ ] Ticket IDs are visible on doctor cards
- [ ] Cards are responsive (test on mobile/tablet)
- [ ] Service persons can see their assigned tickets in dashboard
- [ ] Tickets include ranking reason and patient history summary

---

## Example Complete Flow

### Basic Flow:
1. **Login**: Patient ? Phone: `001-852-326-5094x079`
2. **Start Chat**: Click "New Conversation"
3. **Greet**: Send `Hi`
4. **Provide Info**: Send `My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28`
5. **Verify**: Should see medical history displayed in chat
6. **Request Service**: Send `I need a blood test done`
7. **Check Dashboard**: Ticket should appear in patient dashboard
8. **Login as Service Person**: Username `blood_test_1`, Password `password123`
9. **View Ticket**: Should see ticket with all patient details
10. **Update Status**: Change status to "in_progress" or "completed"

### Doctor Recommendation Flow (NEW):
1. **Login**: Patient ? Phone: `001-852-326-5094x079`
2. **Start Chat**: Click "New Conversation"
3. **Provide Info**: Send `My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28`
4. **Verify & History**: 
   - Patient verified
   - Medical history displayed in chat
   - LLM asks: "What help do you need today?"
5. **Request Help**: Send `My leg is broken, I need urgent help`
6. **Doctor Recommendation**:
   - Service type determined: `orthopedics`
   - Top 5 doctors ranked and displayed as cards
   - 5 tickets created (one for each doctor)
7. **View Doctor Cards**: 
   - Cards show rank, name, specialization, reason, ticket ID
   - Cards are clickable/viewable
8. **Check Tickets**: 
   - Login as one of the ranked doctors
   - Should see ticket assigned to them
   - Ticket includes ranking reason and patient history
9. **Verify All Tickets**: 
   - Check patient dashboard - should see 5 tickets
   - Each ticket assigned to different doctor
   - All tickets have same service_type: `orthopedics`

---

## Notes

- The LLM extracts information from natural language - be flexible with phrasing
- Dates can be in various formats: "1955-02-28", "02/28/1955", "next week", "tomorrow"
- Phone numbers should match database format exactly
- Patient verification happens once per conversation
- Each conversation maintains its own state

### Doctor Recommendation System Notes:
- **Service Type Mapping**: The LLM maps user requests to service types:
  - "broken leg", "fracture" → `orthopedics`
  - "chest pain", "heart" → `cardiology`
  - "headache", "neurological" → `neurology`
  - "blood test", "lab work" → `blood_test`
  - "emergency", "urgent" → `emergency`
  - "mental health", "depression" → `mental_health`
  - "skin", "rash" → `dermatology`
  - "surgery" → `surgery_consultation`
  - Default: `general_consultation`

- **Ranking Criteria**: Doctors are ranked based on:
  - Specialization match with patient history
  - Service type alignment
  - Patient's current symptoms/needs
  - Relevance to medical condition

- **Ticket Creation**: All 5 ranked doctors get tickets automatically
  - Each ticket includes the ranking reason
  - Tickets are pre-assigned to doctors
  - Patient can see all tickets in their dashboard

- **Frontend Display**: Doctor cards are only shown for doctor recommendation messages
  - Regular text messages still use standard message bubbles
  - Cards are responsive and work on mobile devices
  - Rank badges use color coding (1=Best Match, 2=Excellent, etc.)

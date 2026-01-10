# Testing Sequential Multi-Doctor Case Review Feature

This guide explains how to test the new sequential multi-doctor case review feature.

## Prerequisites

1. Database is running (PostgreSQL)
2. Backend dependencies installed
3. Frontend dependencies installed (optional, for full UI testing)

## Step 1: Run Database Migration

First, apply the new migration to create the sequential review tables:

```bash
cd "/Users/vidhan/Vidhan/GDG FINAL/AutonomousHacks26"
alembic upgrade head
```

This will create:
- `sequential_review_chains` table
- `sequential_review_steps` table
- Add `sequential_review_chain_id` and `is_sequential_review` columns to `tickets` table

## Step 2: Ensure Test Data Exists

Make sure you have doctors in multiple service types for testing:

```bash
# Check if you have doctors in different specialties
# You should have doctors with service_types like:
# - cardiology
# - endocrinology
# - neurology
# - pulmonology
# - anesthesiology
# - rheumatology
# - immunology
```

If you need to generate test data, run:

```bash
python scripts/insert_generated_data.py
```

## Step 3: Start the Backend

```bash
cd backend
uvicorn src.main:app --reload --port 8000
```

Or if using Docker:

```bash
docker-compose up backend
```

## Step 4: Test Complex Case Detection

### Test Case 1: Complex Multi-Symptom Case

**Expected**: System detects this as complex and routes to multiple doctors.

1. **Login as a patient** (or create one if needed):
   ```bash
   POST /api/auth/patient/login
   {
     "phoneNumber": "1234567890",
     "password": "your_password"
   }
   ```

2. **Start a conversation**:
   ```bash
   POST /api/conversations
   ```

3. **Send a complex case query**:
   ```
   "I've been experiencing chest pain for the past week, and I also have diabetes. 
   Recently I've been having some numbness in my left arm. I'm worried this might be 
   something serious."
   ```

   **Expected Behavior**:
   - System detects this as a complex case
   - Identifies multiple service types needed: cardiology, endocrinology, neurology
   - Creates a sequential review chain
   - Routes to first doctor (cardiologist)

### Test Case 2: Pre-Surgical Clearance

**Query**:
```
"I need clearance for knee surgery. I have a history of heart problems and 
asthma. My doctor said I need multiple specialists to approve."
```

**Expected**: Routes to Cardiologist → Pulmonologist → Anesthesiologist

### Test Case 3: Normal Case (Single Service Type)

**Query**:
```
"I have a cold and need to see a doctor."
```

**Expected**: Routes to normal flow (single service type, multiple doctors of same type)

## Step 5: Test Sequential Review Flow

### 5.1 Check Chain Creation

After sending a complex case query, check if a chain was created:

```bash
GET /api/sequential-reviews/patient/{patient_id}
```

You should see a chain with status "pending" or "in_progress".

### 5.2 Check Chain Details

```bash
GET /api/sequential-reviews/{chain_id}
```

This will show:
- Chain status
- Current step index
- All review steps with doctor assignments
- Review summaries (if any steps are completed)

### 5.3 Test Doctor Review Submission

1. **Login as the first doctor** (from the chain):
   ```bash
   POST /api/auth/service-person/login
   {
     "email": "doctor1@example.com",
     "password": "password"
   }
   ```

2. **View tickets** (should see the sequential review ticket):
   ```bash
   GET /api/tickets
   ```

3. **Get ticket details**:
   ```bash
   GET /api/tickets/{ticket_id}
   ```

   You should see:
   - `is_sequential_review: true`
   - `sequential_review_chain_id: <chain_id>`
   - Description includes accumulated context (empty for first doctor)

4. **Get sequential context**:
   ```bash
   GET /api/sequential-reviews/tickets/{ticket_id}/sequential-context
   ```

5. **Submit review** (update ticket status with comment):
   ```bash
   PUT /api/tickets/{ticket_id}/status
   {
     "status": "completed",
     "comment": "Patient shows signs of cardiac involvement. Recommended ECG and stress test. 
                 Blood pressure is elevated. Advise cardiology follow-up."
   }
   ```

   **Expected Behavior**:
   - Ticket status updates to "completed"
   - Review notes are extracted
   - Chain advances to next step
   - Next doctor's ticket is created/updated
   - Ticket `assigned_to` updates to next doctor

### 5.4 Test Next Doctor Review

1. **Login as the second doctor**:
   ```bash
   POST /api/auth/service-person/login
   {
     "email": "doctor2@example.com",
     "password": "password"
   }
   ```

2. **View tickets** - Should see the same ticket (now assigned to them)

3. **Get ticket details** - Description should include first doctor's review

4. **Get accumulated context**:
   ```bash
   GET /api/sequential-reviews/tickets/{ticket_id}/sequential-context
   ```

   Should show:
   - Previous doctor's review summary
   - Previous doctor's notes
   - Formatted context

5. **Submit review**:
   ```bash
   PUT /api/tickets/{ticket_id}/status
   {
     "status": "completed",
     "comment": "Diabetes is well-controlled. Blood sugar levels are stable. 
                 No immediate concerns. Continue current medication."
   }
   ```

### 5.5 Test Final Step

Repeat for the last doctor. After the last doctor submits:

- Chain status should be "completed"
- Final summary should be generated
- Patient should receive notification

## Step 6: Test API Endpoints

### 6.1 Get Chain Status

```bash
GET /api/sequential-reviews/{chain_id}
```

**Response includes**:
- Chain metadata (complexity score, reason, status)
- All steps with doctor info and review summaries
- Current step index

### 6.2 Get Accumulated Context

```bash
GET /api/sequential-reviews/{chain_id}/context
```

**Response**: Formatted text with all previous doctors' reviews

### 6.3 Get Patient's Chains

```bash
GET /api/sequential-reviews/patient/{patient_id}
```

**Response**: List of all chains for the patient

### 6.4 Get Ticket Sequential Context

```bash
GET /api/sequential-reviews/tickets/{ticket_id}/sequential-context
```

**Response**: Context for the specific ticket's step

## Step 7: Test Ticket Visibility

### Test: All Doctors See the Ticket

1. Login as Doctor 1 (first in chain)
2. Check tickets - should see ticket assigned to them
3. Login as Doctor 2 (second in chain)
4. Check tickets - should ALSO see the same ticket (even though not yet assigned)
5. Login as Doctor 3 (third in chain)
6. Check tickets - should ALSO see the same ticket

**Expected**: All doctors in the chain can see the ticket, but only the current assigned doctor can submit review.

## Step 8: Test Error Cases

### 8.1 Test Normal Case Routing

Send a simple query that should NOT trigger sequential review:

```
"I have a headache and need to see a doctor."
```

**Expected**: Routes to normal flow (single service type, multiple doctors)

### 8.2 Test Invalid Doctor Assignment

Try to submit review as wrong doctor:

1. Login as Doctor 2
2. Try to submit review when Doctor 1 is still assigned
3. **Expected**: Should fail or be prevented

### 8.3 Test Missing Service Types

If LLM suggests service types that don't exist in database:
- System should fall back to normal case
- Or show appropriate error

## Step 9: Frontend Testing (Optional)

If frontend is updated, test:

1. **Patient Dashboard**:
   - Send complex case query
   - See confirmation that sequential review was initiated

2. **Doctor Dashboard**:
   - See sequential review tickets
   - See "Sequential Review - Step X of Y" badge
   - See previous doctors' reviews
   - Submit review with notes

3. **Ticket Detail Page**:
   - Sequential review section
   - Timeline of reviews
   - Accumulated context display
   - Review form (only for current doctor)

## Step 10: Verify Database State

Check database directly:

```sql
-- Check chains
SELECT * FROM sequential_review_chains;

-- Check steps
SELECT s.*, sp.name as doctor_name, sp.service_type 
FROM sequential_review_steps s
JOIN service_persons sp ON s.doctor_id = sp.service_person_id
ORDER BY s.chain_id, s.step_index;

-- Check tickets linked to chains
SELECT t.ticket_id, t.assigned_to, t.is_sequential_review, 
       t.sequential_review_chain_id, s.step_index, s.status
FROM tickets t
LEFT JOIN sequential_review_steps s ON t.ticket_id = s.ticket_id
WHERE t.is_sequential_review = true;
```

## Troubleshooting

### Issue: Migration fails

**Solution**: Check if previous migrations are applied:
```bash
alembic current
alembic upgrade head
```

### Issue: No doctors found for service types

**Solution**: Ensure doctors exist in required specialties:
```bash
# Check existing doctors
SELECT DISTINCT service_type FROM service_persons WHERE is_active = true;
```

### Issue: Complex case not detected

**Solution**: 
- Check LLM API key is set
- Check logs for detection results
- Verify query contains multiple symptoms/conditions

### Issue: Workflow not advancing

**Solution**:
- Check ticket status update includes `comment` field
- Verify doctor_id matches current step assignment
- Check workflow logs for errors

### Issue: Ticket not visible to all doctors

**Solution**:
- Verify `sequential_review_chain_id` is set on ticket
- Check ticket query includes chain filter
- Verify doctors are in SequentialReviewStep records

## Expected Test Results

After completing all tests, you should have:

1. ✅ Complex cases detected correctly
2. ✅ Sequential chains created with proper doctor ordering
3. ✅ Tickets created and linked to steps
4. ✅ Doctors can see tickets in their dashboard
5. ✅ Reviews submitted and chain advances
6. ✅ Accumulated context passed to next doctor
7. ✅ Final summary generated when all doctors review
8. ✅ Normal cases still route correctly (single service type)

## Next Steps

After testing:
1. Generate test data for complex cases (update `scripts/insert_generated_data.py`)
2. Update frontend UI for sequential review display
3. Add monitoring/logging for production
4. Document API endpoints for frontend team

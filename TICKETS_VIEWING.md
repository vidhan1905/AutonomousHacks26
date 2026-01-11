# How to View Tickets

## API Endpoints

### 1. **List All Tickets** (Role-based filtering)
```
GET /api/tickets
```

**Response (filtered by user role):**
- **Patients**: See only their own tickets
- **Service Persons (Doctors)**: See only tickets assigned to them (excluding cancelled)
- **Admins**: See all tickets

**Query Parameters:**
- `status` (optional): Filter by status (`open`, `assigned`, `in_progress`, `completed`, `cancelled`)
- `service_type` (optional): Filter by service type (e.g., `orthopedics`, `cardiology`)
- `priority` (optional): Filter by priority level

**Example Response:**
```json
[
  {
    "ticket_id": "uuid",
    "conversation_id": "uuid",
    "patient_id": "uuid",
    "service_type": "lab test",
    "status": "open",
    "priority": 1,
    "assigned_to": "uuid" or null,
    "description": "Sugar level checkup",
    "created_at": "2026-01-10T20:39:00"
  }
]
```

### 2. **Get Ticket Details**
```
GET /api/tickets/{ticket_id}
```

**Response:**
```json
{
  "ticket_id": "uuid",
  "conversation_id": "uuid",
  "patient_id": "uuid",
  "service_type": "lab test",
  "status": "open",
  "priority": 1,
  "assigned_to": "uuid" or null,
  "description": "Sugar level checkup",
  "patient_details": {...},
  "past_history_summary": "...",
  "llm_summary": "...",
  "current_symptoms": "...",
  "created_at": "2026-01-10T20:39:00",
  "assigned_at": "2026-01-10T20:40:00" or null,
  "completed_at": null
}
```

## Frontend Integration

In the frontend dashboard:
1. **Patient Dashboard**: Shows tickets created for the patient
2. **Service Person Dashboard**: Shows tickets assigned to that specific doctor/service person
3. **Admin Dashboard**: Shows all tickets in the system

## Ticket Status Flow

1. **`open`**: Ticket created, not yet assigned
2. **`assigned`**: Ticket assigned to a doctor (via accept/reject action)
3. **`in_progress`**: Doctor is working on the ticket
4. **`completed`**: Ticket resolved
5. **`cancelled`**: Ticket cancelled (either rejected by doctor or replaced by another doctor accepting)

## When Tickets Are Created

Tickets are automatically created when:
1. Patient completes verification (provides name, phone, DOB)
2. Patient provides service request (e.g., "I need to check sugar level")
3. Patient provides date/time preference
4. System finds available doctors
5. System ranks doctors based on patient history and specialization
6. Top N doctors (configurable, default: 5) receive tickets

## Checking Ticket Assignment

To check if tickets were assigned:
1. Call `GET /api/tickets` with a service person's token
2. Filter by `status=assigned` to see accepted tickets
3. Check `assigned_to` field - it will contain the doctor's ID if assigned
4. Check `assigned_at` timestamp to see when it was assigned

## Example: Check Assigned Tickets (Service Person)

```bash
# Login as service person
POST /api/auth/login/service-person
{
  "phone_number": "doctor-phone",
  "password": "password"
}

# Get assigned tickets
GET /api/tickets?status=assigned
Authorization: Bearer <token>
```

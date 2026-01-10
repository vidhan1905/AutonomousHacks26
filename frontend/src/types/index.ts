export interface User {
  id: string
  name?: string
  username?: string
  phone?: string
  email?: string
  type: 'patient' | 'service_person' | 'admin'
  service_type?: string
  role?: string
}

export interface Message {
  message_id: string
  sender_type: 'patient' | 'llm'
  content: string
  created_at: string
}

export interface Conversation {
  conversation_id: string
  patient_id: string | null
  status: string
  started_at: string
  ended_at: string | null
}

export interface Ticket {
  ticket_id: string
  conversation_id: string
  patient_id: string
  service_type: string
  status: string
  priority: number
  assigned_to: string | null
  description: string
  patient_details: any
  past_history_summary: string | null
  llm_summary: string | null
  current_symptoms: any
  created_at: string
  assigned_at: string | null
  completed_at: string | null
}

export interface Appointment {
  appointment_id: string
  ticket_id: string | null
  patient_id: string
  service_person_id: string | null
  appointment_type: string
  scheduled_date: string
  status: string
  notes: string | null
  created_at: string
}

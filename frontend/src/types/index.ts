export interface User {
  id: string
  name?: string
  username?: string
  phone?: string
  email?: string
  type: 'patient' | 'service_person'
  service_type?: string
  role?: string
}

export interface DoctorRecommendation {
  doctor_id: string
  name: string
  service_type: string
  specialization?: string
  rank: number
  reason: string
  ticket_id?: string
}

export interface Message {
  message_id: string
  sender_type: 'patient' | 'llm'
  content: string
  created_at: string
  type?: 'doctor_recommendation' | 'text'
  doctors?: DoctorRecommendation[]
  service_type?: string
  metadata?: {
    type?: string
    doctors?: DoctorRecommendation[]
    service_type?: string
    tickets_created?: number
  }
}

export interface Conversation {
  conversation_id: string
  patient_id: string | null
  status: string
  started_at: string
  ended_at: string | null
  summary?: string | null
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
  is_sequential_review?: boolean
  sequential_review_chain_id?: string | null
}

export interface SequentialReviewTicket {
  ticket_id: string
  chain_id: string
  conversation_id: string
  patient_id: string
  status: 'step_pending' | 'step_accepted' | 'step_in_progress' | 'step_completed' | 'chain_completed' | 'chain_cancelled'
  step_id: string  // Direct link to step (replaces current_step_id)
  step_index: number  // Position in sequence (0, 1, 2, 3...)
  can_start: boolean  // Whether this step can be started (previous step completed)
  current_step?: {  // Keep for backward compatibility
    step_id: string
    step_index: number
    doctor_id: string
    doctor_name: string
    service_type: string
    status: string
    review_notes: string | null
    review_summary: string | null
  }
  description: string
  llm_summary: string | null
  patient_details: any
  past_history_summary: string | null
  created_at: string
  updated_at: string
  chain_completed_at: string | null
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

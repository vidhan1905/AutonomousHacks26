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

export interface SequentialReviewStep {
  step_id: string
  step_index: number
  step_number: number
  doctor_id: string
  doctor_name: string
  service_type: string
  status: string
  review_notes?: string | null
  review_summary?: string | null
  started_at?: string | null
  completed_at?: string | null
}

export interface SequentialReviewInfo {
  chain_id: string
  current_step_index: number
  current_step_number: number
  total_steps: number
  chain_status: string
  steps: SequentialReviewStep[]
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
  sequential_review_info?: SequentialReviewInfo
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

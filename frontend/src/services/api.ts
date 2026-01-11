import axios from 'axios'
import type { User, Conversation, Message, Ticket, Appointment, SequentialReviewTicket } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auth endpoints
export const authApi = {
  login: async (username: string, password: string, userType: string) => {
    const response = await api.post('/api/auth/login', {
      username,
      password,
      user_type: userType,
    })
    return response.data
  },
  
  patientLogin: async (phoneNumber: string, password: string) => {
    const response = await api.post('/api/auth/login/patient', {
      phone_number: phoneNumber,
      password: password,
    })
    return response.data
  },
  
  register: async (data: {
    name: string
    phone_number: string
    email: string
    password: string
    date_of_birth: string
    gender: string
  }) => {
    const response = await api.post('/api/auth/register', data)
    return response.data
  },
  
  getMe: async (): Promise<User> => {
    const response = await api.get('/api/auth/me')
    return response.data
  },
  
  logout: async () => {
    await api.post('/api/auth/logout')
    localStorage.removeItem('token')
  },
}

// Conversation endpoints
export const conversationApi = {
  create: async () => {
    // Backend uses authenticated patient automatically
    const response = await api.post('/api/conversations', {})
    return response.data
  },
  
  get: async (conversationId: string): Promise<Conversation> => {
    const response = await api.get(`/api/conversations/${conversationId}`)
    return response.data
  },
  
  sendMessage: async (conversationId: string, content: string): Promise<Message> => {
    const response = await api.post(`/api/conversations/${conversationId}/messages`, {
      content,
    })
    return response.data
  },
  
  getMessages: async (conversationId: string): Promise<Message[]> => {
    const response = await api.get(`/api/conversations/${conversationId}/messages`)
    return response.data
  },
  
  list: async (): Promise<Conversation[]> => {
    // Backend uses authenticated patient automatically
    const response = await api.get('/api/conversations')
    return response.data
  },
}

// Ticket endpoints
export const ticketApi = {
  list: async (filters?: {
    status?: string
    service_type?: string
    priority?: number
  }): Promise<Ticket[]> => {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/a61d17be-af11-4c91-8ff2-4d1814fc0e77', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId: 'debug-session',
        runId: 'run1',
        hypothesisId: 'C',
        location: 'api.ts:103',
        message: 'ticketApi.list called',
        data: { filters },
        timestamp: Date.now()
      })
    }).catch(() => {})
    // #endregion
    const response = await api.get('/api/tickets', { params: filters })
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/a61d17be-af11-4c91-8ff2-4d1814fc0e77', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId: 'debug-session',
        runId: 'run1',
        hypothesisId: 'C',
        location: 'api.ts:111',
        message: 'ticketApi.list response received',
        data: { status: response.status, dataLength: response.data?.length },
        timestamp: Date.now()
      })
    }).catch(() => {})
    // #endregion
    return response.data
  },
  
  get: async (ticketId: string): Promise<Ticket> => {
    const response = await api.get(`/api/tickets/${ticketId}`)
    return response.data
  },
  
  assign: async (ticketId: string, servicePersonId: string) => {
    const response = await api.put(`/api/tickets/${ticketId}/assign`, {
      service_person_id: servicePersonId,
    })
    return response.data
  },
  
  updateStatus: async (ticketId: string, status: string, comment?: string) => {
    const response = await api.put(`/api/tickets/${ticketId}/status`, {
      status,
      comment,
    })
    return response.data
  },
  
  addComment: async (ticketId: string, comment: string) => {
    const response = await api.post(`/api/tickets/${ticketId}/comments`, {
      comment,
    })
    return response.data
  },
  
  acceptReject: async (ticketId: string, action: 'accept' | 'reject') => {
    const response = await api.post(`/api/tickets/${ticketId}/accept-reject`, {
      action,
    })
    return response.data
  },
  
  getSequentialProgress: async (ticketId: string) => {
    const response = await api.get(`/api/tickets/${ticketId}/sequential-progress`)
    return response.data
  },
}

// Sequential review ticket endpoints
export const sequentialReviewTicketApi = {
  list: async (filters?: {
    status?: string
  }): Promise<SequentialReviewTicket[]> => {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/a61d17be-af11-4c91-8ff2-4d1814fc0e77', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId: 'debug-session',
        runId: 'run1',
        hypothesisId: 'D',
        location: 'api.ts:152',
        message: 'sequentialReviewTicketApi.list called',
        data: { filters },
        timestamp: Date.now()
      })
    }).catch(() => {})
    // #endregion
    const response = await api.get('/api/sequential-review-tickets', { params: filters })
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/a61d17be-af11-4c91-8ff2-4d1814fc0e77', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId: 'debug-session',
        runId: 'run1',
        hypothesisId: 'D',
        location: 'api.ts:160',
        message: 'sequentialReviewTicketApi.list response received',
        data: { status: response.status, dataLength: response.data?.length },
        timestamp: Date.now()
      })
    }).catch(() => {})
    // #endregion
    return response.data
  },
  
  get: async (ticketId: string): Promise<SequentialReviewTicket> => {
    const response = await api.get(`/api/sequential-review-tickets/${ticketId}`)
    return response.data
  },
  
  getProgress: async (ticketId: string) => {
    const response = await api.get(`/api/sequential-review-tickets/${ticketId}/progress`)
    return response.data
  },
  
  acceptStep: async (ticketId: string) => {
    const response = await api.post(`/api/sequential-review-tickets/${ticketId}/accept-step`, {})
    return response.data
  },
  
  rejectStep: async (ticketId: string, reason?: string) => {
    const response = await api.post(`/api/sequential-review-tickets/${ticketId}/reject-step`, {
      reason,
    })
    return response.data
  },
  
  updateStepStatus: async (ticketId: string, status: 'step_accepted' | 'step_in_progress' | 'step_completed', reviewNotes?: string) => {
    const response = await api.put(`/api/sequential-review-tickets/${ticketId}/step-status`, {
      status,
      review_notes: reviewNotes,
    })
    return response.data
  },
}

// Appointment endpoints
export const appointmentApi = {
  list: async (filters?: {
    patient_id?: string
    service_person_id?: string
    status?: string
  }): Promise<Appointment[]> => {
    const response = await api.get('/api/appointments', { params: filters })
    return response.data
  },
}

// Patient endpoints
export const patientApi = {
  getProfile: async () => {
    const response = await api.get('/api/patients/profile')
    return response.data
  },
  
  updateProfile: async (data: {
    email?: string
    address?: string
    emergency_contact?: {
      name: string
      phone: string
      relationship: string
    }
    blood_group?: string
    gender?: string
  }) => {
    const response = await api.put('/api/patients/profile', data)
    return response.data
  },
  
  create: async (data: {
    patient_id: string
    service_type: string
    scheduled_date: string
    service_person_id?: string
    ticket_id?: string
    notes?: string
  }) => {
    const response = await api.post('/api/appointments', data)
    return response.data
  },
  
  update: async (appointmentId: string, data: {
    scheduled_date?: string
    status?: string
    notes?: string
  }) => {
    const response = await api.put(`/api/appointments/${appointmentId}`, data)
    return response.data
  },
}

export default api

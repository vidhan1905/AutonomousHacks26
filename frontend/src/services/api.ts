import axios from 'axios'
import type { User, Conversation, Message, Ticket, Appointment } from '../types'

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
  
  patientLogin: async (phoneNumber: string) => {
    const response = await api.post('/api/auth/login/patient', {
      phone_number: phoneNumber,
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
  create: async (patientId?: string, anonymous = false) => {
    const response = await api.post('/api/conversations', {
      patient_id: patientId,
      anonymous,
    })
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
  
  list: async (patientId?: string): Promise<Conversation[]> => {
    const params = patientId ? { patient_id: patientId } : {}
    const response = await api.get('/api/conversations', { params })
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
    const response = await api.get('/api/tickets', { params: filters })
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
  
  updateStatus: async (ticketId: string, status: string) => {
    const response = await api.put(`/api/tickets/${ticketId}/status`, {
      status,
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

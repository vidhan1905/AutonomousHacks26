import { create } from 'zustand'
import type { User } from '../types'
import { authApi } from '../services/api'

interface AuthState {
  user: User | null
  token: string | null
  login: (username: string, password: string, userType: string) => Promise<void>
  patientLogin: (phoneNumber: string) => Promise<void>
  logout: () => Promise<void>
  loadUser: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('token'),
  
  login: async (username: string, password: string, userType: string) => {
    const response = await authApi.login(username, password, userType)
    localStorage.setItem('token', response.access_token)
    set({ user: response.user, token: response.access_token })
  },
  
  patientLogin: async (phoneNumber: string) => {
    const response = await authApi.patientLogin(phoneNumber)
    localStorage.setItem('token', response.access_token)
    set({ user: response.user, token: response.access_token })
  },
  
  logout: async () => {
    await authApi.logout()
    set({ user: null, token: null })
  },
  
  loadUser: async () => {
    try {
      const user = await authApi.getMe()
      set({ user })
    } catch (error) {
      set({ user: null, token: null })
      localStorage.removeItem('token')
    }
  },
}))

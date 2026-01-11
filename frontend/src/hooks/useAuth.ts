import { create } from 'zustand'
import type { User } from '../types'
import { authApi } from '../services/api'

interface AuthState {
  user: User | null
  token: string | null
  isInitialized: boolean
  login: (username: string, password: string, userType: string) => Promise<void>
  patientLogin: (phoneNumber: string, password: string) => Promise<void>
  register: (data: { name: string; phone_number: string; email: string; password: string; date_of_birth: string; gender: string }) => Promise<void>
  logout: () => Promise<void>
  loadUser: () => Promise<void>
  initialize: () => Promise<void>
}

// Helper functions to manage localStorage
const getUserFromStorage = (): User | null => {
  try {
    const userStr = localStorage.getItem('user')
    return userStr ? JSON.parse(userStr) : null
  } catch {
    return null
  }
}

const saveUserToStorage = (user: User | null) => {
  if (user) {
    localStorage.setItem('user', JSON.stringify(user))
  } else {
    localStorage.removeItem('user')
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: getUserFromStorage(),
  token: localStorage.getItem('token'),
  isInitialized: false,
  
  login: async (username: string, password: string, userType: string) => {
    const response = await authApi.login(username, password, userType)
    localStorage.setItem('token', response.access_token)
    saveUserToStorage(response.user)
    set({ user: response.user, token: response.access_token })
  },
  
  register: async (data: { name: string; phone_number: string; email: string; password: string; date_of_birth: string; gender: string }) => {
    const response = await authApi.register(data)
    localStorage.setItem('token', response.access_token)
    saveUserToStorage(response.user)
    set({ user: response.user, token: response.access_token })
  },
  
  logout: async () => {
    try {
      await authApi.logout()
    } catch (error) {
      // Continue with logout even if API call fails
      console.error('Logout API error:', error)
    }
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    set({ user: null, token: null })
  },
  
  loadUser: async () => {
    try {
      const user = await authApi.getMe()
      saveUserToStorage(user)
      set({ user })
    } catch (error) {
      // If token is invalid, clear everything
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      set({ user: null, token: null })
    }
  },
  
  initialize: async () => {
    const { token, user } = get()
    
    // If we have a token but no user, try to load user from API
    if (token && !user) {
      try {
        const loadedUser = await authApi.getMe()
        saveUserToStorage(loadedUser)
        set({ user: loadedUser, isInitialized: true })
      } catch (error) {
        // Token is invalid, clear everything
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        set({ user: null, token: null, isInitialized: true })
      }
    } else if (token && user) {
      // We have both token and user from storage, validate with backend
      try {
        const loadedUser = await authApi.getMe()
        // Update user in case it changed
        saveUserToStorage(loadedUser)
        set({ user: loadedUser, isInitialized: true })
      } catch (error) {
        // Token is invalid, clear everything
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        set({ user: null, token: null, isInitialized: true })
      }
    } else {
      // No token, mark as initialized
      set({ isInitialized: true })
    }
  },
}))

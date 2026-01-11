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
  syncFromStorage: () => void
}

// Helper functions to manage localStorage with separate keys for different user types
const getStorageKey = (userType: 'patient' | 'service_person' | null) => {
  if (!userType) return null
  return {
    token: `token_${userType}`,
    user: `user_${userType}`
  }
}

const getUserFromStorage = (userType?: 'patient' | 'service_person' | null): User | null => {
  try {
    // If userType is specified, use type-specific key
    if (userType) {
      const keys = getStorageKey(userType)
      if (!keys) return null
      const userStr = localStorage.getItem(keys.user)
      return userStr ? JSON.parse(userStr) : null
    }
    
    // Otherwise, try to find any user (check both types)
    const patientUser = localStorage.getItem('user_patient')
    if (patientUser) {
      return JSON.parse(patientUser)
    }
    const serviceUser = localStorage.getItem('user_service_person')
    if (serviceUser) {
      return JSON.parse(serviceUser)
    }
    return null
  } catch {
    return null
  }
}

const saveUserToStorage = (user: User | null) => {
  if (user) {
    const keys = getStorageKey(user.type as 'patient' | 'service_person')
    if (keys) {
      localStorage.setItem(keys.user, JSON.stringify(user))
    }
  } else {
    // Clear both types if user is null
    localStorage.removeItem('user_patient')
    localStorage.removeItem('user_service_person')
  }
}

const getTokenFromStorage = (userType?: 'patient' | 'service_person' | null): string | null => {
  if (userType) {
    const keys = getStorageKey(userType)
    if (!keys) return null
    return localStorage.getItem(keys.token)
  }
  
  // Try to find any token (check both types)
  return localStorage.getItem('token_patient') || localStorage.getItem('token_service_person')
}

const saveTokenToStorage = (token: string | null, userType: 'patient' | 'service_person' | null) => {
  if (token && userType) {
    const keys = getStorageKey(userType)
    if (keys) {
      localStorage.setItem(keys.token, token)
    }
  } else {
    // Clear both types if token is null
    localStorage.removeItem('token_patient')
    localStorage.removeItem('token_service_person')
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: getUserFromStorage(),
  token: getTokenFromStorage(),
  isInitialized: false,
  
  syncFromStorage: () => {
    const currentState = get()
    
    // Don't sync if we're not initialized yet - let initialize handle it first
    if (!currentState.isInitialized) {
      return
    }
    
    // Get token and user based on current user type
    const currentUserType = currentState.user?.type as 'patient' | 'service_person' | null
    const token = getTokenFromStorage(currentUserType)
    const user = getUserFromStorage(currentUserType)
    
    // Only update if something actually changed
    const tokenChanged = currentState.token !== token
    const userChanged = JSON.stringify(currentState.user) !== JSON.stringify(user)
    
    if (tokenChanged || userChanged) {
      set({ user, token })
    }
  },
  
  login: async (username: string, password: string, userType: string) => {
    const response = await authApi.login(username, password, userType)
    const typedUserType = userType as 'patient' | 'service_person'
    saveTokenToStorage(response.access_token, typedUserType)
    saveUserToStorage(response.user)
    set({ user: response.user, token: response.access_token })
  },
  
  register: async (data: { name: string; phone_number: string; email: string; password: string; date_of_birth: string; gender: string }) => {
    const response = await authApi.register(data)
    saveTokenToStorage(response.access_token, 'patient') // Registration is always for patients
    saveUserToStorage(response.user)
    set({ user: response.user, token: response.access_token })
  },
  
  logout: async () => {
    const currentState = get()
    const currentUserType = currentState.user?.type as 'patient' | 'service_person' | null
    
    try {
      await authApi.logout()
    } catch (error) {
      // Continue with logout even if API call fails
      console.error('Logout API error:', error)
    }
    
    // Only clear the current user type's storage, not both
    if (currentUserType) {
      const keys = getStorageKey(currentUserType)
      if (keys) {
        localStorage.removeItem(keys.token)
        localStorage.removeItem(keys.user)
      }
    }
    set({ user: null, token: null })
  },
  
  loadUser: async () => {
    const currentState = get()
    const currentUserType = currentState.user?.type as 'patient' | 'service_person' | null
    
    try {
      const user = await authApi.getMe()
      saveUserToStorage(user)
      set({ user })
    } catch (error) {
      // If token is invalid, clear only this user type's storage
      if (currentUserType) {
        const keys = getStorageKey(currentUserType)
        if (keys) {
          localStorage.removeItem(keys.token)
          localStorage.removeItem(keys.user)
        }
      }
      set({ user: null, token: null })
    }
  },
  
  initialize: async () => {
    // Try to get user from storage (checks both types)
    const storedUser = getUserFromStorage()
    const storedToken = getTokenFromStorage(storedUser?.type as 'patient' | 'service_person' | null)
    
    // If we have a token but no user, try to load user from API
    if (storedToken && !storedUser) {
      try {
        const loadedUser = await authApi.getMe()
        saveUserToStorage(loadedUser)
        saveTokenToStorage(storedToken, loadedUser.type as 'patient' | 'service_person')
        set({ user: loadedUser, token: storedToken, isInitialized: true })
      } catch (error) {
        // Token is invalid, clear both types' storage
        localStorage.removeItem('token_patient')
        localStorage.removeItem('token_service_person')
        localStorage.removeItem('user_patient')
        localStorage.removeItem('user_service_person')
        set({ user: null, token: null, isInitialized: true })
      }
    } else if (storedToken && storedUser) {
      // We have both token and user from storage, validate with backend
      try {
        const loadedUser = await authApi.getMe()
        // Update user in case it changed
        saveUserToStorage(loadedUser)
        saveTokenToStorage(storedToken, loadedUser.type as 'patient' | 'service_person')
        set({ user: loadedUser, token: storedToken, isInitialized: true })
      } catch (error) {
        // Token is invalid, clear this user type's storage
        const userType = storedUser.type as 'patient' | 'service_person'
        const keys = getStorageKey(userType)
        if (keys) {
          localStorage.removeItem(keys.token)
          localStorage.removeItem(keys.user)
        }
        set({ user: null, token: null, isInitialized: true })
      }
    } else {
      // No token, mark as initialized
      set({ user: storedUser, token: storedToken, isInitialized: true })
    }
  },
}))

import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import Login from './pages/Login'
import ChatPage from './pages/ChatPage'
import PatientDashboard from './pages/PatientDashboard'
import ServicePersonDashboard from './pages/ServicePersonDashboard'
import TicketDetailPage from './pages/TicketDetailPage'
import ProtectedRoute from './components/Auth/ProtectedRoute'
import { useAuthStore } from './hooks/useAuth'

function App() {
  const { user, initialize, isInitialized, syncFromStorage } = useAuthStore()

  // Initialize auth state on app mount
  useEffect(() => {
    if (!isInitialized) {
      initialize()
    }
  }, [initialize, isInitialized])

  // Sync auth state across browser tabs when localStorage changes
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      // Only react to token or user changes from other tabs
      // Storage events only fire for changes in OTHER tabs, not the current tab
      if (e.key === 'token' || e.key === 'user') {
        syncFromStorage()
      }
    }

    // Listen for storage events from other tabs
    window.addEventListener('storage', handleStorageChange)

    return () => {
      window.removeEventListener('storage', handleStorageChange)
    }
  }, [syncFromStorage])

  // Show loading state while initializing
  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/patient"
          element={
            <ProtectedRoute requiredType="patient">
              <PatientDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile/edit"
          element={
            <ProtectedRoute requiredType="patient">
              <EditProfilePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/service-person"
          element={
            <ProtectedRoute requiredType="service_person">
              <ServicePersonDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tickets/:ticketId"
          element={
            <ProtectedRoute>
              <TicketDetailPage />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to={user ? (user.type === 'patient' ? "/dashboard/patient" : "/dashboard/service-person") : "/login"} replace />} />
      </Routes>
    </Router>
  )
}

export default App

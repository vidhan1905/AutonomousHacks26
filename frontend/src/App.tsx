import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import Login from './pages/Login'
import ChatPage from './pages/ChatPage'
import PatientDashboard from './pages/PatientDashboard'
import ServicePersonDashboard from './pages/ServicePersonDashboard'
import TicketDetailPage from './pages/TicketDetailPage'
import SequentialReviewTicketDetailPage from './pages/SequentialReviewTicketDetailPage'
import EditProfilePage from './pages/EditProfilePage'
import ProtectedRoute from './components/Auth/ProtectedRoute'
import { useAuthStore } from './hooks/useAuth'

function App() {
  const { user, initialize, isInitialized } = useAuthStore()

  // Initialize auth state on app mount
  useEffect(() => {
    if (!isInitialized) {
      initialize()
    }
  }, [initialize, isInitialized])

  // Show loading state while initializing
  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-500 dark:border-teal-400 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">Loading...</p>
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
            <ProtectedRoute requiredType="service_person">
              <TicketDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tickets/sequential-review/:ticketId"
          element={
            <ProtectedRoute requiredType="service_person">
              <SequentialReviewTicketDetailPage />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to={user ? (user.type === 'patient' ? "/dashboard/patient" : user.type === 'service_person' ? "/dashboard/service-person" : "/login") : "/login"} replace />} />
      </Routes>
    </Router>
  )
}

export default App

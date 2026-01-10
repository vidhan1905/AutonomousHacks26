import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import ChatPage from './pages/ChatPage'
import PatientDashboard from './pages/PatientDashboard'
import ServicePersonDashboard from './pages/ServicePersonDashboard'
import ProtectedRoute from './components/Auth/ProtectedRoute'
import { useAuthStore } from './hooks/useAuth'

function App() {
  const { user } = useAuthStore()

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
          path="/dashboard/service-person"
          element={
            <ProtectedRoute requiredType="service_person">
              <ServicePersonDashboard />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to={user ? "/dashboard/patient" : "/login"} replace />} />
      </Routes>
    </Router>
  )
}

export default App

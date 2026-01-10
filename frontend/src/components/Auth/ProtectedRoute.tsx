import { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../../hooks/useAuth'

interface ProtectedRouteProps {
  children: ReactNode
  requiredType?: 'patient' | 'service_person'
}

export default function ProtectedRoute({ children, requiredType }: ProtectedRouteProps) {
  const { user, token, isInitialized } = useAuthStore()

  // Wait for initialization to complete
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

  if (!token || !user) {
    return <Navigate to="/login" replace />
  }

  if (requiredType && user.type !== requiredType) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

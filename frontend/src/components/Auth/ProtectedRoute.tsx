import { ReactNode, useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../../hooks/useAuth'

interface ProtectedRouteProps {
  children: ReactNode
  requiredType?: 'patient' | 'service_person' | 'admin'
}

export default function ProtectedRoute({ children, requiredType }: ProtectedRouteProps) {
  const { user, token, loadUser } = useAuthStore()

  useEffect(() => {
    if (token && !user) {
      loadUser()
    }
  }, [token, user, loadUser])

  if (!token) {
    return <Navigate to="/login" replace />
  }

  if (requiredType && user?.type !== requiredType) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

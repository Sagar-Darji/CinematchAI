import { Navigate } from 'react-router-dom'
import { useUserStore } from '@/store/useUserStore'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { userId, isOnboarded } = useUserStore()

  if (!userId) {
    return <Navigate to="/login" replace />
  }

  if (!isOnboarded) {
    return <Navigate to="/onboarding" replace />
  }

  return <>{children}</>
}

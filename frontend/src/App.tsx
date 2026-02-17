import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import Home from '@/pages/Home'
import Login from '@/pages/Login'
import Onboarding from '@/pages/Onboarding'
import Recommendations from '@/pages/Recommendations'
import Browse from '@/pages/Browse'
import Profile from '@/pages/Profile'
import { useUserStore } from '@/store/useUserStore'

export default function App() {
  const { userId, isOnboarded } = useUserStore()

  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={userId && isOnboarded ? <Navigate to="/" replace /> : <Login />} />
        <Route path="/onboarding" element={<Onboarding />} />

        {/* Protected routes */}
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route 
            path="/recommendations" 
            element={
              <ProtectedRoute>
                <Recommendations />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/browse" 
            element={
              <ProtectedRoute>
                <Browse />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/profile" 
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            } 
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

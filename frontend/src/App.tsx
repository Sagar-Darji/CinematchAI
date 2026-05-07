import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { Layout } from '@/components/layout/Layout'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import Home from '@/pages/Home'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import ForgotPassword from '@/pages/ForgotPassword'
import ResetPassword from '@/pages/ResetPassword'
import Onboarding from '@/pages/Onboarding'
import Recommendations from '@/pages/Recommendations'
import Browse from '@/pages/Browse'
import Profile from '@/pages/Profile'
import Digest from '@/pages/Digest'
import ReleaseCalendar from '@/pages/ReleaseCalendar'
import MovieWeb from '@/pages/MovieWeb'
import Search from '@/pages/Search'
import MovieDetail from '@/pages/MovieDetail'
import Watchlist from '@/pages/Watchlist'
import { useUserStore } from '@/store/useUserStore'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ''
const GOOGLE_ENABLED = GOOGLE_CLIENT_ID.length > 0

export default function App() {
  const { userId, isOnboarded } = useUserStore()

  const routes = (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={userId && isOnboarded ? <Navigate to="/" replace /> : <Login />} />
        <Route path="/register" element={userId && isOnboarded ? <Navigate to="/" replace /> : <Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
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
          <Route path="/digest" element={<Digest />} />
          <Route path="/calendar" element={<ReleaseCalendar />} />
          <Route path="/web" element={<MovieWeb />} />
          <Route path="/search" element={<Search />} />
          <Route path="/title/:mediaType/:tmdbId" element={<MovieDetail />} />
          <Route
            path="/watchlist"
            element={
              <ProtectedRoute>
                <Watchlist />
              </ProtectedRoute>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )

  return GOOGLE_ENABLED
    ? <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>{routes}</GoogleOAuthProvider>
    : routes
}

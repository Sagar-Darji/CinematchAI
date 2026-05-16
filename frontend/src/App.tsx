import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { Layout } from '@/components/layout/Layout'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { getCurrentUser } from '@/lib/api'
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
import Settings from '@/pages/Settings'
import SettingsImport from '@/pages/SettingsImport'
import { useUserStore } from '@/store/useUserStore'
import { useWatchlistStore } from '@/store/useWatchlistStore'
import { useHistoryStore } from '@/store/useHistoryStore'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ''
const GOOGLE_ENABLED = GOOGLE_CLIENT_ID.length > 0

export default function App() {
  const { userId, isOnboarded, token, hasHydrated } = useUserStore()

  // On boot: if we have a persisted token, ping /me to validate it. The api
  // wrapper handles 401 by clearing local state and bouncing to /login, so we
  // don't need to do anything with the result here. Also sync watchlist and
  // history from the backend so cross-device state and cache-wiped users
  // get their data back.
  useEffect(() => {
    if (hasHydrated && token) {
      getCurrentUser().catch(() => { /* handled by 401 interceptor */ })
      useWatchlistStore.getState().syncFromServer().catch(() => { /* offline */ })
      useHistoryStore.getState().syncFromServer().catch(() => { /* offline */ })
    }
  }, [hasHydrated, token])

  // Avoid the login-screen flash on slow devices: don't render routes until
  // Zustand has finished reading persisted state from localStorage.
  if (!hasHydrated) {
    return (
      <div
        style={{
          minHeight: '100dvh',
          background: 'var(--bg-primary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          aria-hidden
          style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            border: '2px solid var(--border)',
            borderTopColor: 'var(--accent-gold)',
            animation: 'spin 0.8s linear infinite',
          }}
        />
        <style>{'@keyframes spin{to{transform:rotate(360deg)}}'}</style>
      </div>
    )
  }

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
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <Settings />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings/import"
            element={
              <ProtectedRoute>
                <SettingsImport />
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

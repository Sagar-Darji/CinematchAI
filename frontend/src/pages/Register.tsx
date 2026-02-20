import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ArrowRight, Loader2, Eye, EyeOff } from 'lucide-react'
import { useGoogleLogin } from '@react-oauth/google'
import { useUserStore } from '@/store/useUserStore'
import { registerUser, googleAuth } from '@/lib/api'

export default function Register() {
  const navigate = useNavigate()
  const { setUserId, setEmail, setToken, setOnboarded } = useUserStore()

  const [username, setUsername] = useState('')
  const [email, setEmailInput] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [error, setError] = useState('')

  const _onSuccess = (auth: Awaited<ReturnType<typeof registerUser>>, isNew: boolean) => {
    setUserId(auth.user_id)
    setEmail(auth.email)
    setToken(auth.token)
    setOnboarded(!isNew)
    navigate(isNew ? '/onboarding' : '/')
  }

  const handleRegister = async () => {
    if (!username.trim() || !email.trim() || !password) return
    setLoading(true); setError('')
    try {
      const auth = await registerUser(username.trim(), email.trim(), password)
      _onSuccess(auth, true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally { setLoading(false) }
  }

  const handleGoogleRegister = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      setGoogleLoading(true); setError('')
      try {
        const userInfoRes = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
          headers: { Authorization: `Bearer ${tokenResponse.access_token}` },
        })
        const userInfo = await userInfoRes.json()
        const auth = await googleAuth(tokenResponse.access_token, userInfo.sub)
        _onSuccess(auth, auth.is_new_user)
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Google sign-up failed.')
      } finally { setGoogleLoading(false) }
    },
    onError: () => setError('Google sign-up was cancelled or failed.'),
  })

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-4"
      style={{ background: 'var(--bg-primary)' }}
    >
      <div className="w-full max-w-sm">
        <div className="text-center mb-10">
          <p className="text-xs font-bold tracking-[0.3em] uppercase mb-3" style={{ color: 'var(--accent-gold)' }}>
            CineMatch AI
          </p>
          <h1 className="text-4xl font-black tracking-tight text-white">Create account</h1>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-muted)' }}>
            Build your taste profile and get personalised recommendations.
          </p>
        </div>

        <div className="flex flex-col gap-3">
          {/* Google Sign-Up */}
          <button
            onClick={() => handleGoogleRegister()}
            disabled={googleLoading || loading}
            className="flex items-center justify-center gap-3 py-4 rounded-xl font-semibold text-base disabled:opacity-40 transition-opacity"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)', cursor: 'pointer' }}
          >
            {googleLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <svg width="18" height="18" viewBox="0 0 48 48" fill="none">
                <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.6 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34 6.4 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.9z"/>
                <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.5 16 19 12 24 12c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34 6.4 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
                <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.3 35.2 26.8 36 24 36c-5.3 0-9.6-3.3-11.3-8H6.3C9.6 35.5 16.3 44 24 44z"/>
                <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.3-2.3 4.3-4.2 5.6l6.2 5.2C43 35 44 30 44 24c0-1.3-.1-2.6-.4-3.9z"/>
              </svg>
            )}
            Continue with Google
          </button>

          <div className="flex items-center gap-3 my-1">
            <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>or sign up with email</span>
            <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
          </div>

          <input
            type="text"
            autoFocus
            placeholder="Username (3–32 chars, letters/numbers/_/-)"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full px-5 py-4 rounded-xl text-base outline-none"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
          />

          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmailInput(e.target.value)}
            className="w-full px-5 py-4 rounded-xl text-base outline-none"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
          />

          <div className="relative">
            <input
              type={showPw ? 'text' : 'password'}
              placeholder="Password (min 8 characters)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleRegister()}
              className="w-full px-5 py-4 rounded-xl text-base outline-none pr-12"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            />
            <button
              type="button"
              onClick={() => setShowPw((v) => !v)}
              className="absolute right-4 top-1/2 -translate-y-1/2"
              style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          {error && (
            <p className="text-sm px-1" style={{ color: 'var(--accent-red)' }}>{error}</p>
          )}

          <button
            onClick={handleRegister}
            disabled={loading || !username.trim() || !email.trim() || !password}
            className="flex items-center justify-center gap-2 py-4 rounded-xl font-bold text-base disabled:opacity-40 transition-opacity"
            style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
          >
            {loading ? <Loader2 size={18} className="animate-spin" /> : <ArrowRight size={18} />}
            Create Account
          </button>

          <p className="text-center text-sm mt-2" style={{ color: 'var(--text-muted)' }}>
            Already have an account?{' '}
            <Link to="/login" className="font-medium hover:underline" style={{ color: 'var(--accent-gold)' }}>
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

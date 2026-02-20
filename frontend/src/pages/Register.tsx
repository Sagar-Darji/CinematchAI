import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ArrowRight, Loader2, Eye, EyeOff } from 'lucide-react'
import { useUserStore } from '@/store/useUserStore'
import { registerUser } from '@/lib/api'

export default function Register() {
  const navigate = useNavigate()
  const { setUserId, setEmail, setToken, setOnboarded } = useUserStore()

  const [username, setUsername] = useState('')
  const [email, setEmailInput] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleRegister = async () => {
    if (!username.trim() || !email.trim() || !password) return
    setLoading(true)
    setError('')
    try {
      const auth = await registerUser(username.trim(), email.trim(), password)
      setUserId(auth.user_id)
      setEmail(auth.email)
      setToken(auth.token)
      setOnboarded(false)
      // Send to onboarding to rate some movies and build profile
      navigate('/onboarding')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

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

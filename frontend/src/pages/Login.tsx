import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Loader2 } from 'lucide-react'
import { useUserStore } from '@/store/useUserStore'
import { getUserProfile } from '@/lib/api'

export default function Login() {
  const navigate = useNavigate()
  const { setUserId, setOnboarded, setRatingCount } = useUserStore()

  const [username, setUsername] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleLogin = async () => {
    const trimmed = username.trim()
    if (!trimmed) return
    setLoading(true)
    setError('')
    try {
      const profile = await getUserProfile(trimmed)
      if (!profile) {
        setError('User not found. Please check your username or create a new account.')
        return
      }
      setUserId(trimmed)
      setRatingCount(profile.total_ratings ?? 0)
      setOnboarded(true)
      navigate('/')
    } catch {
      setError('Something went wrong. Please try again.')
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
          <h1 className="text-4xl font-black tracking-tight text-white">Welcome back</h1>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-muted)' }}>
            Sign in to access your taste profile and recommendations.
          </p>
        </div>

        <div className="flex flex-col gap-3">
          <input
            type="text"
            autoFocus
            placeholder="Your username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            className="w-full px-5 py-4 rounded-xl text-lg outline-none"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
          />

          {error && (
            <p className="text-sm px-1" style={{ color: 'var(--accent-red)' }}>{error}</p>
          )}

          <button
            onClick={handleLogin}
            disabled={loading || !username.trim()}
            className="flex items-center justify-center gap-2 py-4 rounded-xl font-bold text-base disabled:opacity-40 transition-opacity"
            style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
          >
            {loading ? <Loader2 size={18} className="animate-spin" /> : <ArrowRight size={18} />}
            Sign In
          </button>

          <p className="text-center text-sm mt-2" style={{ color: 'var(--text-muted)' }}>
            New here?{' '}
            <a
              href="/onboarding"
              className="font-medium hover:underline"
              style={{ color: 'var(--accent-gold)' }}
            >
              Create an account
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { Loader2, Eye, EyeOff, CheckCircle, ArrowLeft } from 'lucide-react'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') ?? ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) setError('Invalid or missing reset token. Please request a new link.')
  }, [token])

  const handleReset = async () => {
    if (!password || password !== confirm) {
      setError(password !== confirm ? 'Passwords do not match.' : 'Enter a new password.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    setLoading(true); setError('')
    try {
      const res = await fetch('/api/v1/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Reset failed. The link may have expired.')
      }
      setDone(true)
      setTimeout(() => navigate('/login'), 3000)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally { setLoading(false) }
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
          <h1 className="text-4xl font-black tracking-tight text-white">New password</h1>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-muted)' }}>
            Choose a strong password for your account.
          </p>
        </div>

        {done ? (
          <div className="flex flex-col items-center gap-4 text-center">
            <CheckCircle size={48} style={{ color: 'var(--accent-gold)' }} />
            <p className="text-white font-semibold">Password updated!</p>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              Redirecting you to sign in…
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="relative">
              <input
                type={showPw ? 'text' : 'password'}
                autoFocus
                placeholder="New password (min 8 characters)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
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

            <input
              type={showPw ? 'text' : 'password'}
              placeholder="Confirm new password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleReset()}
              className="w-full px-5 py-4 rounded-xl text-base outline-none"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            />

            {error && (
              <p className="text-sm px-1" style={{ color: 'var(--accent-red)' }}>{error}</p>
            )}

            <button
              onClick={handleReset}
              disabled={loading || !password || !confirm || !token}
              className="flex items-center justify-center gap-2 py-4 rounded-xl font-bold text-base disabled:opacity-40 transition-opacity"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : null}
              Set New Password
            </button>

            <Link
              to="/login"
              className="flex items-center justify-center gap-2 text-sm font-medium hover:underline mt-1"
              style={{ color: 'var(--text-muted)' }}
            >
              <ArrowLeft size={14} /> Back to Sign In
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}

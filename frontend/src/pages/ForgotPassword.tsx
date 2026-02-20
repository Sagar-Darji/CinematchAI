import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, ArrowLeft, CheckCircle } from 'lucide-react'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async () => {
    if (!email.trim()) return
    setLoading(true); setError('')
    try {
      const res = await fetch('/api/v1/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Something went wrong.')
      }
      setSent(true)
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
          <h1 className="text-4xl font-black tracking-tight text-white">Forgot password?</h1>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-muted)' }}>
            Enter your email and we'll send you a reset link.
          </p>
        </div>

        {sent ? (
          <div className="flex flex-col items-center gap-4 text-center">
            <CheckCircle size={48} style={{ color: 'var(--accent-gold)' }} />
            <p className="text-white font-semibold">Check your inbox</p>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              If <strong>{email}</strong> is registered, a reset link is on its way.
            </p>
            <Link
              to="/login"
              className="flex items-center gap-2 text-sm font-medium hover:underline mt-2"
              style={{ color: 'var(--accent-gold)' }}
            >
              <ArrowLeft size={14} /> Back to Sign In
            </Link>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <input
              type="email"
              autoFocus
              placeholder="Your email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              className="w-full px-5 py-4 rounded-xl text-base outline-none"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            />

            {error && (
              <p className="text-sm px-1" style={{ color: 'var(--accent-red)' }}>{error}</p>
            )}

            <button
              onClick={handleSubmit}
              disabled={loading || !email.trim()}
              className="flex items-center justify-center gap-2 py-4 rounded-xl font-bold text-base disabled:opacity-40 transition-opacity"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : null}
              Send Reset Link
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

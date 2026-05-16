/**
 * Settings page — collected user actions outside the main rating /
 * browsing flow. Currently:
 *   - Import from Letterboxd ZIP (full ZIP support, replaces the old
 *     Profile-page modal)
 *   - Regenerate analytics (manual recompute trigger)
 *
 * Auth-protected via the Route wrapper in App.tsx.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, Sparkles, Upload } from 'lucide-react'
import { useUserStore } from '@/store/useUserStore'
import { recomputeProfile } from '@/lib/api'

export default function Settings() {
  return (
    <div className="min-h-screen px-4 sm:px-6 md:px-8 pb-16">
      <div className="max-w-3xl mx-auto pt-4 md:pt-6 space-y-6">
        <header className="space-y-2">
          <h1 className="text-2xl md:text-3xl font-bold text-white">Settings</h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Manage imports, analytics, and account preferences.
          </p>
        </header>

        <ImportCard />
        <RegenerateCard />
      </div>
    </div>
  )
}

function ImportCard() {
  return (
    <section
      className="rounded-2xl p-5 md:p-6 flex flex-col gap-3"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2">
        <Upload size={16} style={{ color: 'var(--accent-gold)' }} />
        <h2 className="text-base font-bold text-white">Import from Letterboxd</h2>
      </div>
      <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
        Upload your Letterboxd export ZIP and CinematchAI ingests ratings,
        real watch dates (from diary.csv), reviews, watchlist, and likes
        in one pass.
      </p>
      <Link
        to="/settings/import"
        className="inline-block self-start mt-1 px-4 py-2 rounded-xl text-sm font-bold"
        style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}
      >
        Open importer
      </Link>
    </section>
  )
}

function RegenerateCard() {
  const userId = useUserStore((s) => s.userId)
  const [submitting, setSubmitting] = useState(false)
  const [status, setStatus] = useState<'idle' | 'queued' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)

  const trigger = async () => {
    if (!userId) return
    setSubmitting(true)
    setStatus('idle')
    setMessage(null)
    try {
      await recomputeProfile(userId)
      setStatus('queued')
      setMessage('Recompute scheduled. Your Profile updates in ~30 seconds.')
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof Error ? err.message : 'Could not queue recompute.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section
      className="rounded-2xl p-5 md:p-6 flex flex-col gap-3"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2">
        <Sparkles size={16} style={{ color: 'var(--accent-gold)' }} />
        <h2 className="text-base font-bold text-white">Regenerate analytics</h2>
      </div>
      <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
        Recompute your top genres, decades, insights, and the layered
        taste-as-personality essay from your full library. Triggered
        automatically after a Letterboxd import — use this if you've
        rated a chunk of films manually and want the numbers refreshed.
      </p>
      <button
        type="button"
        onClick={trigger}
        disabled={submitting || !userId}
        className="inline-flex items-center gap-2 self-start mt-1 px-4 py-2 rounded-xl text-sm font-bold disabled:opacity-40"
        style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
      >
        {submitting && <Loader2 size={14} className="animate-spin" />}
        Regenerate now
      </button>
      {message && (
        <p
          className="text-sm"
          style={{ color: status === 'error' ? 'var(--accent-red)' : 'var(--accent-gold)' }}
        >
          {message}
        </p>
      )}
    </section>
  )
}

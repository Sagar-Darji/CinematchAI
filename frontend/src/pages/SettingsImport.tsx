/**
 * Letterboxd import page.
 *
 * Lives at /settings/import. Replaces the old in-Profile modal. Same
 * UX as before -- pick a ZIP (or bare CSV), see progress, see the
 * 'Import complete' confirmation -- but the page owns the flow now,
 * which keeps Profile.tsx focused on display and lets future import
 * sources (Trakt, IMDb) plug into the same surface.
 */
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Check, Loader2, Upload } from 'lucide-react'
import { useUserStore } from '@/store/useUserStore'
import { importLetterboxd, pollImportJob } from '@/lib/api'

type Phase = 'idle' | 'importing' | 'done' | 'error'

export default function SettingsImport() {
  const navigate = useNavigate()
  const userId = useUserStore((s) => s.userId)
  const setRatingCount = useUserStore((s) => s.setRatingCount)

  const [pickedFile, setPickedFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [progress, setProgress] = useState(0)
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string>('')

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    setPickedFile(f)
  }

  const start = async () => {
    if (!pickedFile) {
      setError('Pick your Letterboxd .zip (or ratings.csv) first.')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      const result = await importLetterboxd(userId, pickedFile)
      setJobId(result.job_id)
      setTotal(result.total_movies)
      setPhase('importing')
    } catch (err) {
      // Surface backend detail when present.
      let msg = 'Could not start the import.'
      if (err instanceof Error && err.message) {
        const raw = err.message.trim()
        try {
          const parsed = JSON.parse(raw)
          if (parsed?.detail) msg = String(parsed.detail)
          else if (parsed?.error) msg = String(parsed.error)
          else msg = raw.slice(0, 300)
        } catch {
          msg = raw.slice(0, 300)
        }
      }
      setError(msg)
      setPhase('error')
    } finally {
      setSubmitting(false)
    }
  }

  // ── Polling with exponential backoff (matches the prior Profile UX) ──
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (phase !== 'importing' || !jobId) return
    const BACKOFF_MS = [2000, 3000, 5000, 8000, 12000]
    const MAX_ERRORS = 5
    let cancelled = false
    let consecutiveErrors = 0

    const tick = async () => {
      if (cancelled) return
      try {
        const data = await pollImportJob(jobId)
        if (cancelled) return
        consecutiveErrors = 0
        setProgress(data.progress ?? 0)
        if (data.status === 'completed') {
          setPhase('done')
          // Bump the live rating count optimistically — the precomputed
          // analytics blob will catch up on the next render.
          setRatingCount(total)
          return
        }
        if (data.status === 'failed') {
          setPhase('error')
          setError('Import failed. Please try again.')
          return
        }
      } catch {
        consecutiveErrors += 1
        if (consecutiveErrors >= MAX_ERRORS) {
          setPhase('error')
          setError('Lost connection to import job. Refresh to keep watching progress.')
          return
        }
      }
      const delay = consecutiveErrors === 0
        ? BACKOFF_MS[0]
        : BACKOFF_MS[Math.min(consecutiveErrors, BACKOFF_MS.length - 1)]
      pollTimer.current = setTimeout(tick, delay)
    }

    pollTimer.current = setTimeout(tick, BACKOFF_MS[0])
    return () => {
      cancelled = true
      if (pollTimer.current) clearTimeout(pollTimer.current)
    }
  }, [phase, jobId, total, setRatingCount])

  return (
    <div className="min-h-screen px-4 sm:px-6 md:px-8 pb-16">
      <div className="max-w-2xl mx-auto pt-4 md:pt-6 space-y-6">
        <Link
          to="/settings"
          className="inline-flex items-center gap-2 text-sm"
          style={{ color: 'var(--text-muted)' }}
        >
          <ArrowLeft size={14} /> Back to Settings
        </Link>

        <header className="space-y-2">
          <h1 className="text-2xl md:text-3xl font-bold text-white">Import from Letterboxd</h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Upload the entire Letterboxd export ZIP — we pull ratings, real
            watch dates (from diary.csv), reviews, watchlist, and likes.
          </p>
        </header>

        {/* ── Phase: idle or error (idle UI with error banner) ────── */}
        {(phase === 'idle' || phase === 'error') && (
          <section
            className="rounded-2xl p-5 md:p-6 space-y-4"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            <div
              className="rounded-xl p-4 text-sm"
              style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)' }}
            >
              <p className="font-semibold text-white mb-2">How to export from Letterboxd:</p>
              <ol className="space-y-1" style={{ color: 'var(--text-muted)' }}>
                <li>1. letterboxd.com → Settings → Import &amp; Export</li>
                <li>2. <strong className="text-white">Export Your Data</strong></li>
                <li>3. Upload the downloaded <code className="text-yellow-400">.zip</code> below</li>
              </ol>
            </div>

            <label
              className="flex flex-col items-center justify-center gap-3 rounded-xl p-6 cursor-pointer transition-colors"
              style={{ border: `2px dashed ${pickedFile ? 'var(--accent-gold)' : 'var(--border)'}`, background: 'var(--bg-overlay)' }}
            >
              <Upload size={28} style={{ color: pickedFile ? 'var(--accent-gold)' : 'var(--text-muted)' }} />
              <span className="text-sm font-medium" style={{ color: pickedFile ? 'var(--accent-gold)' : 'var(--text-muted)' }}>
                {pickedFile ? `${pickedFile.name} ✓ — ready to import` : 'Click to select your Letterboxd .zip (or ratings.csv)'}
              </span>
              <input type="file" accept=".zip,.csv" onChange={onFile} className="hidden" />
            </label>

            {error && (
              <p className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</p>
            )}

            <button
              type="button"
              onClick={start}
              disabled={submitting || !pickedFile}
              className="w-full py-3 rounded-xl font-bold flex items-center justify-center gap-2 disabled:opacity-40"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
            >
              {submitting ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
              Start import
            </button>
          </section>
        )}

        {/* ── Phase: importing ─────────────────────────────────────── */}
        {phase === 'importing' && (
          <section
            className="rounded-2xl p-6 text-center space-y-5"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            <Loader2 size={40} className="animate-spin mx-auto" style={{ color: 'var(--accent-gold)' }} />
            <div>
              <p className="text-white font-bold">Importing your library…</p>
              <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
                {total > 0 ? `${total} films queued. Safe to leave this page — the import keeps running.` : 'Reading the export…'}
              </p>
            </div>
            <div
              className="w-full h-2 rounded-full overflow-hidden"
              style={{ background: 'var(--bg-overlay)' }}
            >
              <div
                style={{
                  width: `${Math.max(2, Math.min(100, progress))}%`,
                  height: '100%',
                  background: 'var(--accent-gold)',
                  transition: 'width 250ms ease-out',
                }}
              />
            </div>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{progress}% complete</p>
          </section>
        )}

        {/* ── Phase: done ──────────────────────────────────────────── */}
        {phase === 'done' && (
          <section
            className="rounded-2xl p-6 text-center space-y-4"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            <div
              className="mx-auto flex items-center justify-center"
              style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(245,197,24,0.18)' }}
            >
              <Check size={28} style={{ color: 'var(--accent-gold)' }} />
            </div>
            <div>
              <p className="text-white font-bold">Import complete</p>
              <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
                Your taste profile is being recomputed in the background.
              </p>
            </div>
            <button
              type="button"
              onClick={() => navigate('/profile')}
              className="px-4 py-2 rounded-xl text-sm font-bold"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
            >
              See your Profile
            </button>
          </section>
        )}
      </div>
    </div>
  )
}

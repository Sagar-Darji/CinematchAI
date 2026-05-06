import { useEffect, useState, useRef } from 'react'
import { User, Film, Star, TrendingUp, Upload, Loader2, Check, X } from 'lucide-react'
import { useUserStore } from '@/store/useUserStore'
import { getUserProfile, getAdminProfile, importLetterboxd, pollImportJob, type UserProfile, type AdminProfile } from '@/lib/api'
import { PageLoader } from '@/components/ui/PageLoader'

// ── Skeleton components ────────────────────────────────────────────────────────

function SkeletonProfile() {
  return (
    <div className="space-y-5">
      {/* Identity card skeleton */}
      <div className="rounded-xl p-5 flex items-center gap-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <div className="skeleton w-14 h-14 rounded-full flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="skeleton-text w-32" />
          <div className="skeleton-text w-20" style={{ opacity: 0.6 }} />
        </div>
      </div>

      {/* Stats row skeleton */}
      <div className="grid grid-cols-3 gap-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="rounded-xl p-4 flex flex-col items-center gap-2" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <div className="skeleton w-4 h-4 rounded" />
            <div className="skeleton-text w-10" />
            <div className="skeleton-text w-14" style={{ opacity: 0.5 }} />
          </div>
        ))}
      </div>

      {/* Genre bars skeleton */}
      <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <div className="skeleton-text w-24 mb-5" />
        <div className="space-y-3.5">
          {[90, 70, 55, 45, 35, 25].map((w, i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="skeleton-text w-24 flex-shrink-0" />
              <div className="skeleton flex-1 h-1.5 rounded-full" style={{ opacity: w / 100 }} />
              <div className="skeleton-text w-4 flex-shrink-0" />
            </div>
          ))}
        </div>
      </div>

      {/* Recent ratings skeleton */}
      <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <div className="skeleton-text w-28 mb-5" />
        <div className="space-y-3">
          {[80, 65, 72, 55, 68].map((w, i) => (
            <div key={i} className="flex items-center gap-3 py-1.5">
              <div className="flex-1 space-y-1.5">
                <div className="skeleton-text" style={{ width: `${w}%` }} />
                <div className="skeleton-text w-10" style={{ opacity: 0.5 }} />
              </div>
              <div className="skeleton w-8 h-5 rounded flex-shrink-0" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

// ── Letterboxd Import Panel ────────────────────────────────────────────────────

function LetterboxdImport({ userId, onComplete }: { userId: string; onComplete: (count: number) => void }) {
  const [open, setOpen] = useState(false)
  const [csvContent, setCsvContent] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<'idle' | 'importing' | 'done' | 'error'>('idle')
  const [error, setError] = useState('')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => setCsvContent(ev.target?.result as string)
    reader.readAsText(file)
  }

  const handleStart = async () => {
    if (!csvContent) { setError('Please select your ratings.csv file.'); return }
    setError('')
    setSubmitting(true)
    try {
      const result = await importLetterboxd(userId, csvContent)
      setJobId(result.job_id)
      setTotal(result.total_movies)
      setStatus('importing')
    } catch {
      setError('Failed to start import. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  useEffect(() => {
    if (status !== 'importing' || !jobId) return
    pollRef.current = setInterval(async () => {
      try {
        const data = await pollImportJob(jobId)
        setProgress(data.progress ?? 0)
        if (data.status === 'completed') {
          clearInterval(pollRef.current!)
          setStatus('done')
          onComplete(total)
        } else if (data.status === 'failed') {
          clearInterval(pollRef.current!)
          setStatus('error')
          setError('Import failed. Please try again.')
        }
      } catch {
        clearInterval(pollRef.current!)
        setStatus('error')
        setError('Lost connection to import job.')
      }
    }, 2000)
    return () => clearInterval(pollRef.current!)
  }, [status, jobId, total, onComplete])

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="w-full flex items-center gap-3 rounded-xl p-4 text-left transition-colors hover:opacity-80"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', cursor: 'pointer' }}
      >
        <Upload size={18} style={{ color: 'var(--accent-gold)', flexShrink: 0 }} />
        <div>
          <p className="text-sm font-semibold text-white">Import Letterboxd Ratings</p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>Upload your ratings.csv to enrich your taste profile</p>
        </div>
      </button>
    )
  }

  return (
    <div className="rounded-xl p-5 animate-fade-in" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>Import Letterboxd</h3>
        {status === 'idle' && (
          <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
            <X size={16} />
          </button>
        )}
      </div>

      {status === 'idle' && (
        <div className="space-y-4">
          <div className="rounded-xl p-4 text-sm" style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)' }}>
            <p className="font-semibold text-white mb-2">How to export from Letterboxd:</p>
            <ol className="space-y-1" style={{ color: 'var(--text-muted)' }}>
              <li>1. Go to letterboxd.com → Settings → Import &amp; Export</li>
              <li>2. Click <strong className="text-white">Export Your Data</strong></li>
              <li>3. Download the ZIP, extract <code className="text-yellow-400">ratings.csv</code></li>
              <li>4. Upload that file below</li>
            </ol>
          </div>
          <label
            className="flex flex-col items-center justify-center gap-3 rounded-xl p-6 cursor-pointer transition-colors"
            style={{ border: `2px dashed ${csvContent ? 'var(--accent-gold)' : 'var(--border)'}`, background: 'var(--bg-overlay)' }}
          >
            <Upload size={28} style={{ color: csvContent ? 'var(--accent-gold)' : 'var(--text-muted)' }} />
            <span className="text-sm font-medium" style={{ color: csvContent ? 'var(--accent-gold)' : 'var(--text-muted)' }}>
              {csvContent ? 'CSV loaded ✓ — ready to import' : 'Click to select ratings.csv'}
            </span>
            <input type="file" accept=".csv" onChange={handleFile} className="hidden" />
          </label>
          {error && <p className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</p>}
          <button
            onClick={handleStart}
            disabled={submitting || !csvContent}
            className="w-full py-3 rounded-xl font-bold flex items-center justify-center gap-2 disabled:opacity-40"
            style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
          >
            {submitting ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
            Start Import
          </button>
        </div>
      )}

      {status === 'importing' && (
        <div className="text-center space-y-5 py-4">
          <Loader2 size={40} className="animate-spin mx-auto" style={{ color: 'var(--accent-gold)' }} />
          <div>
            <p className="text-white font-bold">Importing your ratings…</p>
            <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
              {total ? `${Math.round(progress / 100 * total)} / ${total} movies` : `${progress}% complete`}
            </p>
          </div>
          <div className="score-bar-track max-w-xs mx-auto">
            <div className="score-bar-fill" style={{ width: `${progress}%`, background: 'var(--accent-gold)' }} />
          </div>
        </div>
      )}

      {status === 'done' && (
        <div className="text-center py-4 space-y-3">
          <div className="w-12 h-12 rounded-full flex items-center justify-center mx-auto" style={{ background: 'var(--accent-gold)' }}>
            <Check size={22} color="#0a0a0f" />
          </div>
          <p className="text-white font-bold">Import complete!</p>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{total} ratings imported from Letterboxd.</p>
          <button
            onClick={() => setOpen(false)}
            className="text-xs font-semibold px-4 py-2 rounded-lg"
            style={{ background: 'var(--bg-overlay)', color: 'var(--text-muted)', border: '1px solid var(--border)', cursor: 'pointer' }}
          >
            Close
          </button>
        </div>
      )}

      {status === 'error' && (
        <div className="space-y-3">
          <p className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</p>
          <button
            onClick={() => { setStatus('idle'); setJobId(null); setProgress(0) }}
            className="text-xs font-semibold px-4 py-2 rounded-lg"
            style={{ background: 'var(--bg-overlay)', color: 'var(--text-muted)', border: '1px solid var(--border)', cursor: 'pointer' }}
          >
            Try again
          </button>
        </div>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function Profile() {
  const { userId, ratingCount, setRatingCount } = useUserStore()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [admin, setAdmin] = useState<AdminProfile | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!userId) return
    setLoading(true)
    Promise.all([
      getUserProfile(userId),
      getAdminProfile(userId),
    ]).then(([p, a]) => {
      setProfile(p)
      setAdmin(a)
      const total = p?.total_ratings ?? a?.total_ratings
      if (total) setRatingCount(total)
    }).finally(() => setLoading(false))
  }, [userId, setRatingCount])

  const genres = profile?.genres ?? {}
  const topGenres = Object.entries(genres).sort((a, b) => b[1] - a[1]).slice(0, 8)
  const maxCount = topGenres[0]?.[1] ?? 1
  const totalRatings = profile?.total_ratings ?? admin?.total_ratings ?? ratingCount
  const avgRating = admin?.avg_rating_given

  return (
    <div className="p-5 md:p-8 min-h-screen max-w-2xl lg:max-w-4xl">
      <PageLoader visible={loading} />

      <h1 className="text-3xl font-black tracking-tight text-white mb-8">Profile</h1>

      {!userId ? (
        <div className="flex flex-col items-center py-20 text-center gap-4">
          <User size={48} style={{ color: 'var(--text-muted)' }} />
          <p style={{ color: 'var(--text-muted)' }}>Enter a username on the Home page to get started.</p>
        </div>
      ) : loading ? (
        <SkeletonProfile />
      ) : (
        <div className="space-y-5">
          {/* User identity card */}
          <div
            className="rounded-xl p-5 flex items-center gap-5 animate-fade-in"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            <div
              className="w-14 h-14 rounded-full flex items-center justify-center text-xl font-black flex-shrink-0"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}
            >
              {userId[0]?.toUpperCase() ?? '?'}
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-bold text-white">{userId}</h2>
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{totalRatings} ratings</p>
            </div>
            {admin?.profile_status && (
              <span
                className="text-[10px] font-bold px-2 py-1 rounded-full flex-shrink-0"
                style={{
                  background: admin.profile_status === 'active' ? 'rgba(245,197,24,0.15)' : 'var(--bg-overlay)',
                  color: admin.profile_status === 'active' ? 'var(--accent-gold)' : 'var(--text-muted)',
                  border: '1px solid var(--border)',
                }}
              >
                {admin.profile_status}
              </span>
            )}
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { icon: Film, label: 'Ratings', value: totalRatings || '—' },
              { icon: Star, label: 'Avg Rating', value: avgRating ? avgRating.toFixed(1) : '—' },
              { icon: TrendingUp, label: 'Genres', value: Object.keys(genres).length || '—' },
            ].map(({ icon: Icon, label, value }, i) => (
              <div
                key={label}
                className="rounded-xl p-4 flex flex-col items-center gap-1 text-center animate-fade-in"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', animationDelay: `${i * 0.06}s` }}
              >
                <Icon size={16} style={{ color: 'var(--accent-gold)' }} />
                <span className="text-xl font-black text-white">{value}</span>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
              </div>
            ))}
          </div>

          {/* Genre breakdown */}
          {topGenres.length > 0 && (
            <div
              className="rounded-xl p-5 animate-fade-in"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', animationDelay: '0.12s' }}
            >
              <h3 className="text-xs font-bold uppercase tracking-widest mb-4" style={{ color: 'var(--text-muted)' }}>
                Top Genres
              </h3>
              <div className="space-y-2.5">
                {topGenres.map(([genre, count], i) => (
                  <div key={genre} className="flex items-center gap-3">
                    <span className="text-sm text-white font-medium w-28 flex-shrink-0 truncate">{genre}</span>
                    <div className="score-bar-track flex-1">
                      <div
                        className="score-bar-fill"
                        style={{
                          width: `${(count / maxCount) * 100}%`,
                          background: 'var(--accent-gold)',
                          transitionDelay: `${i * 0.05}s`,
                        }}
                      />
                    </div>
                    <span className="text-xs font-bold w-5 text-right flex-shrink-0" style={{ color: 'var(--accent-gold)' }}>
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent ratings */}
          {admin && admin.recent_ratings && admin.recent_ratings.length > 0 && (
            <div
              className="rounded-xl p-5 animate-fade-in"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', animationDelay: '0.18s' }}
            >
              <h3 className="text-xs font-bold uppercase tracking-widest mb-4" style={{ color: 'var(--text-muted)' }}>
                Recent Ratings
              </h3>
              <div className="space-y-2">
                {admin.recent_ratings.slice(0, 15).map((r, i) => (
                  <div key={i} className="flex items-center gap-3 py-1.5 border-b last:border-0" style={{ borderColor: 'var(--border)' }}>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white truncate">{r.title ?? `Movie #${r.movie_id}`}</p>
                      {r.year && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{r.year}</p>}
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <Star size={11} style={{ color: 'var(--accent-gold)' }} />
                      <span className="text-sm font-bold" style={{ color: 'var(--accent-gold)' }}>{r.rating}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Letterboxd import */}
          <LetterboxdImport
            userId={userId}
            onComplete={(count) => setRatingCount(ratingCount + count)}
          />

          {!profile && !admin && (
            <div className="text-sm text-center py-8" style={{ color: 'var(--text-muted)' }}>
              No profile data yet. Rate some movies to build your taste profile.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

import { useEffect, useMemo, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { User, Film, Star, TrendingUp, Upload, Loader2, Check, X, Pencil, PlayCircle, Bookmark, Calendar } from 'lucide-react'
import { useUserStore } from '@/store/useUserStore'
import { useHistoryStore } from '@/store/useHistoryStore'
import { useWatchlistStore } from '@/store/useWatchlistStore'
import { useReviewsStore } from '@/store/useReviewsStore'
import {
  getUserProfile,
  getAdminProfile,
  getFavorites,
  getHeatmap,
  getUserStats,
  recomputeUserStats,
  importLetterboxd,
  pollImportJob,
  type UserProfile,
  type AdminProfile,
  type FavoriteItem,
  type HeatmapData,
  type UserStatsResponse,
} from '@/lib/api'
import { tmdbPoster } from '@/lib/utils'
import { PageLoader } from '@/components/ui/PageLoader'
import { Tabs } from '@/components/profile/Tabs'
import { RatingHistogram } from '@/components/profile/RatingHistogram'
import { Heatmap } from '@/components/profile/Heatmap'
import { YearInReview } from '@/components/profile/YearInReview'
import { FavoritesEditor } from '@/components/profile/FavoritesEditor'
import { RatedGrid } from '@/components/profile/RatedGrid'
import { InsightCards, InsightCardsSkeleton } from '@/components/profile/InsightCards'
import { AvatarUploader } from '@/components/profile/AvatarUploader'
import { TasteSignals, TasteSignalsSkeleton } from '@/components/profile/TasteSignals'
import { PeopleLists, PeopleListsSkeleton } from '@/components/profile/PeopleLists'
import { YearChart, YearChartSkeleton } from '@/components/profile/YearChart'
import {
  ratingHistogram,
  decadeBreakdown,
  filmsThisYear,
  yearInReview,
} from '@/lib/profileStats'

type TabKey = 'overview' | 'diary' | 'films' | 'series' | 'watchlist'

// ── Letterboxd Import Panel (unchanged from previous design) ──────────────────

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
    } catch (err) {
      // Surface whatever the backend told us — usually the actual reason
      // (missing column, malformed CSV, auth, etc.) — instead of a
      // generic "try again" that hides the cause.
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

// ── Skeleton ──────────────────────────────────────────────────────────────────

function SkeletonProfile() {
  return (
    <div className="space-y-5">
      <div className="rounded-xl p-5 flex items-center gap-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <div className="skeleton w-14 h-14 rounded-full flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="skeleton-text w-32" />
          <div className="skeleton-text w-20" style={{ opacity: 0.6 }} />
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="rounded-xl p-4 flex flex-col items-center gap-2" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <div className="skeleton w-4 h-4 rounded" />
            <div className="skeleton-text w-10" />
            <div className="skeleton-text w-14" style={{ opacity: 0.5 }} />
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function FavoritesStrip({ items, onEdit }: { items: FavoriteItem[]; onEdit: () => void }) {
  // Render 4 slots — empty ones are placeholders prompting the user to add.
  const slots: (FavoriteItem | null)[] = [...items]
  while (slots.length < 4) slots.push(null)

  return (
    <div
      className="rounded-xl p-5 animate-fade-in"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Star size={14} style={{ color: 'var(--accent-gold)' }} />
          <h3 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
            Favorites
          </h3>
        </div>
        <button
          onClick={onEdit}
          className="flex items-center gap-1 text-[11px] font-semibold"
          style={{ color: 'var(--accent-gold)', background: 'none', border: 'none', cursor: 'pointer' }}
        >
          <Pencil size={11} /> Edit
        </button>
      </div>
      <div className="grid grid-cols-4 gap-2.5">
        {slots.map((it, idx) => {
          if (!it) {
            return (
              <button
                key={`empty-${idx}`}
                onClick={onEdit}
                className="rounded-lg flex items-center justify-center text-[11px] font-semibold"
                style={{
                  aspectRatio: '2/3',
                  border: '1.5px dashed var(--border)',
                  background: 'transparent',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                }}
              >
                + Add
              </button>
            )
          }
          const poster = tmdbPoster(it.poster_path ?? undefined, 'w300')
          return (
            <Link
              key={`${it.tmdb_id}-${it.media_type}`}
              to={`/title/${it.media_type}/${it.tmdb_id}`}
              className="block rounded-lg overflow-hidden group"
              style={{ aspectRatio: '2/3', border: '1px solid var(--border)', background: 'var(--bg-overlay)', textDecoration: 'none' }}
            >
              {poster ? (
                <img
                  src={poster}
                  alt={it.title}
                  className="w-full h-full object-cover transition-transform group-hover:scale-105"
                  loading="lazy"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-center p-1 text-[10px] font-bold text-white">
                  {it.title}
                </div>
              )}
            </Link>
          )
        })}
      </div>
    </div>
  )
}

function PosterGrid({ items }: { items: { tmdbId: number; mediaType: 'movie' | 'tv'; title: string; posterPath?: string | null; subtitle?: string }[] }) {
  if (items.length === 0) {
    return (
      <p className="text-sm py-6 text-center" style={{ color: 'var(--text-muted)' }}>
        Nothing here yet.
      </p>
    )
  }
  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 gap-3">
      {items.map((it) => {
        const poster = tmdbPoster(it.posterPath ?? undefined, 'w300')
        return (
          <Link
            key={`${it.tmdbId}-${it.mediaType}`}
            to={`/title/${it.mediaType}/${it.tmdbId}`}
            className="block group"
            style={{ textDecoration: 'none' }}
          >
            <div
              className="rounded-lg overflow-hidden mb-1.5"
              style={{ aspectRatio: '2/3', border: '1px solid var(--border)', background: 'var(--bg-overlay)' }}
            >
              {poster ? (
                <img
                  src={poster}
                  alt={it.title}
                  className="w-full h-full object-cover transition-transform group-hover:scale-105"
                  loading="lazy"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-center p-1 text-[10px] font-bold text-white">
                  {it.title}
                </div>
              )}
            </div>
            <p className="text-[11px] font-semibold text-white truncate leading-tight">{it.title}</p>
            {it.subtitle && (
              <p className="text-[10px] truncate leading-tight" style={{ color: 'var(--text-muted)' }}>
                {it.subtitle}
              </p>
            )}
          </Link>
        )
      })}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Profile() {
  const { userId, ratingCount, setRatingCount } = useUserStore()
  const history = useHistoryStore((s) => s.items)
  const clearHistory = useHistoryStore((s) => s.clear)
  const watchlist = useWatchlistStore((s) => s.items)
  const reviewsByKey = useReviewsStore((s) => s.byKey)
  const hydrateReviews = useReviewsStore((s) => s.hydrate)

  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [admin, setAdmin] = useState<AdminProfile | null>(null)
  const [favorites, setFavoritesState] = useState<FavoriteItem[]>([])
  const [heatmap, setHeatmap] = useState<HeatmapData | null>(null)
  const [statsResp, setStatsResp] = useState<UserStatsResponse | null>(null)
  const [regenerating, setRegenerating] = useState(false)
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState<TabKey>('overview')
  const [editingFavs, setEditingFavs] = useState(false)
  const [editingAvatar, setEditingAvatar] = useState(false)

  const currentYear = useMemo(() => new Date().getFullYear(), [])

  useEffect(() => {
    if (!userId) return
    let cancelled = false
    // Fire each fetch independently so the page renders progressively —
    // identity card lands instantly, history is already in the store,
    // favorites and heatmap pop in as they arrive, and the slow stats
    // compute keeps its own skeleton without blocking anything else.
    Promise.resolve().then(() => {
      if (cancelled) return
      setLoading(true)
      let pending = 5
      const done = () => {
        pending -= 1
        if (pending <= 0 && !cancelled) setLoading(false)
      }
      getUserProfile(userId)
        .then((p) => {
          if (cancelled) return
          setProfile(p)
          if (p?.total_ratings) setRatingCount(p.total_ratings)
        })
        .finally(done)
      getAdminProfile(userId)
        .then((a) => {
          if (cancelled) return
          setAdmin(a)
          if (a?.total_ratings) setRatingCount(a.total_ratings)
        })
        .finally(done)
      getFavorites(userId).then((favs) => { if (!cancelled) setFavoritesState(favs) }).finally(done)
      getHeatmap(currentYear).then((h) => { if (!cancelled) setHeatmap(h) }).finally(done)
      getUserStats(userId).then((s) => { if (!cancelled) setStatsResp(s) }).finally(done)
      // Reviews hydrate side-effects into a Zustand store; no setState needed here.
      hydrateReviews(userId)
    })
    return () => { cancelled = true }
  }, [userId, setRatingCount, currentYear, hydrateReviews])

  // Poll stats while a background recompute is running. Stops on success
  // or after a 60s safety cap so we don't poll forever for a stuck job.
  useEffect(() => {
    if (!userId || !statsResp?.computing) return
    let cancelled = false
    const start = Date.now()
    const tick = setInterval(async () => {
      if (cancelled || Date.now() - start > 60_000) {
        clearInterval(tick)
        return
      }
      const fresh = await getUserStats(userId)
      if (cancelled || !fresh) return
      setStatsResp(fresh)
      if (!fresh.computing) {
        clearInterval(tick)
        setRegenerating(false)
      }
    }, 4000)
    return () => { cancelled = true; clearInterval(tick) }
  }, [userId, statsResp?.computing])

  const genres = useMemo(() => profile?.genres ?? {}, [profile])
  const topGenres = useMemo(
    () => Object.entries(genres).sort((a, b) => b[1] - a[1]).slice(0, 8),
    [genres],
  )
  const maxGenreCount = topGenres[0]?.[1] ?? 1

  const ratings = admin?.recent_ratings
  const persistedStats = statsResp?.stats ?? null
  const histogram = useMemo(
    () =>
      persistedStats?.rating_histogram?.length
        ? persistedStats.rating_histogram
        : ratingHistogram(ratings),
    [persistedStats, ratings],
  )
  const decades = useMemo(
    () =>
      persistedStats?.decade_breakdown?.length
        ? persistedStats.decade_breakdown
        : decadeBreakdown(ratings),
    [persistedStats, ratings],
  )
  const yearStats = useMemo(() => yearInReview(ratings, genres, currentYear), [ratings, genres, currentYear])
  const filmsYear = persistedStats
    ? persistedStats.films_this_year
    : filmsThisYear(ratings, currentYear)
  const totalRatingsFromStats = persistedStats
    ? persistedStats.total_films + persistedStats.total_series
    : null
  const totalRatings = totalRatingsFromStats ?? profile?.total_ratings ?? admin?.total_ratings ?? ratingCount
  const avgRating = persistedStats?.avg_rating ?? admin?.avg_rating_given
  const avatarUrl = profile?.avatar_url ?? null

  // Heuristic for the "watch dates missing" banner: a Letterboxd import done
  // before the date-preservation fix landed all share roughly one timestamp.
  // If >50% of recent ratings fall inside a single 24h window AND the user
  // has lots of ratings, surface a re-upload prompt.
  const datesLikelyStale = useMemo(() => {
    if (!ratings || ratings.length < 50) return false
    const stamps = ratings
      .map((r) => (r.timestamp ? new Date(r.timestamp).getTime() : 0))
      .filter((t) => t > 0)
      .sort()
    if (stamps.length < 50) return false
    // Find any 24h window containing >half the timestamps.
    const windowMs = 24 * 60 * 60 * 1000
    let i = 0
    let best = 0
    for (let j = 0; j < stamps.length; j++) {
      while (stamps[j] - stamps[i] > windowMs) i++
      best = Math.max(best, j - i + 1)
    }
    return best / stamps.length > 0.5
  }, [ratings])
  const [staleBannerDismissed, setStaleBannerDismissed] = useState(() => {
    try { return localStorage.getItem('cinematch-stale-dates-dismissed') === '1' } catch { return false }
  })
  const showStaleBanner = datesLikelyStale && !staleBannerDismissed

  const maxDecade = decades.reduce((m, d) => Math.max(m, d.count), 1)

  // Banner backdrop URL — pulled from the user's #1 favorite if available.
  const bannerUrl = favorites[0]?.poster_path
    ? tmdbPoster(favorites[0].poster_path, 'original')
    : null

  return (
    <div className="min-h-screen">
      <PageLoader visible={loading} />

      {!userId ? (
        <div className="p-5 md:p-8 max-w-4xl mx-auto">
          <h1 className="text-3xl font-black tracking-tight text-white mb-8">Profile</h1>
          <div className="flex flex-col items-center py-20 text-center gap-4">
            <User size={48} style={{ color: 'var(--text-muted)' }} />
            <p style={{ color: 'var(--text-muted)' }}>Enter a username on the Home page to get started.</p>
          </div>
        </div>
      ) : (
        <>
          {/* Header banner — taller, more cinematic */}
          <div className="relative" style={{ height: '240px', overflow: 'hidden' }}>
            {bannerUrl ? (
              <>
                <div
                  className="absolute inset-0"
                  style={{
                    backgroundImage: `url(${bannerUrl})`,
                    backgroundSize: 'cover',
                    backgroundPosition: 'center 30%',
                    filter: 'blur(14px) brightness(0.42)',
                    transform: 'scale(1.12)',
                  }}
                />
                <div
                  className="absolute inset-0"
                  style={{
                    background:
                      'linear-gradient(to bottom, rgba(10,10,15,0.2) 0%, rgba(10,10,15,0.5) 55%, var(--bg-primary) 100%)',
                  }}
                />
              </>
            ) : (
              <div className="absolute inset-0" style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #0f0f1a 100%)' }} />
            )}
          </div>

          <div className="p-5 md:p-8 max-w-4xl mx-auto -mt-24 relative">
            {/* No global skeleton — every section below renders progressively
                based on its own slice of state, so the page paints quickly
                and each component swaps from skeleton → real as it arrives. */}
            <div className="space-y-6">
                {/* Identity card — bigger avatar, more breathing room */}
                <div
                  className="rounded-2xl p-5 md:p-6 flex items-center gap-5 animate-fade-in"
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border)',
                    boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                  }}
                >
                  <button
                    onClick={() => setEditingAvatar(true)}
                    aria-label="Edit profile picture"
                    title="Edit profile picture"
                    className="rounded-full flex items-center justify-center font-black flex-shrink-0 overflow-hidden relative group"
                    style={{
                      width: '88px',
                      height: '88px',
                      background: avatarUrl
                        ? 'var(--bg-overlay)'
                        : 'linear-gradient(135deg, var(--accent-gold) 0%, #d4a813 100%)',
                      color: '#0a0a0f',
                      fontSize: '38px',
                      boxShadow: '0 6px 20px rgba(245,197,24,0.32)',
                      border: 'none',
                      cursor: 'pointer',
                      padding: 0,
                    }}
                  >
                    {avatarUrl ? (
                      <img
                        src={avatarUrl}
                        alt=""
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                    ) : (
                      userId[0]?.toUpperCase() ?? '?'
                    )}
                    <span
                      className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-[10px] font-bold uppercase tracking-widest"
                      style={{
                        background: 'rgba(0,0,0,0.55)',
                        color: '#fff',
                      }}
                    >
                      Edit
                    </span>
                  </button>
                  <div className="flex-1 min-w-0">
                    <h1 className="text-2xl md:text-3xl font-black text-white truncate leading-tight tracking-tight">
                      {userId}
                    </h1>
                    <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
                      {(totalRatings || 0).toLocaleString()} {totalRatings === 1 ? 'rating' : 'ratings'}
                      {filmsYear ? ` · ${filmsYear} this year` : ''}
                    </p>
                  </div>
                  {admin?.profile_status && (
                    <span
                      className="hidden sm:inline-flex text-[10px] font-bold px-2.5 py-1 rounded-full flex-shrink-0 uppercase tracking-wider"
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

                {/* Stats row — 4 cards with gold accent on the value */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { icon: Film, label: 'Films', value: totalRatings ? totalRatings.toLocaleString() : '—' },
                    { icon: Calendar, label: `In ${currentYear}`, value: filmsYear ? filmsYear.toLocaleString() : '—' },
                    { icon: Star, label: 'Avg ★', value: avgRating ? avgRating.toFixed(1) : '—' },
                    { icon: TrendingUp, label: 'Genres', value: Object.keys(genres).length ? Object.keys(genres).length.toLocaleString() : '—' },
                  ].map(({ icon: Icon, label, value }, i) => (
                    <div
                      key={label}
                      className="rounded-2xl p-4 flex flex-col items-start gap-1 animate-fade-in"
                      style={{
                        background: 'linear-gradient(180deg, var(--bg-card) 0%, rgba(18,18,26,0.7) 100%)',
                        border: '1px solid var(--border)',
                        animationDelay: `${i * 0.05}s`,
                      }}
                    >
                      <div className="flex items-center gap-1.5">
                        <Icon size={12} style={{ color: 'var(--accent-gold)' }} />
                        <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
                          {label}
                        </span>
                      </div>
                      <span className="text-2xl md:text-3xl font-black text-white leading-none mt-1">
                        {value}
                      </span>
                    </div>
                  ))}
                </div>

                {/* "Watch dates missing" prompt for users whose Letterboxd
                    import happened before we started preserving the Date
                    column. Heuristic-based + dismissable. */}
                {showStaleBanner && (
                  <div
                    className="rounded-2xl p-4 flex items-start gap-3 animate-fade-in"
                    style={{
                      background: 'rgba(245,197,24,0.07)',
                      border: '1px solid rgba(245,197,24,0.28)',
                    }}
                  >
                    <Calendar size={16} style={{ color: 'var(--accent-gold)', flexShrink: 0, marginTop: 2 }} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-white">Watch dates missing</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                        Your imported ratings are dated to the day you uploaded the CSV. Re-upload your
                        Letterboxd <code style={{ color: 'var(--accent-gold)' }}>ratings.csv</code> from
                        the Overview tab to fix yearly stats.
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setStaleBannerDismissed(true)
                        try { localStorage.setItem('cinematch-stale-dates-dismissed', '1') } catch { /* ignore */ }
                      }}
                      aria-label="Dismiss"
                      className="text-xs font-semibold flex-shrink-0"
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        padding: '2px 4px',
                      }}
                    >
                      Dismiss
                    </button>
                  </div>
                )}

                {/* Favorites */}
                <FavoritesStrip items={favorites} onEdit={() => setEditingFavs(true)} />

                {/* Tabs */}
                <Tabs<TabKey>
                  active={tab}
                  onChange={setTab}
                  options={[
                    { value: 'overview', label: 'Overview' },
                    { value: 'diary', label: 'Diary', count: history.length },
                    { value: 'films', label: 'Films' },
                    { value: 'series', label: 'Series' },
                    { value: 'watchlist', label: 'Watchlist', count: watchlist.length },
                  ]}
                />

                {/* Tab content */}
                {tab === 'overview' && (
                  <div className="space-y-5">
                    {/* Cinephile insights — derived from the user's full
                        rated library by the persisted-stats compute job.
                        Show skeleton while the worker is still computing
                        so the page doesn't reflow on arrival. */}
                    {persistedStats ? (
                      <InsightCards
                        stats={persistedStats}
                        regenerating={regenerating || statsResp?.computing}
                        onRegenerate={async () => {
                          if (!userId) return
                          setRegenerating(true)
                          try {
                            await recomputeUserStats(userId)
                            const fresh = await getUserStats(userId)
                            if (fresh) setStatsResp(fresh)
                          } catch {
                            setRegenerating(false)
                          }
                        }}
                      />
                    ) : (
                      <InsightCardsSkeleton />
                    )}

                    {/* Numeric "taste signals" — total runtime, foreign %,
                        generosity vs the TMDB crowd. */}
                    {persistedStats ? (
                      <TasteSignals stats={persistedStats} />
                    ) : (
                      <TasteSignalsSkeleton />
                    )}

                    {/* Top directors + actors derived from the full library. */}
                    {persistedStats ? (
                      <PeopleLists stats={persistedStats} />
                    ) : (
                      <PeopleListsSkeleton />
                    )}

                    <YearInReview stats={yearStats} />

                    {/* Rating histogram */}
                    <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                      <h3 className="text-xs font-bold uppercase tracking-widest mb-4" style={{ color: 'var(--text-muted)' }}>
                        Rating distribution
                      </h3>
                      <RatingHistogram buckets={histogram} />
                    </div>

                    {/* Top genres */}
                    {topGenres.length > 0 && (
                      <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <h3 className="text-xs font-bold uppercase tracking-widest mb-4" style={{ color: 'var(--text-muted)' }}>
                          Top genres
                        </h3>
                        <div className="space-y-2.5">
                          {topGenres.map(([genre, count], i) => (
                            <div key={genre} className="flex items-center gap-3">
                              <span className="text-sm text-white font-medium w-28 flex-shrink-0 truncate">{genre}</span>
                              <div className="score-bar-track flex-1">
                                <div
                                  className="score-bar-fill"
                                  style={{
                                    width: `${(count / maxGenreCount) * 100}%`,
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

                    {/* Decade breakdown */}
                    {decades.length > 0 && (
                      <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <h3 className="text-xs font-bold uppercase tracking-widest mb-4" style={{ color: 'var(--text-muted)' }}>
                          Decades
                        </h3>
                        <div className="flex items-end gap-1.5" style={{ height: '80px' }}>
                          {decades.map((d) => (
                            <div key={d.decade} className="flex-1 flex flex-col items-center gap-1">
                              <span className="text-[10px] font-bold" style={{ color: 'var(--accent-gold)' }}>{d.count}</span>
                              <div
                                className="w-full rounded-t-sm"
                                style={{
                                  height: `${(d.count / maxDecade) * 100}%`,
                                  minHeight: '4px',
                                  background: 'var(--accent-gold)',
                                }}
                              />
                            </div>
                          ))}
                        </div>
                        <div className="flex gap-1.5 mt-1.5">
                          {decades.map((d) => (
                            <div key={d.decade} className="flex-1 text-[10px] font-semibold text-center" style={{ color: 'var(--text-muted)' }}>
                              {d.label}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Letterboxd import (kept on overview as a CTA) */}
                    <LetterboxdImport
                      userId={userId}
                      onComplete={(count) => setRatingCount(ratingCount + count)}
                    />
                  </div>
                )}

                {tab === 'diary' && (
                  <div className="space-y-5">
                    {/* Year-by-year activity chart pulls from the persisted
                        stats so it covers the user's *entire* rated
                        timeline, not just the heatmap's current year. */}
                    {persistedStats ? (
                      <YearChart stats={persistedStats} />
                    ) : (
                      <YearChartSkeleton />
                    )}

                    <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                      <h3 className="text-xs font-bold uppercase tracking-widest mb-4" style={{ color: 'var(--text-muted)' }}>
                        Activity in {heatmap?.year ?? currentYear}
                      </h3>
                      {heatmap ? (
                        <Heatmap counts={heatmap.counts} year={heatmap.year} />
                      ) : (
                        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading heatmap…</p>
                      )}
                    </div>

                    {history.length > 0 ? (
                      <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <PlayCircle size={14} style={{ color: 'var(--accent-gold)' }} />
                            <h3 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
                              Recently watched
                            </h3>
                          </div>
                          <button
                            onClick={() => { if (confirm('Clear your watch history?')) clearHistory() }}
                            className="text-[10px] font-semibold"
                            style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                          >
                            Clear
                          </button>
                        </div>
                        <div className="space-y-2">
                          {history.slice(0, 50).map((h) => {
                            const poster = tmdbPoster(h.posterPath, 'w185')
                            const date = new Date(h.watchedAt)
                            const review = reviewsByKey[`${h.tmdbId}-${h.mediaType}`]
                            const snippet = review?.review_text
                              ? review.review_text.length > 90
                                ? `${review.review_text.slice(0, 90)}…`
                                : review.review_text
                              : null
                            return (
                              <Link
                                key={`${h.tmdbId}-${h.mediaType}`}
                                to={`/title/${h.mediaType}/${h.tmdbId}`}
                                className="flex items-start gap-3 p-2 rounded-lg"
                                style={{ background: 'transparent', textDecoration: 'none' }}
                              >
                                <div className="w-10 flex-shrink-0 rounded overflow-hidden" style={{ aspectRatio: '2/3', background: 'var(--bg-overlay)' }}>
                                  {poster ? (
                                    <img src={poster} alt="" className="w-full h-full object-cover" loading="lazy" />
                                  ) : null}
                                </div>
                                <div className="flex-1 min-w-0 py-0.5">
                                  <div className="flex items-center gap-2">
                                    <p className="text-sm font-semibold text-white truncate">{h.title}</p>
                                    {review?.rating != null && (
                                      <span className="flex items-center gap-0.5 flex-shrink-0">
                                        <Star size={10} fill="currentColor" style={{ color: 'var(--accent-gold)' }} />
                                        <span className="text-[11px] font-bold" style={{ color: 'var(--accent-gold)' }}>
                                          {review.rating.toFixed(1)}
                                        </span>
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                                    {date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                                    {h.mediaType === 'tv' && h.lastSeason && h.lastEpisode
                                      ? ` · S${h.lastSeason} · E${h.lastEpisode}`
                                      : ''}
                                  </p>
                                  {snippet && (
                                    <p className="text-[11px] italic mt-0.5 line-clamp-2" style={{ color: 'var(--text-muted)' }}>
                                      “{snippet}”
                                    </p>
                                  )}
                                </div>
                              </Link>
                            )
                          })}
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-xl p-8 text-center" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                          Nothing watched yet. Start a film or series and it'll show up here.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {tab === 'films' && (
                  <RatedGrid userId={userId} mediaType="movie" />
                )}

                {tab === 'series' && (
                  <RatedGrid userId={userId} mediaType="tv" />
                )}

                {tab === 'watchlist' && (
                  <div className="space-y-3">
                    {watchlist.length > 0 ? (
                      <>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Bookmark size={14} style={{ color: 'var(--accent-gold)' }} />
                            <h3 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
                              Watchlist · {watchlist.length}
                            </h3>
                          </div>
                          <Link to="/watchlist" className="text-[11px] font-semibold" style={{ color: 'var(--accent-gold)', textDecoration: 'none' }}>
                            Open full page →
                          </Link>
                        </div>
                        <PosterGrid
                          items={watchlist.map((w) => ({
                            tmdbId: w.tmdbId,
                            mediaType: w.mediaType,
                            title: w.title,
                            posterPath: w.posterPath,
                            subtitle: w.year ? String(w.year) : undefined,
                          }))}
                        />
                      </>
                    ) : (
                      <div className="rounded-xl p-8 text-center" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                          Watchlist is empty. Bookmark films from the discovery feed to save them here.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {!profile && !admin && (
                  <div className="text-sm text-center py-8" style={{ color: 'var(--text-muted)' }}>
                    No profile data yet. Rate some movies to build your taste profile.
                  </div>
                )}
              </div>
          </div>

          {editingFavs && (
            <FavoritesEditor
              userId={userId}
              initial={favorites}
              onClose={() => setEditingFavs(false)}
              onSaved={(items) => setFavoritesState(items)}
            />
          )}

          {editingAvatar && (
            <AvatarUploader
              userId={userId}
              currentUrl={avatarUrl}
              onClose={() => setEditingAvatar(false)}
              onSaved={(url) => {
                // Patch the local profile so the avatar updates immediately
                // without waiting for the next /users/{id} fetch.
                setProfile((p) => (p ? { ...p, avatar_url: url } : p))
              }}
            />
          )}
        </>
      )}
    </div>
  )
}

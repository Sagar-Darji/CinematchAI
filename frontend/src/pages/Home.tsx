import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Sparkles, UserPlus } from 'lucide-react'
import { useUserStore } from '@/store/useUserStore'
import { useHistoryStore } from '@/store/useHistoryStore'
import { getTrending, getNowPlaying, getOttReleases, type Movie } from '@/lib/api'
import { Hero } from '@/components/home/Hero'
import { Rail } from '@/components/home/Rail'

const API_URL = import.meta.env.VITE_API_URL || ''

// Module-level rail cache (5 min TTL) — survives page navigation in-session
const CACHE_TTL = 5 * 60 * 1000
type CacheEntry = { data: Movie[]; timestamp: number }
const railCache = new Map<string, CacheEntry>()

function cacheGet(key: string): Movie[] | null {
  const e = railCache.get(key)
  if (!e) return null
  if (Date.now() - e.timestamp > CACHE_TTL) {
    railCache.delete(key)
    return null
  }
  return e.data
}

function cacheSet(key: string, data: Movie[]) {
  railCache.set(key, { data, timestamp: Date.now() })
}

interface RailState {
  trending: Movie[]
  trendingHi: Movie[]
  nowPlaying: Movie[]
  ottReleases: Movie[]
}

export default function Home() {
  const { userId, isOnboarded } = useUserStore()
  const [movieCount, setMovieCount] = useState<number | null>(null)

  const [rails, setRails] = useState<RailState>({
    trending: [],
    trendingHi: [],
    nowPlaying: [],
    ottReleases: [],
  })
  const [loading, setLoading] = useState({
    trending: true,
    trendingHi: true,
    nowPlaying: true,
    ottReleases: true,
  })

  useEffect(() => {
    fetch(`${API_URL}/api/v1/health`)
      .then((r) => r.json())
      .then((d) => {
        if (d?.details?.movie_count) setMovieCount(d.details.movie_count)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!userId || !isOnboarded) return

    const loaders: { key: keyof RailState; loader: () => Promise<Movie[]> }[] = [
      { key: 'trending',    loader: () => getTrending(20) },
      { key: 'trendingHi',  loader: () => getTrending(20, 'hi') },
      { key: 'nowPlaying',  loader: () => getNowPlaying() },
      { key: 'ottReleases', loader: () => getOttReleases() },
    ]

    loaders.forEach(({ key, loader }) => {
      const cached = cacheGet(key)
      if (cached) {
        setRails((r) => ({ ...r, [key]: cached }))
        setLoading((l) => ({ ...l, [key]: false }))
        return
      }
      loader()
        .then((data) => {
          cacheSet(key, data)
          setRails((r) => ({ ...r, [key]: data }))
        })
        .catch(() => {})
        .finally(() => setLoading((l) => ({ ...l, [key]: false })))
    })
  }, [userId, isOnboarded])

  // ── Logged-out landing (preserved) ───────────────────────────────────────
  if (!userId || !isOnboarded) {
    return (
      <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
        <section className="flex-1 flex flex-col items-center justify-center px-6 py-20 text-center">
          <p className="text-xs font-bold tracking-[0.3em] uppercase mb-6" style={{ color: 'var(--accent-gold)' }}>
            AI-Powered Cinema Discovery
          </p>
          <h1
            className="text-5xl md:text-7xl font-black leading-none mb-6 tracking-tight"
            style={{ color: 'var(--text-primary)' }}
          >
            Find Your
            <br />
            <span style={{ color: 'var(--accent-gold)' }}>Next Film</span>
          </h1>
          <p
            className="text-lg max-w-lg mb-8"
            style={{ color: 'var(--text-muted)', lineHeight: 1.7 }}
          >
            A multi-agent AI pipeline analyzes your taste, mood, and context to surface
            exactly the right movie — across 20+ languages.
          </p>
          {movieCount && (
            <div
              className="flex items-center gap-2 mb-10 px-4 py-2 rounded-full text-xs font-semibold"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}
            >
              <span style={{ color: 'var(--accent-gold)' }}>🎬</span>
              <span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{movieCount.toLocaleString()}</span>{' '}
                movies indexed
              </span>
            </div>
          )}
          <div className="flex flex-col sm:flex-row justify-center gap-3">
            <Link
              to="/login"
              className="flex items-center justify-center gap-2 px-8 py-4 rounded-xl font-bold text-base hover:opacity-90 transition-opacity"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', textDecoration: 'none' }}
            >
              <UserPlus size={18} /> Sign In
            </Link>
            <Link
              to="/onboarding"
              className="flex items-center justify-center gap-2 px-8 py-4 rounded-xl font-bold text-base hover:opacity-90 transition-opacity border"
              style={{
                background: 'transparent',
                borderColor: 'var(--border)',
                color: 'var(--text-primary)',
                textDecoration: 'none',
              }}
            >
              Create Account
            </Link>
          </div>
        </section>
      </div>
    )
  }

  // ── Logged-in OTT hub ────────────────────────────────────────────────────
  const heroMovies = rails.trending.slice(0, 5)
  const history = useHistoryStore((s) => s.items)
  const continueWatching: Movie[] = history.map((h) => ({
    tmdb_id: h.tmdbId,
    title: h.title,
    year: h.year,
    poster_path: h.posterPath,
    media_type: h.mediaType,
  }))

  return (
    <div className="min-h-screen pb-8" style={{ background: 'var(--bg-primary)' }}>
      <Hero movies={heroMovies} />

      <div className="mt-2">
        {continueWatching.length > 0 && (
          <Rail title="Continue Watching" items={continueWatching} seeAllHref="/profile" />
        )}
        <Rail title="Trending Now" items={rails.trending} loading={loading.trending} seeAllHref="/browse" />
        <Rail title="In Theaters" items={rails.nowPlaying} loading={loading.nowPlaying} seeAllHref="/calendar" />
        <Rail title="Top Picks · Hindi" items={rails.trendingHi} loading={loading.trendingHi} seeAllHref="/browse" />
        <Rail title="New on OTT" items={rails.ottReleases} loading={loading.ottReleases} seeAllHref="/calendar" />

        {/* CTA — push users to AI recs once they've browsed a bit */}
        <div className="px-4 md:px-6 mt-6 mb-4">
          <Link
            to="/recommendations"
            className="flex items-center justify-center gap-3 w-full py-4 rounded-2xl font-bold text-base transition-transform hover:scale-[1.01]"
            style={{
              background:
                'linear-gradient(135deg, rgba(245,197,24,0.15), rgba(229,9,20,0.10))',
              color: 'var(--accent-gold)',
              textDecoration: 'none',
              border: '1px solid var(--border)',
            }}
          >
            <Sparkles size={18} /> Get personalized AI recommendations
          </Link>
        </div>
      </div>
    </div>
  )
}

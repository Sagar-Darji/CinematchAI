import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  Star,
  Calendar,
  Clock,
  PlayCircle,
  ThumbsUp,
  ThumbsDown,
  Bookmark,
  BookmarkCheck,
  ArrowLeft,
} from 'lucide-react'
import {
  getMediaDetails,
  submitFeedback,
  recordInteraction,
  type Movie,
  type MediaType,
} from '@/lib/api'
import { tmdbPoster, scoreColor, formatRuntime } from '@/lib/utils'
import { useUserStore } from '@/store/useUserStore'
import { useWatchlistStore } from '@/store/useWatchlistStore'
import { FullScreenPlayer } from '@/components/ui/MovieCard'
import { PageLoader } from '@/components/ui/PageLoader'

export default function MovieDetail() {
  const { mediaType, tmdbId } = useParams<{ mediaType: string; tmdbId: string }>()
  const navigate = useNavigate()
  const userId = useUserStore((s) => s.userId)
  const has = useWatchlistStore((s) => s.has)
  const toggle = useWatchlistStore((s) => s.toggle)

  const [movie, setMovie] = useState<Movie | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [showPlayer, setShowPlayer] = useState(false)
  const [rated, setRated] = useState<'up' | 'down' | null>(null)

  const mt: MediaType = mediaType === 'tv' ? 'tv' : 'movie'
  const id = parseInt(tmdbId ?? '0', 10)
  const isTv = mt === 'tv'

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    setMovie(null)
    getMediaDetails(id, mt)
      .then((m) => {
        if (cancelled) return
        if (!m) {
          setError(true)
          return
        }
        setMovie(m)
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id, mt])

  const handleRate = async (v: 'up' | 'down') => {
    if (!userId || !id || isTv || !movie) return
    setRated(v)
    await submitFeedback(userId, id, v === 'up' ? 5.0 : 1.0)
    recordInteraction(userId, id, v === 'up' ? 'watched' : 'dismissed')
  }

  const handlePlay = () => {
    if (!userId) {
      navigate(`/login?next=/title/${mt}/${id}`)
      return
    }
    setShowPlayer(true)
    if (!isTv) recordInteraction(userId, id, 'clicked')
  }

  const handleWatchlist = () => {
    if (!movie) return
    if (!userId) {
      navigate(`/login?next=/title/${mt}/${id}`)
      return
    }
    toggle({
      tmdbId: id,
      mediaType: mt,
      title: movie.title,
      posterPath: movie.poster_path,
      year: movie.year,
    })
  }

  if (loading) {
    return (
      <div className="min-h-screen">
        <PageLoader visible={true} />
      </div>
    )
  }

  if (error || !movie) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-6 text-center pt-20">
        <div className="text-5xl mb-4">😕</div>
        <p className="text-base font-bold text-white mb-2">Could not load this title.</p>
        <p className="text-sm mb-5" style={{ color: 'var(--text-muted)' }}>
          The title may have been removed or the API is temporarily unavailable.
        </p>
        <Link
          to="/browse"
          className="px-5 py-2.5 rounded-xl text-sm font-bold"
          style={{ background: 'var(--accent-gold)', color: '#0a0a0f', textDecoration: 'none' }}
        >
          Browse all titles
        </Link>
      </div>
    )
  }

  const backdrop = (movie as Movie & { backdrop_path?: string }).backdrop_path
  const bgUrl = backdrop
    ? `https://image.tmdb.org/t/p/w1280${backdrop}`
    : tmdbPoster(movie.poster_path, 'original')
  const posterImg = tmdbPoster(movie.poster_path, 'w500')
  const inWatchlist = has(id, mt)

  // Use vote_average as a public score proxy (recommendation score isn't available here).
  const score = Math.min((movie.vote_average ?? 5) / 10, 1)
  const pct = Math.round(score * 100)
  const barColor = scoreColor(score)

  return (
    <div className="min-h-screen pb-12" style={{ background: 'var(--bg-primary)' }}>
      {/* Backdrop hero */}
      <section
        className="relative w-full overflow-hidden"
        style={{ minHeight: '320px', height: 'min(50vh, 480px)' }}
      >
        {bgUrl && (
          <div
            aria-hidden
            className="absolute inset-0"
            style={{
              backgroundImage: `url(${bgUrl})`,
              backgroundSize: 'cover',
              backgroundPosition: 'center 25%',
              filter: 'brightness(0.65)',
            }}
          />
        )}
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            background: 'linear-gradient(to top, var(--bg-primary) 0%, rgba(10,10,15,0.55) 50%, transparent 100%)',
          }}
        />

        <button
          onClick={() => navigate(-1)}
          aria-label="Back"
          className="absolute top-4 left-4 z-10 w-9 h-9 flex items-center justify-center rounded-full"
          style={{
            background: 'rgba(0,0,0,0.55)',
            backdropFilter: 'blur(6px)',
            color: '#fff',
            border: '1px solid rgba(255,255,255,0.18)',
            cursor: 'pointer',
          }}
        >
          <ArrowLeft size={18} />
        </button>
      </section>

      {/* Body */}
      <div className="px-5 md:px-10 -mt-20 md:-mt-32 relative">
        <div className="flex flex-col lg:flex-row gap-6 lg:gap-8 items-start max-w-5xl mx-auto">
          {posterImg && (
            <div
              className="rounded-2xl overflow-hidden flex-shrink-0 mx-auto lg:mx-0"
              style={{
                width: 'clamp(160px, 35vw, 240px)',
                boxShadow: '0 24px 60px rgba(0,0,0,0.6)',
                border: '1px solid var(--border)',
              }}
            >
              <img src={posterImg} alt={movie.title} className="w-full h-auto block" />
            </div>
          )}

          <div className="flex-1 min-w-0 mt-2 lg:mt-12 w-full">
            <div className="flex items-baseline gap-2 flex-wrap mb-3">
              <h1 className="text-3xl md:text-4xl font-black text-white leading-tight tracking-tight">
                {movie.title}
              </h1>
              <span
                className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide"
                style={{
                  background: isTv ? 'rgba(91,192,190,0.12)' : 'rgba(245,197,24,0.12)',
                  color: isTv ? '#8be0db' : 'var(--accent-gold)',
                  border: `1px solid ${isTv ? 'rgba(91,192,190,0.3)' : 'rgba(245,197,24,0.22)'}`,
                }}
              >
                {isTv ? 'Series' : 'Movie'}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-3 mb-4 text-xs" style={{ color: 'var(--text-muted)' }}>
              {movie.year && (
                <span className="flex items-center gap-1">
                  <Calendar size={11} />
                  {movie.year}
                </span>
              )}
              {movie.vote_average && (
                <span className="flex items-center gap-1">
                  <Star size={11} style={{ color: 'var(--accent-gold)' }} />
                  {Number(movie.vote_average).toFixed(1)}/10
                </span>
              )}
              {movie.runtime && (
                <span className="flex items-center gap-1">
                  <Clock size={11} />
                  {formatRuntime(movie.runtime)}
                </span>
              )}
              {movie.director && <span>🎬 {movie.director}</span>}
              {movie.creator && <span>📺 {movie.creator}</span>}
              {isTv && movie.season_count && (
                <span>
                  {movie.season_count} {movie.season_count === 1 ? 'season' : 'seasons'}
                </span>
              )}
              {isTv && movie.episode_count && <span>{movie.episode_count} episodes</span>}
            </div>

            {(movie.genres?.length ?? 0) > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-5">
                {movie.genres!.map((g) => (
                  <span key={g} className="genre-pill">{g}</span>
                ))}
              </div>
            )}

            <div className="flex items-center gap-3 mb-5 max-w-md">
              <span className="text-xs" style={{ color: 'var(--text-muted)', minWidth: '60px' }}>Score</span>
              <div className="score-bar-track flex-1">
                <div className="score-bar-fill" style={{ width: `${pct}%`, background: barColor }} />
              </div>
              <span className="text-sm font-black" style={{ color: barColor }}>{pct}%</span>
            </div>

            <div className="flex items-center gap-2.5 flex-wrap mb-6">
              <button
                onClick={handlePlay}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm transition-transform hover:scale-105"
                style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
              >
                <PlayCircle size={16} /> {isTv ? 'Watch Series' : 'Watch Now'}
              </button>
              <button
                onClick={handleWatchlist}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-bold text-sm"
                style={{
                  background: inWatchlist ? 'var(--accent-gold)' : 'var(--bg-overlay)',
                  color: inWatchlist ? '#0a0a0f' : 'var(--text-primary)',
                  border: '1px solid var(--border)',
                  cursor: 'pointer',
                }}
              >
                {inWatchlist ? <BookmarkCheck size={16} /> : <Bookmark size={16} />}
                {inWatchlist ? 'In Watchlist' : 'Watchlist'}
              </button>
              {!isTv && userId && (
                <>
                  <button
                    onClick={() => handleRate('up')}
                    className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-xs font-medium"
                    style={{
                      background: rated === 'up' ? 'var(--accent-gold)' : 'var(--bg-overlay)',
                      color: rated === 'up' ? '#0a0a0f' : 'var(--text-muted)',
                      border: '1px solid var(--border)',
                      cursor: 'pointer',
                    }}
                  >
                    <ThumbsUp size={12} /> Love it
                  </button>
                  <button
                    onClick={() => handleRate('down')}
                    className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-xs font-medium"
                    style={{
                      background: rated === 'down' ? 'var(--accent-red)' : 'var(--bg-overlay)',
                      color: rated === 'down' ? '#fff' : 'var(--text-muted)',
                      border: '1px solid var(--border)',
                      cursor: 'pointer',
                    }}
                  >
                    <ThumbsDown size={12} /> Not for me
                  </button>
                </>
              )}
            </div>

            {!userId && (
              <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
                <Link to={`/login?next=/title/${mt}/${id}`} style={{ color: 'var(--accent-gold)' }}>
                  Sign in
                </Link>{' '}
                to rate, save to watchlist, and watch.
              </p>
            )}

            {movie.overview && (
              <div className="mt-2 max-w-3xl">
                <h3
                  className="text-xs font-bold uppercase tracking-[0.2em] mb-2"
                  style={{ color: 'var(--accent-gold)' }}
                >
                  Overview
                </h3>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                  {movie.overview}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {showPlayer && id > 0 && (
        <FullScreenPlayer
          tmdbId={id}
          title={movie.title}
          mediaType={mt}
          seasons={movie.seasons}
          onClose={() => setShowPlayer(false)}
        />
      )}
    </div>
  )
}

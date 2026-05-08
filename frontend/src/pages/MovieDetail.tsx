import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { createPortal } from 'react-dom'
import {
  Star,
  Calendar,
  Clock,
  PlayCircle,
  Film,
  ThumbsUp,
  ThumbsDown,
  Bookmark,
  BookmarkCheck,
  ArrowLeft,
  Share2,
  X,
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
import { useHistoryStore } from '@/store/useHistoryStore'
import { FullScreenPlayer } from '@/components/ui/MovieCard'
import { PageLoader } from '@/components/ui/PageLoader'
import { Rail } from '@/components/home/Rail'

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
  const [showTrailer, setShowTrailer] = useState(false)
  const [shareToast, setShareToast] = useState<string | null>(null)
  const [rated, setRated] = useState<'up' | 'down' | null>(null)
  const [overviewExpanded, setOverviewExpanded] = useState(false)

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
    if (movie) {
      useHistoryStore.getState().record({
        tmdbId: id,
        mediaType: mt,
        title: movie.title,
        posterPath: movie.poster_path,
        year: movie.year,
      })
    }
    setShowPlayer(true)
    if (!isTv) recordInteraction(userId, id, 'clicked')
  }

  const handleShare = async () => {
    const url = `${window.location.origin}/title/${mt}/${id}`
    const data = {
      title: movie?.title ?? 'CineMatch AI',
      text: movie?.title ? `Watch ${movie.title} on CineMatch AI` : 'CineMatch AI',
      url,
    }
    try {
      // Web Share API on Android Chrome / iOS Safari
      if (typeof navigator !== 'undefined' && navigator.share) {
        await navigator.share(data)
        return
      }
      await navigator.clipboard.writeText(url)
      setShareToast('Link copied to clipboard')
      setTimeout(() => setShareToast(null), 2400)
    } catch {
      // User cancelled — no-op
    }
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
        style={{ minHeight: '200px', height: 'clamp(220px, 38vh, 460px)' }}
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

      {/* Body — side-by-side on every breakpoint to keep above-the-fold tight */}
      <div className="px-4 md:px-10 -mt-12 md:-mt-24 relative">
        <div className="flex gap-3 md:gap-6 items-start max-w-5xl mx-auto">
          {posterImg && (
            <div
              className="rounded-xl md:rounded-2xl overflow-hidden flex-shrink-0"
              style={{
                width: 'clamp(96px, 26vw, 220px)',
                boxShadow: '0 18px 50px rgba(0,0,0,0.6)',
                border: '1px solid var(--border)',
              }}
            >
              <img src={posterImg} alt={movie.title} className="w-full h-auto block" />
            </div>
          )}

          <div className="flex-1 min-w-0 lg:mt-12 w-full">
            <div className="flex items-baseline gap-2 flex-wrap mb-1.5 md:mb-3">
              <h1 className="text-xl md:text-3xl lg:text-4xl font-black text-white leading-[1.1] tracking-tight">
                {movie.title}
              </h1>
              <span
                className="px-1.5 py-0.5 rounded-full text-[9px] md:text-[10px] font-bold uppercase tracking-wide"
                style={{
                  background: isTv ? 'rgba(91,192,190,0.12)' : 'rgba(245,197,24,0.12)',
                  color: isTv ? '#8be0db' : 'var(--accent-gold)',
                  border: `1px solid ${isTv ? 'rgba(91,192,190,0.3)' : 'rgba(245,197,24,0.22)'}`,
                }}
              >
                {isTv ? 'Series' : 'Movie'}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mb-2 md:mb-4 text-[11px] md:text-xs" style={{ color: 'var(--text-muted)' }}>
              {movie.year && (
                <span className="flex items-center gap-1">
                  <Calendar size={10} />
                  {movie.year}
                </span>
              )}
              {movie.vote_average && (
                <span className="flex items-center gap-1">
                  <Star size={10} style={{ color: 'var(--accent-gold)' }} />
                  {Number(movie.vote_average).toFixed(1)}
                </span>
              )}
              {movie.runtime && (
                <span className="flex items-center gap-1">
                  <Clock size={10} />
                  {formatRuntime(movie.runtime)}
                </span>
              )}
              {isTv && movie.season_count && (
                <span>
                  {movie.season_count} {movie.season_count === 1 ? 's' : 'ssn'}.
                </span>
              )}
              {isTv && movie.episode_count && <span>{movie.episode_count} ep.</span>}
              {movie.director && <span className="hidden md:inline">🎬 {movie.director}</span>}
              {movie.creator && <span className="hidden md:inline">📺 {movie.creator}</span>}
            </div>

            {(movie.genres?.length ?? 0) > 0 && (
              <div className="flex flex-wrap gap-1 mb-2 md:mb-4">
                {movie.genres!.slice(0, 4).map((g) => (
                  <span key={g} className="genre-pill">{g}</span>
                ))}
              </div>
            )}

            {/* Action row — primary actions visible above the fold on phone */}
            <div className="flex items-center gap-2 flex-wrap mb-3 md:mb-5">
              <button
                onClick={handlePlay}
                className="flex items-center gap-1.5 px-4 py-2 md:px-5 md:py-2.5 rounded-xl font-bold text-xs md:text-sm transition-transform hover:scale-105"
                style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
              >
                <PlayCircle size={15} /> {isTv ? 'Watch' : 'Watch Now'}
              </button>
              {movie.trailer_key && (
                <button
                  onClick={() => setShowTrailer(true)}
                  aria-label="Play trailer"
                  className="flex items-center gap-1.5 px-3 py-2 md:px-4 md:py-2.5 rounded-xl font-bold text-xs md:text-sm"
                  style={{
                    background: 'var(--bg-overlay)',
                    color: 'var(--text-primary)',
                    border: '1px solid var(--border)',
                    cursor: 'pointer',
                  }}
                >
                  <Film size={15} />
                  <span className="hidden sm:inline">Trailer</span>
                </button>
              )}
              <button
                onClick={handleWatchlist}
                aria-label={inWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
                className="flex items-center gap-1.5 px-3 py-2 md:px-4 md:py-2.5 rounded-xl font-bold text-xs md:text-sm"
                style={{
                  background: inWatchlist ? 'var(--accent-gold)' : 'var(--bg-overlay)',
                  color: inWatchlist ? '#0a0a0f' : 'var(--text-primary)',
                  border: '1px solid var(--border)',
                  cursor: 'pointer',
                }}
              >
                {inWatchlist ? <BookmarkCheck size={15} /> : <Bookmark size={15} />}
                <span className="hidden sm:inline">{inWatchlist ? 'In Watchlist' : 'Watchlist'}</span>
              </button>
              <button
                onClick={handleShare}
                aria-label="Share"
                className="flex items-center justify-center w-9 h-9 md:w-auto md:h-auto md:px-3 md:py-2.5 rounded-xl text-xs font-medium md:gap-1.5"
                style={{
                  background: 'var(--bg-overlay)',
                  color: 'var(--text-muted)',
                  border: '1px solid var(--border)',
                  cursor: 'pointer',
                }}
              >
                <Share2 size={14} />
                <span className="hidden md:inline">Share</span>
              </button>
              {!isTv && userId && (
                <>
                  <button
                    onClick={() => handleRate('up')}
                    aria-label="Love it"
                    className="flex items-center justify-center w-9 h-9 md:w-auto md:h-auto md:px-3 md:py-2.5 rounded-xl text-xs font-medium md:gap-1.5"
                    style={{
                      background: rated === 'up' ? 'var(--accent-gold)' : 'var(--bg-overlay)',
                      color: rated === 'up' ? '#0a0a0f' : 'var(--text-muted)',
                      border: '1px solid var(--border)',
                      cursor: 'pointer',
                    }}
                  >
                    <ThumbsUp size={13} />
                    <span className="hidden md:inline">Love it</span>
                  </button>
                  <button
                    onClick={() => handleRate('down')}
                    aria-label="Not for me"
                    className="flex items-center justify-center w-9 h-9 md:w-auto md:h-auto md:px-3 md:py-2.5 rounded-xl text-xs font-medium md:gap-1.5"
                    style={{
                      background: rated === 'down' ? 'var(--accent-red)' : 'var(--bg-overlay)',
                      color: rated === 'down' ? '#fff' : 'var(--text-muted)',
                      border: '1px solid var(--border)',
                      cursor: 'pointer',
                    }}
                  >
                    <ThumbsDown size={13} />
                    <span className="hidden md:inline">Not for me</span>
                  </button>
                </>
              )}
            </div>

            {/* Score bar on tablet+ — hidden on phone where vertical space is precious */}
            <div className="hidden sm:flex items-center gap-3 mb-4 max-w-md">
              <span className="text-xs" style={{ color: 'var(--text-muted)', minWidth: '50px' }}>Score</span>
              <div className="score-bar-track flex-1">
                <div className="score-bar-fill" style={{ width: `${pct}%`, background: barColor }} />
              </div>
              <span className="text-sm font-black" style={{ color: barColor }}>{pct}%</span>
            </div>

            {!userId && (
              <p className="text-[11px] md:text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
                <Link to={`/login?next=/title/${mt}/${id}`} style={{ color: 'var(--accent-gold)' }}>
                  Sign in
                </Link>{' '}
                to rate, save, and watch.
              </p>
            )}
          </div>
        </div>

        {/* Overview below the fold (collapsed on phone, full on lg+) */}
        {movie.overview && (
          <div className="max-w-5xl mx-auto mt-4 md:mt-6">
            <h3
              className="text-[10px] md:text-xs font-bold uppercase tracking-[0.2em] mb-1.5"
              style={{ color: 'var(--accent-gold)' }}
            >
              Overview
            </h3>
            <p
              className={`text-xs md:text-sm leading-relaxed ${overviewExpanded ? '' : 'line-clamp-3 md:line-clamp-none'}`}
              style={{ color: 'var(--text-muted)' }}
            >
              {movie.overview}
            </p>
            <button
              onClick={() => setOverviewExpanded((v) => !v)}
              className="md:hidden text-[11px] font-semibold mt-1"
              style={{ color: 'var(--accent-gold)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
            >
              {overviewExpanded ? 'Show less' : 'Read more'}
            </button>
          </div>
        )}

        {/* Cast strip */}
        {(movie.cast?.length ?? 0) > 0 && (
          <div className="max-w-5xl mx-auto mt-6">
            <h3
              className="text-[10px] md:text-xs font-bold uppercase tracking-[0.2em] mb-2.5"
              style={{ color: 'var(--accent-gold)' }}
            >
              Cast
            </h3>
            <div className="flex gap-2.5 overflow-x-auto hide-scrollbar pb-1" style={{ scrollSnapType: 'x mandatory' }}>
              {movie.cast!.map((c) => {
                const profile = c.profile_path
                  ? `https://image.tmdb.org/t/p/w185${c.profile_path}`
                  : null
                return (
                  <div
                    key={`${c.name}-${c.order ?? ''}`}
                    className="flex-shrink-0 text-center"
                    style={{ width: '80px', scrollSnapAlign: 'start' }}
                  >
                    <div
                      className="w-16 h-16 mx-auto rounded-full overflow-hidden mb-1.5"
                      style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)' }}
                    >
                      {profile ? (
                        <img
                          src={profile}
                          alt={c.name}
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-[10px] font-bold" style={{ color: 'var(--text-muted)' }}>
                          {c.name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()}
                        </div>
                      )}
                    </div>
                    <p className="text-[11px] font-semibold text-white leading-tight line-clamp-2">{c.name}</p>
                    {c.character && (
                      <p className="text-[10px] leading-tight line-clamp-1" style={{ color: 'var(--text-muted)' }}>
                        {c.character}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* More like this — full-width rail outside the constrained body */}
      {(movie.similar?.length ?? 0) > 0 && (
        <div className="mt-8">
          <Rail
            title="More like this"
            items={movie.similar!.map((s) => ({
              tmdb_id: s.tmdb_id,
              title: s.title,
              year: s.year ?? undefined,
              poster_path: s.poster_path ?? undefined,
              vote_average: s.vote_average ?? undefined,
              media_type: s.media_type,
            }))}
          />
        </div>
      )}

      {showPlayer && id > 0 && (
        <FullScreenPlayer
          tmdbId={id}
          title={movie.title}
          mediaType={mt}
          seasons={movie.seasons}
          onClose={() => setShowPlayer(false)}
        />
      )}

      {/* Trailer modal — YouTube embed */}
      {showTrailer && movie.trailer_key && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          onClick={(e) => { if (e.currentTarget === e.target) setShowTrailer(false) }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            background: 'rgba(0,0,0,0.92)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
        >
          <button
            onClick={() => setShowTrailer(false)}
            aria-label="Close trailer"
            style={{
              position: 'absolute',
              top: 'max(env(safe-area-inset-top, 0px), 1rem)',
              right: '1rem',
              width: 40,
              height: 40,
              borderRadius: '50%',
              background: 'rgba(255,255,255,0.18)',
              border: 'none',
              color: '#fff',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={18} />
          </button>
          <div style={{ width: '100%', maxWidth: 960, aspectRatio: '16/9' }}>
            <iframe
              src={`https://www.youtube.com/embed/${movie.trailer_key}?autoplay=1&rel=0`}
              title={`${movie.title} trailer`}
              style={{ width: '100%', height: '100%', border: 'none', borderRadius: 12 }}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
            />
          </div>
        </div>,
        document.body,
      )}

      {/* Share toast */}
      {shareToast && (
        <div
          role="status"
          style={{
            position: 'fixed',
            bottom: 'calc(env(safe-area-inset-bottom, 0px) + 80px)',
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'var(--bg-card)',
            color: 'var(--text-primary)',
            padding: '10px 16px',
            borderRadius: 999,
            border: '1px solid var(--border)',
            fontSize: 12,
            fontWeight: 600,
            boxShadow: '0 12px 32px rgba(0,0,0,0.5)',
            zIndex: 50,
          }}
        >
          {shareToast}
        </div>
      )}
    </div>
  )
}

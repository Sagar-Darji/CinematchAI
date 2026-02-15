import { useState } from 'react'
import { Star, Calendar, Clock, PlayCircle, ChevronDown, ChevronUp } from 'lucide-react'
import type { Movie, Recommendation } from '@/lib/api'
import { tmdbPoster, scoreColor, formatRuntime, cn } from '@/lib/utils'
import { submitFeedback } from '@/lib/api'
import { useUserStore } from '@/store/useUserStore'

interface MovieCardProps {
  rec: Recommendation
  rank?: number
}

export function MovieCard({ rec, rank }: MovieCardProps) {
  const { movie, score, explanation, is_exploration } = rec
  const [expanded, setExpanded] = useState(false)
  const [showPlayer, setShowPlayer] = useState(false)
  const [rated, setRated] = useState<'up' | 'down' | null>(null)
  const userId = useUserStore((s) => s.userId)

  const poster = tmdbPoster(movie.poster_path, 'w300')
  const pct = Math.round(score * 100)
  const barColor = scoreColor(score)
  const tmdbId = movie.tmdb_id || movie.id

  const handleRate = async (v: 'up' | 'down') => {
    if (!userId || !tmdbId) return
    setRated(v)
    await submitFeedback(userId, tmdbId, v === 'up' ? 5.0 : 1.0)
  }

  return (
    <article
      className="rounded-xl overflow-hidden animate-fade-in"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        animationDelay: `${((rank ?? 1) - 1) * 0.06}s`,
      }}
    >
      <div className="flex gap-0">
        {/* Poster */}
        <div className="relative flex-shrink-0 w-28 md:w-36">
          {poster ? (
            <img
              src={poster}
              alt={movie.title}
              className="w-full h-full object-cover"
              style={{ minHeight: '160px' }}
              loading="lazy"
            />
          ) : (
            <div
              className="w-full flex items-center justify-center text-xs text-center p-2"
              style={{
                minHeight: '160px',
                background: 'linear-gradient(135deg, #1a1a2e, #0f3460)',
                color: 'var(--accent-gold)',
              }}
            >
              {movie.title.slice(0, 30)}
            </div>
          )}
          {rank && (
            <div
              className="absolute top-2 left-2 w-7 h-7 flex items-center justify-center rounded-full text-xs font-bold"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}
            >
              {rank}
            </div>
          )}
          {is_exploration && (
            <div
              className="absolute bottom-2 left-2 text-white text-[10px] font-bold px-2 py-0.5 rounded-full"
              style={{ background: 'var(--accent-red)' }}
            >
              Discovery
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 p-4 flex flex-col gap-2">
          {/* Title + year */}
          <div>
            <h3 className="font-bold text-base leading-tight text-white">{movie.title}</h3>
            <div className="flex items-center gap-3 mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
              {movie.year && (
                <span className="flex items-center gap-1">
                  <Calendar size={11} /> {movie.year}
                </span>
              )}
              {movie.vote_average && (
                <span className="flex items-center gap-1">
                  <Star size={11} style={{ color: 'var(--accent-gold)' }} />
                  {Number(movie.vote_average).toFixed(1)}
                </span>
              )}
              {movie.runtime && (
                <span className="flex items-center gap-1">
                  <Clock size={11} /> {formatRuntime(movie.runtime)}
                </span>
              )}
            </div>
          </div>

          {/* Genres */}
          {(movie.genres?.length ?? 0) > 0 && (
            <div className="flex flex-wrap gap-1">
              {movie.genres!.slice(0, 3).map((g) => (
                <span key={g} className="genre-pill">{g}</span>
              ))}
            </div>
          )}

          {/* Match score bar */}
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs" style={{ color: 'var(--text-muted)', minWidth: '64px' }}>
              Match score
            </span>
            <div className="score-bar-track flex-1">
              <div
                className="score-bar-fill"
                style={{ width: `${pct}%`, background: barColor }}
              />
            </div>
            <span className="text-xs font-bold min-w-[36px]" style={{ color: barColor }}>
              {pct}%
            </span>
          </div>

          {/* Expand toggle */}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 text-xs mt-auto self-start transition-colors"
            style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {expanded ? 'Less' : 'Details & Watch'}
          </button>
        </div>
      </div>

      {/* Expanded section */}
      {expanded && (
        <div
          className="px-4 pb-4 space-y-3 border-t animate-fade-in"
          style={{ borderColor: 'var(--border)' }}
        >
          {/* Overview */}
          {movie.overview && (
            <div className="pt-3">
              <p className="text-sm" style={{ color: 'var(--text-muted)', lineHeight: 1.6 }}>
                {movie.overview}
              </p>
            </div>
          )}

          {/* Director */}
          {movie.director && (
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              <span className="text-white font-medium">Director:</span> {movie.director}
            </p>
          )}

          {/* Explanation */}
          {explanation && (
            <div
              className="rounded-lg px-3 py-2 text-sm"
              style={{ background: 'var(--bg-overlay)', color: 'var(--text-muted)', borderLeft: `3px solid ${barColor}` }}
            >
              <span className="text-white font-medium">Why this? </span>
              {explanation}
            </div>
          )}

          {/* Feedback buttons */}
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Rate this pick:</span>
            <button
              onClick={() => handleRate('up')}
              className={cn(
                'px-3 py-1 rounded-full text-xs font-medium transition-all',
                rated === 'up' ? 'text-white' : 'opacity-60 hover:opacity-100',
              )}
              style={{
                background: rated === 'up' ? 'var(--accent-gold)' : 'var(--bg-overlay)',
                color: rated === 'up' ? '#0a0a0f' : 'var(--text-muted)',
                border: '1px solid var(--border)',
                cursor: 'pointer',
              }}
            >
              👍 Loved it
            </button>
            <button
              onClick={() => handleRate('down')}
              className={cn(
                'px-3 py-1 rounded-full text-xs font-medium transition-all',
                rated === 'down' ? 'text-white' : 'opacity-60 hover:opacity-100',
              )}
              style={{
                background: rated === 'down' ? 'var(--accent-red)' : 'var(--bg-overlay)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border)',
                cursor: 'pointer',
              }}
            >
              👎 Not for me
            </button>
          </div>

          {/* Watch Now */}
          {tmdbId && (
            <div>
              <button
                onClick={() => setShowPlayer((v) => !v)}
                className="flex items-center gap-2 text-sm font-medium transition-colors"
                style={{ color: 'var(--accent-gold)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
              >
                <PlayCircle size={16} />
                {showPlayer ? 'Hide Player' : 'Watch Now'}
              </button>
              {showPlayer && (
                <div className="mt-2 rounded-lg overflow-hidden animate-fade-in">
                  <p className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>
                    Streamed via VidSrc · Ad redirects blocked · Availability varies by region.
                  </p>
                  <iframe
                    src={`https://vidsrc.to/embed/movie/${tmdbId}`}
                    width="100%"
                    height="420"
                    frameBorder="0"
                    referrerPolicy="no-referrer"
                    sandbox="allow-scripts allow-same-origin allow-forms"
                    allow="autoplay; fullscreen"
                    loading="lazy"
                    style={{ borderRadius: '8px' }}
                    title={`Watch ${movie.title}`}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  )
}

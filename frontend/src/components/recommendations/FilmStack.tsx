import { useState, useEffect, useCallback } from 'react'
import type { CSSProperties } from 'react'
import { ChevronLeft, ChevronRight, PlayCircle, ThumbsUp, ThumbsDown, Star, Calendar } from 'lucide-react'
import type { Recommendation } from '@/lib/api'
import { tmdbPoster, scoreColor, cn } from '@/lib/utils'
import { submitFeedback } from '@/lib/api'
import { useUserStore } from '@/store/useUserStore'
import { useHistoryStore } from '@/store/useHistoryStore'
import { FullScreenPlayer } from '@/components/ui/MovieCard'

interface FilmStackProps {
  recs: Recommendation[]
}

// ── Card transform math ────────────────────────────────────────────────────────
function getCardStyle(offset: number): CSSProperties {
  const abs = Math.abs(offset)
  if (abs > 3) return { display: 'none' }

  const sign = offset === 0 ? 0 : offset / abs
  const tx = offset * 38
  const ry = -offset * 32
  const scale = 1 - abs * 0.165
  const opacity = abs === 0 ? 1 : abs === 1 ? 0.68 : abs === 2 ? 0.38 : 0.16
  const tz = -abs * 55

  return {
    position: 'absolute' as const,
    left: '50%',
    top: 0,
    transform: `translateX(calc(-50% + ${tx}%)) rotateY(${ry}deg) scale(${scale}) translateZ(${tz}px)`,
    opacity,
    zIndex: 10 - abs,
    transition: 'transform 0.55s cubic-bezier(0.4,0,0.2,1), opacity 0.45s ease',
    cursor: abs > 0 ? 'pointer' : 'default',
    transformOrigin: sign < 0 ? 'right center' : sign > 0 ? 'left center' : 'center center',
    willChange: 'transform',
  }
}

// ── Single poster card ────────────────────────────────────────────────────────
function PosterCard({
  rec, offset, onClick,
}: {
  rec: Recommendation
  offset: number
  onClick: () => void
}) {
  const poster = tmdbPoster(rec.movie.poster_path, 'w500')
  const pct = Math.round(rec.score * 100)
  const barColor = scoreColor(rec.score)

  return (
    <div data-reduced-motion-flat style={getCardStyle(offset)} onClick={abs(offset) > 0 ? onClick : undefined}>
      <div
        className="relative overflow-hidden rounded-xl"
        style={{
          width: '150px',
          height: '225px',
          boxShadow: offset === 0
            ? '0 28px 70px rgba(0,0,0,0.85), 0 0 0 1px rgba(245,197,24,0.15)'
            : '0 14px 36px rgba(0,0,0,0.6)',
        }}
      >
        {poster
          ? <img src={poster} alt={rec.movie.title} className="w-full h-full object-cover" loading="lazy" />
          : <div className="w-full h-full flex items-center justify-center text-center p-4"
              style={{ background: 'linear-gradient(135deg,#1a1a2e,#0f3460)', color: 'var(--accent-gold)', fontWeight: 700 }}>
              {rec.movie.title}
            </div>
        }

        {/* Rank badge */}
        {offset === 0 && (
          <div
            className="absolute top-2.5 left-2.5 w-7 h-7 flex items-center justify-center rounded-full text-xs font-black"
            style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}
          >
            {rec.rank}
          </div>
        )}

        {/* Match badge */}
        {offset === 0 && (
          <div
            className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full text-[11px] font-black"
            style={{ background: 'rgba(0,0,0,0.75)', color: barColor, border: `1px solid ${barColor}` }}
          >
            {pct}%
          </div>
        )}

        {/* Bottom gradient on adjacent cards */}
        {abs(offset) > 0 && (
          <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.3)' }} />
        )}
      </div>
    </div>
  )
}

function abs(n: number) { return Math.abs(n) }

function FilmInfo({
  rec, onRate, rated,
}: {
  rec: Recommendation
  onRate: (v: 'up' | 'down') => void
  rated: 'up' | 'down' | null
}) {
  const { movie, explanation, is_exploration } = rec
  const barColor = scoreColor(rec.score)
  const pct = Math.round(rec.score * 100)
  const [showPlayer, setShowPlayer] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const tmdbId = movie.tmdb_id || movie.id

  const titleWords = movie.title.split(' ')
  const TRUNCATE = 130
  const shortExplanation = explanation && explanation.length > TRUNCATE
    ? explanation.slice(0, TRUNCATE).trimEnd() + '…'
    : explanation

  return (
    <div className="animate-film-info text-center max-w-lg mx-auto px-4 mt-4">
      {/* Pipeline trace line */}
      <div className="flex items-center justify-center gap-2 mb-3">
        <div className="h-px flex-1 max-w-[60px] animate-trace-line" style={{ background: 'linear-gradient(to right, transparent, var(--accent-gold))', animationDelay: '0.1s' }} />
        <span className="text-[9px] font-bold uppercase tracking-[0.25em] animate-fade-in" style={{ color: 'var(--accent-gold)', animationDelay: '0.3s' }}>
          #{rec.rank} Pick
        </span>
        <div className="h-px flex-1 max-w-[60px] animate-trace-line" style={{ background: 'linear-gradient(to left, transparent, var(--accent-gold))', animationDelay: '0.1s' }} />
      </div>

      {/* Genre / discovery pill */}
      <div className="flex items-center justify-center gap-2 mb-2">
        {is_exploration && (
          <span className="text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full text-white"
            style={{ background: 'var(--accent-red)' }}>Discovery</span>
        )}
        {(movie.genres ?? []).slice(0, 3).map((g) => (
          <span key={g} className="genre-pill">{g}</span>
        ))}
      </div>

      {/* Title */}
      <h2 className="text-xl md:text-2xl font-black text-white leading-tight mb-1 tracking-tight" style={{ perspective: '600px' }}>
        {titleWords.map((word, i) => (
          <span key={i} className="animate-title-word" style={{ animationDelay: `${0.15 + i * 0.08}s` }}>
            {word}{i < titleWords.length - 1 ? '\u00A0' : ''}
          </span>
        ))}
      </h2>

      {/* Meta row */}
      <div className="flex items-center justify-center gap-3 text-xs mb-2 animate-fade-in" style={{ color: 'var(--text-muted)', animationDelay: '0.4s' }}>
        {movie.year && (
          <span className="flex items-center gap-1"><Calendar size={11} />{movie.year}</span>
        )}
        {movie.vote_average && (
          <span className="flex items-center gap-1">
            <Star size={11} style={{ color: 'var(--accent-gold)' }} />
            {Number(movie.vote_average).toFixed(1)}
          </span>
        )}
        <span className="font-bold" style={{ color: barColor }}>{pct}% match</span>
      </div>

      {/* Explanation — truncated with Read more */}
      {explanation && (
        <div className="mb-4 animate-fade-in" style={{ animationDelay: '0.5s' }}>
          <p className="text-sm leading-relaxed mx-auto max-w-sm" style={{ color: 'var(--text-muted)' }}>
            {expanded ? explanation : shortExplanation}
          </p>
          {explanation.length > TRUNCATE && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-xs font-semibold mt-1 transition-opacity hover:opacity-80"
              style={{ color: 'var(--accent-gold)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
            >
              {expanded ? 'Show less' : 'Read more'}
            </button>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-center gap-3 flex-wrap">
        {tmdbId && (
          <button
            onClick={() => {
              useHistoryStore.getState().record({
                tmdbId,
                mediaType: 'movie',
                title: movie.title,
                posterPath: movie.poster_path,
                year: movie.year,
              })
              setShowPlayer(true)
            }}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-bold transition-all hover:scale-105"
            style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
          >
            <PlayCircle size={14} /> Watch Now
          </button>
        )}
        <button
          onClick={() => onRate('up')}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-medium transition-all hover:scale-105"
          style={{
            background: rated === 'up' ? 'var(--accent-gold)' : 'var(--bg-overlay)',
            color: rated === 'up' ? '#0a0a0f' : 'var(--text-muted)',
            border: '1px solid var(--border)', cursor: 'pointer',
          }}
        >
          <ThumbsUp size={13} /> Love it
        </button>
        <button
          onClick={() => onRate('down')}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-medium transition-all hover:scale-105"
          style={{
            background: rated === 'down' ? 'var(--accent-red)' : 'var(--bg-overlay)',
            color: rated === 'down' ? '#fff' : 'var(--text-muted)',
            border: '1px solid var(--border)', cursor: 'pointer',
          }}
        >
          <ThumbsDown size={13} /> Pass
        </button>
      </div>

      {/* Full-screen player overlay */}
      {showPlayer && tmdbId && (
        <FullScreenPlayer tmdbId={tmdbId} title={movie.title} mediaType="movie" onClose={() => setShowPlayer(false)} />
      )}
    </div>
  )
}

// ── Main FilmStack ────────────────────────────────────────────────────────────
export function FilmStack({ recs }: FilmStackProps) {
  const [current, setCurrent] = useState(0)
  const [rated, setRated] = useState<Record<number, 'up' | 'down'>>({})
  const userId = useUserStore((s) => s.userId)

  const go = useCallback((dir: 'prev' | 'next') => {
    setCurrent((c) => {
      if (dir === 'next') return Math.min(c + 1, recs.length - 1)
      return Math.max(c - 1, 0)
    })
  }, [recs.length])

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') go('next')
      if (e.key === 'ArrowLeft') go('prev')
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [go])

  const handleRate = async (v: 'up' | 'down') => {
    const rec = recs[current]
    const tmdbId = rec.movie.tmdb_id || rec.movie.id
    if (!userId || !tmdbId) return
    setRated((r) => ({ ...r, [current]: v }))
    await submitFeedback(userId, tmdbId, v === 'up' ? 5.0 : 1.0)
  }

  const canPrev = current > 0
  const canNext = current < recs.length - 1

  return (
    <div className="select-none">
      {/* 3D stack viewport */}
      <div
        className="relative mx-auto"
        style={{
          perspective: '1200px',
          perspectiveOrigin: '50% 40%',
          height: '245px',
          maxWidth: '800px',
        }}
      >
        {recs.map((rec, i) => (
          <PosterCard
            key={rec.movie.tmdb_id ?? i}
            rec={rec}
            offset={i - current}
            onClick={() => setCurrent(i)}
          />
        ))}
      </div>

      {/* Nav + dots */}
      <div className="flex items-center justify-center gap-5 mt-6">
        <button
          onClick={() => go('prev')}
          disabled={!canPrev}
          className="w-10 h-10 flex items-center justify-center rounded-full transition-all hover:scale-110 disabled:opacity-25"
          style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'var(--text-muted)', cursor: canPrev ? 'pointer' : 'default' }}
        >
          <ChevronLeft size={18} />
        </button>

        {/* Dot navigation */}
        <div className="flex items-center gap-1.5">
          {recs.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrent(i)}
              className="rounded-full transition-all"
              style={{
                width: i === current ? '20px' : '6px',
                height: '6px',
                background: i === current ? 'var(--accent-gold)' : 'var(--border-hover)',
                border: 'none',
                cursor: 'pointer',
              }}
            />
          ))}
        </div>

        <button
          onClick={() => go('next')}
          disabled={!canNext}
          className="w-10 h-10 flex items-center justify-center rounded-full transition-all hover:scale-110 disabled:opacity-25"
          style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'var(--text-muted)', cursor: canNext ? 'pointer' : 'default' }}
        >
          <ChevronRight size={18} />
        </button>
      </div>

      {/* Info panel — keyed to current to re-trigger animation */}
      <FilmInfo
        key={current}
        rec={recs[current]}
        onRate={handleRate}
        rated={rated[current] ?? null}
      />

      {/* Keyboard hint */}
      <p className="text-center text-[11px] mt-6" style={{ color: 'var(--text-muted)', opacity: 0.5 }}>
        ← → to navigate · {current + 1} of {recs.length}
      </p>
    </div>
  )
}

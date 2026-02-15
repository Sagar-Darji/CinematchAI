import { useState, useEffect, useCallback } from 'react'
import type { CSSProperties } from 'react'
import { ChevronLeft, ChevronRight, PlayCircle, ThumbsUp, ThumbsDown, Star, Calendar } from 'lucide-react'
import type { Recommendation } from '@/lib/api'
import { tmdbPoster, scoreColor, cn } from '@/lib/utils'
import { submitFeedback } from '@/lib/api'
import { useUserStore } from '@/store/useUserStore'

interface FilmStackProps {
  recs: Recommendation[]
}

// ── Card transform math ────────────────────────────────────────────────────────
function getCardStyle(offset: number): CSSProperties {
  const abs = Math.abs(offset)
  if (abs > 3) return { display: 'none' }

  const sign = offset === 0 ? 0 : offset / abs
  // translateX: spread cards sideways
  const tx = offset * 42  // % of container
  // rotateY: near cards show their spine
  const ry = -offset * 36  // degrees
  // scale: far cards shrink
  const scale = 1 - abs * 0.165
  // opacity: far cards fade
  const opacity = abs === 0 ? 1 : abs === 1 ? 0.68 : abs === 2 ? 0.38 : 0.16
  // z-depth: far cards recede
  const tz = -abs * 60

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
    <div style={getCardStyle(offset)} onClick={abs(offset) > 0 ? onClick : undefined}>
      <div
        className="relative overflow-hidden rounded-xl"
        style={{
          width: '200px',
          height: '300px',
          boxShadow: offset === 0
            ? '0 32px 80px rgba(0,0,0,0.85), 0 0 0 1px rgba(245,197,24,0.15)'
            : '0 16px 40px rgba(0,0,0,0.6)',
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

// ── Info panel ────────────────────────────────────────────────────────────────
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
  const tmdbId = movie.tmdb_id || movie.id

  return (
    <div className="animate-film-info text-center max-w-lg mx-auto px-4 mt-8">
      {/* Genre / discovery pill */}
      <div className="flex items-center justify-center gap-2 mb-3">
        {is_exploration && (
          <span className="text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full text-white"
            style={{ background: 'var(--accent-red)' }}>Discovery</span>
        )}
        {(movie.genres ?? []).slice(0, 3).map((g) => (
          <span key={g} className="genre-pill">{g}</span>
        ))}
      </div>

      {/* Title */}
      <h2 className="text-2xl md:text-3xl font-black text-white leading-tight mb-1.5 tracking-tight">
        {movie.title}
      </h2>

      {/* Meta row */}
      <div className="flex items-center justify-center gap-3 text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
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

      {/* Explanation */}
      {explanation && (
        <p className="text-sm mb-5 leading-relaxed mx-auto max-w-sm" style={{ color: 'var(--text-muted)' }}>
          {explanation}
        </p>
      )}

      {/* Actions */}
      <div className="flex items-center justify-center gap-3 flex-wrap">
        {tmdbId && (
          <button
            onClick={() => setShowPlayer((v) => !v)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-bold transition-all hover:scale-105"
            style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
          >
            <PlayCircle size={14} /> {showPlayer ? 'Hide' : 'Watch Now'}
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

      {/* VidSrc player */}
      {showPlayer && tmdbId && (
        <div className="mt-5 rounded-2xl overflow-hidden animate-fade-in">
          <p className="text-xs mb-2 text-left" style={{ color: 'var(--text-muted)' }}>
            Via VidSrc · availability varies
          </p>
          <iframe
            src={`https://vidsrc.to/embed/movie/${tmdbId}`}
            width="100%" height="340"
            frameBorder="0"
            referrerPolicy="no-referrer"
            sandbox="allow-scripts allow-same-origin allow-forms"
            allow="autoplay; fullscreen"
            loading="lazy"
            style={{ borderRadius: '12px' }}
            title={`Watch ${movie.title}`}
          />
        </div>
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
          height: '320px',
          maxWidth: '860px',
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

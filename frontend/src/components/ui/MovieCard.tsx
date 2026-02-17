import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Star, Calendar, Clock, PlayCircle, X, ThumbsUp, ThumbsDown } from 'lucide-react'
import type { Movie, Recommendation } from '@/lib/api'
import { tmdbPoster, scoreColor, formatRuntime, cn } from '@/lib/utils'
import { submitFeedback, recordInteraction } from '@/lib/api'
import { useUserStore } from '@/store/useUserStore'

// ── Full-screen video player overlay ─────────────────────────────────────────

export function FullScreenPlayer({ tmdbId, title, onClose }: { tmdbId: number | string; title: string; onClose: () => void }) {
  const [mode, setMode] = useState<'movie' | 'tv'>('movie')
  const [adShield, setAdShield] = useState(true)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    // Block popups opened by the iframe
    const origOpen = window.open
    window.open = () => null
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
      window.open = origOpen
    }
  }, [onClose])

  const src = `https://vidsrc.to/embed/${mode}/${tmdbId}`

  return createPortal(
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        zIndex: 99999,
        background: '#000',
      }}
    >
      {/* Top bar: mode toggle + close */}
      <div className="absolute top-0 inset-x-0 z-10 flex items-center justify-between px-4 py-3"
        style={{ background: 'linear-gradient(to bottom, rgba(0,0,0,0.8), transparent)' }}>
        <div className="flex items-center gap-1 rounded-full p-0.5" style={{ background: 'rgba(255,255,255,0.1)' }}>
          {(['movie', 'tv'] as const).map((m) => (
            <button key={m} onClick={() => setMode(m)}
              className="px-3.5 py-1.5 rounded-full text-xs font-bold capitalize"
              style={{
                background: mode === m ? 'var(--accent-gold)' : 'transparent',
                color: mode === m ? '#0a0a0f' : 'rgba(255,255,255,0.6)',
                border: 'none', cursor: 'pointer',
              }}>
              {m === 'tv' ? 'TV Show' : 'Movie'}
            </button>
          ))}
        </div>
        <span className="text-white text-sm font-semibold truncate mx-4 flex-1 text-center opacity-70">{title}</span>
        <button
          onClick={onClose}
          className="w-9 h-9 flex items-center justify-center rounded-full flex-shrink-0"
          style={{ background: 'rgba(255,255,255,0.15)', color: 'white', border: 'none', cursor: 'pointer' }}
        >
          <X size={18} />
        </button>
      </div>

      {/* Ad shield: absorbs the first click (VidSrc ad redirect) then disappears */}
      {adShield && (
        <div
          onClick={() => setAdShield(false)}
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 5,
            cursor: 'pointer',
            background: 'transparent',
          }}
        />
      )}

      <iframe
        key={mode}
        src={src}
        style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
        referrerPolicy="no-referrer"
        allow="autoplay; fullscreen; encrypted-media"
        allowFullScreen
        loading="lazy"
        title={`Watch ${title}`}
      />
    </div>,
    document.body
  )
}

interface MovieCardProps {
  rec: Recommendation
  rank?: number
  compact?: boolean
}

// ── Floating modal ────────────────────────────────────────────────────────────

interface ModalProps {
  rec: Recommendation
  onClose: () => void
}

function MovieModal({ rec, onClose }: ModalProps) {
  const { movie, score, explanation, is_exploration } = rec
  const [showPlayer, setShowPlayer] = useState(false)
  const [rated, setRated] = useState<'up' | 'down' | null>(null)
  const userId = useUserStore((s) => s.userId)
  const overlayRef = useRef<HTMLDivElement>(null)

  const poster = tmdbPoster(movie.poster_path, 'w500')
  const pct = Math.round(score * 100)
  const barColor = scoreColor(score)
  const tmdbId = movie.tmdb_id || movie.id

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
    }
  }, [onClose])

  const handleRate = async (v: 'up' | 'down') => {
    if (!userId || !tmdbId) return
    setRated(v)
    await submitFeedback(userId, tmdbId, v === 'up' ? 5.0 : 1.0)
    // Also record as dismissal signal for the feedback loop
    recordInteraction(userId, tmdbId, v === 'up' ? 'watched' : 'dismissed')
  }

  const modalContent = (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ 
        background: 'rgba(0,0,0,0.85)', 
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)'
      }}
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div
        className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl animate-fade-in shadow-2xl"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border-hover)' }}
      >
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-10 w-8 h-8 flex items-center justify-center rounded-full"
          style={{ background: 'rgba(0,0,0,0.7)', color: 'white', border: 'none', cursor: 'pointer' }}
        >
          <X size={15} />
        </button>

        {/* Poster backdrop header */}
        <div className="relative overflow-hidden rounded-t-2xl" style={{ height: '260px' }}>
          {poster ? (
            <>
              <div
                className="absolute inset-0"
                style={{
                  backgroundImage: `url(${poster})`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center 20%',
                  filter: 'blur(18px) brightness(0.35)',
                  transform: 'scale(1.15)',
                }}
              />
              <div className="relative h-full flex items-center justify-center">
                <img
                  src={poster}
                  alt={movie.title}
                  style={{ height: '200px', borderRadius: '10px', boxShadow: '0 20px 60px rgba(0,0,0,0.8)', objectFit: 'cover' }}
                />
              </div>
            </>
          ) : (
            <div className="h-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#1a1a2e,#0f3460)' }}>
              <span className="text-xl font-bold" style={{ color: 'var(--accent-gold)' }}>{movie.title}</span>
            </div>
          )}
          <div className="absolute bottom-0 inset-x-0 h-16" style={{ background: 'linear-gradient(to bottom, transparent, var(--bg-card))' }} />
        </div>

        {/* Body */}
        <div className="px-6 pb-6 -mt-2 space-y-4">
          {is_exploration && (
            <span className="inline-block text-white text-[10px] font-bold px-2 py-0.5 rounded-full"
              style={{ background: 'var(--accent-red)' }}>🔍 Discovery Pick</span>
          )}

          <div>
            <h2 className="text-2xl font-black text-white leading-tight">{movie.title}</h2>
            <div className="flex flex-wrap items-center gap-3 mt-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
              {movie.year && <span className="flex items-center gap-1"><Calendar size={11} />{movie.year}</span>}
              {movie.vote_average && (
                <span className="flex items-center gap-1">
                  <Star size={11} style={{ color: 'var(--accent-gold)' }} />
                  {Number(movie.vote_average).toFixed(1)}/10
                </span>
              )}
              {movie.runtime && <span className="flex items-center gap-1"><Clock size={11} />{formatRuntime(movie.runtime)}</span>}
              {movie.director && <span>🎬 {movie.director}</span>}
            </div>
          </div>

          {(movie.genres?.length ?? 0) > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {movie.genres!.map((g) => <span key={g} className="genre-pill">{g}</span>)}
            </div>
          )}

          {/* Score bar */}
          <div className="flex items-center gap-3">
            <span className="text-xs" style={{ color: 'var(--text-muted)', minWidth: '70px' }}>Match score</span>
            <div className="score-bar-track flex-1">
              <div className="score-bar-fill" style={{ width: `${pct}%`, background: barColor }} />
            </div>
            <span className="text-sm font-black" style={{ color: barColor }}>{pct}%</span>
          </div>

          {movie.overview && (
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>{movie.overview}</p>
          )}

          {explanation && (
            <div className="rounded-lg px-4 py-3 text-sm" style={{ background: 'var(--bg-overlay)', borderLeft: `3px solid ${barColor}`, color: 'var(--text-muted)' }}>
              <span className="text-white font-semibold">Why this? </span>{explanation}
            </div>
          )}

          {/* Feedback */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Rate this pick:</span>
            {([{ v: 'up', I: ThumbsUp, l: 'Love it', a: 'var(--accent-gold)', at: '#0a0a0f' },
               { v: 'down', I: ThumbsDown, l: 'Not for me', a: 'var(--accent-red)', at: '#fff' }] as const)
              .map(({ v, I, l, a, at }) => (
                <button key={v} onClick={() => handleRate(v)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium"
                  style={{ background: rated === v ? a : 'var(--bg-overlay)', color: rated === v ? at : 'var(--text-muted)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                  <I size={11} /> {l}
                </button>
              ))}
          </div>

          {/* Watch Now */}
          {tmdbId && (
            <button onClick={() => {
              setShowPlayer(true)
              recordInteraction(userId, tmdbId, 'clicked')
            }}
              className="flex items-center gap-2 text-sm font-bold"
              style={{ color: 'var(--accent-gold)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
              <PlayCircle size={16} /> Watch Now
            </button>
          )}
          {showPlayer && tmdbId && (
            <FullScreenPlayer tmdbId={tmdbId} title={movie.title} onClose={() => setShowPlayer(false)} />
          )}
        </div>
      </div>
    </div>
  )

  // Render modal in a portal at document.body level
  return createPortal(modalContent, document.body)
}

// ── Compact row (Recommendations list) ───────────────────────────────────────

export function MovieCard({ rec, rank, compact = true }: MovieCardProps) {
  const [open, setOpen] = useState(false)
  const { movie, score, is_exploration } = rec
  const poster = tmdbPoster(movie.poster_path, 'w185')
  const pct = Math.round(score * 100)
  const barColor = scoreColor(score)

  const handleClick = () => {
    console.log('MovieCard clicked, opening modal for:', movie.title)
    setOpen(true)
  }

  return (
    <>
      <button
        onClick={handleClick}
        className={cn(
          'w-full text-left transition-all animate-fade-in',
          compact
            ? 'flex items-center gap-3 rounded-xl px-3 py-2.5 hover:brightness-110'
            : 'poster-card group relative',
        )}
        style={compact
          ? { background: 'var(--bg-card)', border: '1px solid var(--border)', cursor: 'pointer', animationDelay: `${((rank ?? 1) - 1) * 0.045}s` }
          : { cursor: 'pointer', background: 'none', border: 'none', padding: 0 }
        }
      >
        {compact ? (
          <>
            {rank && (
              <span className="font-black text-base w-7 flex-shrink-0 text-center" style={{ color: 'var(--accent-gold)' }}>
                {rank}
              </span>
            )}
            <div className="w-9 h-13 flex-shrink-0 rounded overflow-hidden" style={{ height: '52px', width: '36px' }}>
              {poster
                ? <img src={poster} alt={movie.title} className="w-full h-full object-cover" loading="lazy" />
                : <div className="w-full h-full" style={{ background: '#1a1a2e' }} />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-sm text-white truncate">{movie.title}</p>
              <p className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
                {[movie.year, (movie.genres ?? []).slice(0, 2).join(' · ')].filter(Boolean).join(' · ')}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {is_exploration && (
                <span className="text-white text-[8px] font-black px-1.5 py-0.5 rounded-full uppercase" style={{ background: 'var(--accent-red)' }}>
                  disc
                </span>
              )}
              <div className="text-right">
                <div className="text-sm font-black" style={{ color: barColor }}>{pct}%</div>
              </div>
            </div>
          </>
        ) : (
          // Poster grid cell
          <div className="rounded-xl overflow-hidden relative" style={{ border: '1px solid var(--border)' }}>
            {poster
              ? <img src={poster} alt={movie.title} className="w-full aspect-[2/3] object-cover" loading="lazy" />
              : <div className="w-full aspect-[2/3]" style={{ background: 'linear-gradient(135deg,#1a1a2e,#0f3460)' }} />}
            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex flex-col justify-end p-2"
              style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, transparent 55%)' }}>
              <p className="text-white text-[10px] font-bold line-clamp-2 leading-tight">{movie.title}</p>
              {movie.year && <p className="text-[9px] mt-0.5" style={{ color: 'var(--text-muted)' }}>{movie.year}</p>}
              <p className="text-[10px] font-bold mt-0.5" style={{ color: barColor }}>{pct}%</p>
            </div>
            {rank && (
              <div className="absolute top-1.5 left-1.5 w-5 h-5 flex items-center justify-center rounded-full text-[9px] font-black"
                style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}>{rank}</div>
            )}
          </div>
        )}
      </button>

      {open && <MovieModal rec={rec} onClose={() => setOpen(false)} />}
    </>
  )
}

// ── Helper ────────────────────────────────────────────────────────────────────

export function movieToRec(movie: Movie, rank = 1): Recommendation {
  return { movie, score: Math.min((movie.vote_average ?? 5) / 10, 1), rank }
}

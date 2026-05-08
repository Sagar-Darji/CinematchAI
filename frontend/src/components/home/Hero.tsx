import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { PlayCircle, Info } from 'lucide-react'
import type { Movie, MediaType } from '@/lib/api'
import { FullScreenPlayer } from '@/components/ui/MovieCard'
import { useHistoryStore } from '@/store/useHistoryStore'

interface HeroProps {
  /** Up to ~5 candidates; the hero auto-rotates through them every 8s. */
  movies: Movie[]
}

function backdropUrl(path: string | null | undefined) {
  if (!path) return null
  return `https://image.tmdb.org/t/p/w1280${path}`
}

function posterUrl(path: string | null | undefined) {
  if (!path) return null
  return `https://image.tmdb.org/t/p/w780${path}`
}

const ROTATION_INTERVAL_MS = 8000

export function Hero({ movies }: HeroProps) {
  const [playerOpen, setPlayerOpen] = useState(false)
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const intervalRef = useRef<number | null>(null)

  // Cap to first 5 — anything beyond is noise.
  const candidates = movies.slice(0, 5)
  const movie = candidates[index] ?? null

  // Auto-rotate every 8s. Pauses while the player is open or the user is
  // hovering. Honors prefers-reduced-motion (skips rotation entirely).
  useEffect(() => {
    if (candidates.length <= 1) return
    if (paused || playerOpen) return
    if (typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return

    intervalRef.current = window.setInterval(() => {
      setIndex((i) => (i + 1) % candidates.length)
    }, ROTATION_INTERVAL_MS)
    return () => {
      if (intervalRef.current) window.clearInterval(intervalRef.current)
    }
  }, [candidates.length, paused, playerOpen])

  // If the candidates array shrinks (rare), keep index in bounds.
  useEffect(() => {
    if (index >= candidates.length && candidates.length > 0) setIndex(0)
  }, [candidates.length, index])

  if (!movie) {
    return (
      <section
        className="relative w-full overflow-hidden skeleton"
        style={{ height: 'min(70vh, 520px)', minHeight: '320px', borderRadius: 0 }}
      />
    )
  }

  // Movie type may not formally include backdrop_path; backend often returns it.
  const bg =
    backdropUrl((movie as Movie & { backdrop_path?: string }).backdrop_path) ??
    posterUrl(movie.poster_path)

  const mediaType: MediaType = movie.media_type ?? 'movie'
  const tmdbId = movie.tmdb_id ?? movie.id ?? 0

  return (
    <>
      <section
        className="relative w-full overflow-hidden"
        style={{ height: 'min(70vh, 520px)', minHeight: '380px' }}
        onPointerEnter={() => setPaused(true)}
        onPointerLeave={() => setPaused(false)}
        aria-roledescription="carousel"
        aria-label="Featured titles"
      >
        {bg && (
          <div
            aria-hidden
            className="absolute inset-0"
            style={{
              backgroundImage: `url(${bg})`,
              backgroundSize: 'cover',
              backgroundPosition: 'center 25%',
            }}
          />
        )}
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(to top, var(--bg-primary) 0%, rgba(10,10,15,0.55) 45%, rgba(10,10,15,0.05) 100%)',
          }}
        />
        <div
          aria-hidden
          className="absolute inset-0 hidden md:block"
          style={{
            background: 'linear-gradient(to right, var(--bg-primary) 0%, transparent 65%)',
          }}
        />

        <div className="relative h-full flex items-end pb-8 md:pb-12 px-5 md:px-10">
          <div className="max-w-2xl animate-fade-in">
            <p
              className="text-[10px] font-bold tracking-[0.3em] uppercase mb-2"
              style={{ color: 'var(--accent-gold)' }}
            >
              Featured · {mediaType === 'tv' ? 'Series' : 'Movie'}
            </p>
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-black text-white leading-[1.05] tracking-tight mb-3 line-clamp-3">
              {movie.title}
            </h1>
            {movie.overview && (
              <p
                className="hidden sm:block text-sm md:text-base mb-5 line-clamp-2 md:line-clamp-3"
                style={{ color: 'rgba(255,255,255,0.85)', maxWidth: '34rem' }}
              >
                {movie.overview}
              </p>
            )}
            <div className="flex items-center gap-2.5 flex-wrap">
              <button
                onClick={() => {
                  useHistoryStore.getState().record({
                    tmdbId,
                    mediaType,
                    title: movie.title,
                    posterPath: movie.poster_path,
                    year: movie.year,
                  })
                  setPlayerOpen(true)
                }}
                className="flex items-center gap-2 px-5 py-3 rounded-xl font-bold text-sm md:text-base transition-transform hover:scale-105"
                style={{
                  background: 'var(--accent-gold)',
                  color: '#0a0a0f',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                <PlayCircle size={18} /> Watch Now
              </button>
              <Link
                to="/browse"
                className="flex items-center gap-2 px-5 py-3 rounded-xl font-bold text-sm md:text-base"
                style={{
                  background: 'rgba(255,255,255,0.15)',
                  color: '#fff',
                  backdropFilter: 'blur(4px)',
                  textDecoration: 'none',
                  border: '1px solid rgba(255,255,255,0.18)',
                }}
              >
                <Info size={18} /> More like this
              </Link>
            </div>
          </div>
        </div>

        {/* Rotation indicator dots */}
        {candidates.length > 1 && (
          <div
            className="absolute bottom-3 right-4 md:right-10 flex items-center gap-1.5"
            role="tablist"
            aria-label="Featured slide selector"
          >
            {candidates.map((_, i) => (
              <button
                key={i}
                role="tab"
                aria-selected={i === index}
                aria-label={`Slide ${i + 1} of ${candidates.length}`}
                onClick={() => setIndex(i)}
                className="transition-all"
                style={{
                  height: 4,
                  width: i === index ? 22 : 8,
                  borderRadius: 2,
                  background: i === index ? 'var(--accent-gold)' : 'rgba(255,255,255,0.4)',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                }}
              />
            ))}
          </div>
        )}
      </section>

      {playerOpen && tmdbId > 0 && (
        <FullScreenPlayer
          tmdbId={tmdbId}
          title={movie.title}
          mediaType={mediaType}
          seasons={movie.seasons}
          onClose={() => setPlayerOpen(false)}
        />
      )}
    </>
  )
}

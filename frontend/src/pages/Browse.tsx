import { useState, useEffect, useCallback } from 'react'
import { Search, X } from 'lucide-react'
import { getTrending, searchMovies, getMoviesByGenre } from '@/lib/api'
import type { Movie, Recommendation } from '@/lib/api'
import { tmdbPoster, cn } from '@/lib/utils'
import { MovieCard } from '@/components/ui/MovieCard'

const GENRES = ['Action','Comedy','Drama','Horror','Sci-Fi','Romance','Thriller','Animation','Documentary','Crime']

// Convert a bare Movie into a Recommendation shape so MovieCard can handle it
function toRec(movie: Movie, rank: number): Recommendation {
  return { movie, score: (movie.vote_average ?? 5) / 10, rank, explanation: undefined, is_exploration: false }
}

export default function Browse() {
  const [movies, setMovies] = useState<Movie[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [activeGenre, setActiveGenre] = useState('')
  const [selectedMovie, setSelectedMovie] = useState<Movie | null>(null)

  const load = useCallback(async (q: string, genre: string) => {
    setLoading(true)
    try {
      let results: Movie[]
      if (q.trim()) {
        results = await searchMovies(q.trim(), 40)
      } else if (genre) {
        results = await getMoviesByGenre(genre, 40)
      } else {
        results = await getTrending(40)
      }
      setMovies(results)
    } catch {
      setMovies([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load('', '') }, [load])

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => load(query, activeGenre), 400)
    return () => clearTimeout(t)
  }, [query, activeGenre, load])

  const handleGenre = (g: string) => {
    setActiveGenre(g === activeGenre ? '' : g)
    setQuery('')
  }

  return (
    <div className="p-6 md:p-8 min-h-screen" style={{ background: 'var(--bg-primary)' }}>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-black tracking-tight text-white mb-1">Browse</h1>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          9,600+ movies · 20+ languages
        </p>
      </div>

      {/* Search + genre filter — nothing-to-watch style bar */}
      <div className="space-y-3 mb-8">
        <div
          className="flex items-center gap-3 rounded-xl px-4 py-3"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          <Search size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <input
            type="text"
            placeholder="Search by title, director, actor…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: 'var(--text-primary)' }}
          />
          {query && (
            <button onClick={() => setQuery('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
              <X size={14} />
            </button>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          {GENRES.map((g) => (
            <button
              key={g}
              onClick={() => handleGenre(g)}
              className={cn(
                'px-3 py-1.5 rounded-full text-xs font-semibold transition-all',
                activeGenre === g ? 'text-black' : 'text-muted hover:opacity-100 opacity-70',
              )}
              style={{
                background: activeGenre === g ? 'var(--accent-gold)' : 'var(--bg-card)',
                border: '1px solid var(--border)',
                color: activeGenre === g ? '#0a0a0f' : 'var(--text-muted)',
                cursor: 'pointer',
              }}
            >
              {g}
            </button>
          ))}
        </div>
      </div>

      {/* Poster grid — nothing-to-watch style */}
      {loading ? (
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 gap-3">
          {Array.from({ length: 28 }).map((_, i) => (
            <div key={i} className="skeleton aspect-[2/3] rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 gap-3">
          {movies.map((movie, i) => {
            const poster = tmdbPoster(movie.poster_path, 'w300')
            return (
              <button
                key={movie.tmdb_id ?? i}
                onClick={() => setSelectedMovie(selectedMovie?.tmdb_id === movie.tmdb_id ? null : movie)}
                className="poster-card rounded-lg overflow-hidden text-left relative"
                style={{
                  background: 'var(--bg-card)',
                  border: selectedMovie?.tmdb_id === movie.tmdb_id
                    ? '2px solid var(--accent-gold)'
                    : '1px solid var(--border)',
                  cursor: 'pointer',
                }}
                title={movie.title}
              >
                {poster ? (
                  <img
                    src={poster}
                    alt={movie.title}
                    className="w-full aspect-[2/3] object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div
                    className="w-full aspect-[2/3] flex items-center justify-center text-[10px] text-center p-2"
                    style={{ background: 'linear-gradient(135deg,#1a1a2e,#0f3460)', color: 'var(--accent-gold)' }}
                  >
                    {movie.title.slice(0, 25)}
                  </div>
                )}
                {/* Hover overlay */}
                <div className="absolute inset-0 opacity-0 hover:opacity-100 transition-opacity duration-200 flex flex-col justify-end p-2"
                  style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.9) 0%, transparent 60%)' }}>
                  <p className="text-white text-[10px] font-bold leading-tight line-clamp-2">{movie.title}</p>
                  {movie.year && <p className="text-[9px]" style={{ color: 'var(--text-muted)' }}>{movie.year}</p>}
                </div>
              </button>
            )
          })}
        </div>
      )}

      {/* Inline expanded card */}
      {selectedMovie && (
        <div
          className="mt-6 rounded-xl overflow-hidden animate-fade-in"
          style={{ border: '1px solid var(--accent-gold)' }}
        >
          <div className="flex items-center justify-between px-4 py-3" style={{ background: 'var(--bg-overlay)' }}>
            <span className="font-bold text-sm text-white">{selectedMovie.title}</span>
            <button
              onClick={() => setSelectedMovie(null)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
            >
              <X size={16} />
            </button>
          </div>
          <MovieCard rec={toRec(selectedMovie, 1)} />
        </div>
      )}

      {!loading && movies.length === 0 && (
        <div className="text-center py-20" style={{ color: 'var(--text-muted)' }}>
          No movies found. Try a different search.
        </div>
      )}
    </div>
  )
}

import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search as SearchIcon, X } from 'lucide-react'
import { searchMovies, type Movie } from '@/lib/api'
import { MovieCard, movieToRec } from '@/components/ui/MovieCard'
import { PageLoader } from '@/components/ui/PageLoader'

export default function Search() {
  const [params, setParams] = useSearchParams()
  const initialQ = params.get('q') ?? ''
  const [query, setQuery] = useState(initialQ)
  const [movies, setMovies] = useState<Movie[]>([])
  const [series, setSeries] = useState<Movie[]>([])
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef<number | null>(null)

  useEffect(() => {
    const trimmed = query.trim()
    if (debounceRef.current) clearTimeout(debounceRef.current)

    if (!trimmed) {
      setMovies([])
      setSeries([])
      setLoading(false)
      if (params.get('q')) {
        params.delete('q')
        setParams(params, { replace: true })
      }
      return
    }

    debounceRef.current = window.setTimeout(async () => {
      setLoading(true)
      params.set('q', trimmed)
      setParams(params, { replace: true })
      try {
        const [m, s] = await Promise.all([
          searchMovies(trimmed, 24, undefined, 1, 'movie'),
          searchMovies(trimmed, 24, undefined, 1, 'tv'),
        ])
        setMovies(m)
        setSeries(s)
      } finally {
        setLoading(false)
      }
    }, 380)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query])

  const total = movies.length + series.length

  return (
    <div className="min-h-screen px-4 md:px-6 pt-4 pb-10">
      <PageLoader visible={loading} />

      <div className="flex items-center gap-3 mb-5">
        <div
          className="flex items-center gap-2 rounded-xl px-3 py-2.5 flex-1"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          <SearchIcon size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <input
            autoFocus
            type="text"
            placeholder="Search movies & series…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent outline-none text-sm min-w-0"
            style={{ color: 'var(--text-primary)' }}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              aria-label="Clear search"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0, lineHeight: 0 }}
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {!query.trim() ? (
        <div className="text-center py-20">
          <div className="text-5xl mb-4">🎬</div>
          <p className="text-base font-bold text-white mb-1">Find what you want to watch</p>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Type a movie or series title — we search both at once.
          </p>
        </div>
      ) : !loading && total === 0 ? (
        <div className="flex flex-col items-center py-20 text-center">
          <div className="text-4xl mb-3">🤷</div>
          <p className="text-base font-bold text-white mb-1">No matches for "{query}"</p>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Try a different title or spelling.</p>
        </div>
      ) : (
        <>
          {movies.length > 0 && (
            <section className="mb-8">
              <h2 className="text-xs font-bold uppercase tracking-[0.2em] mb-3" style={{ color: 'var(--accent-gold)' }}>
                Movies · {movies.length}
              </h2>
              <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 md:gap-4">
                {movies.map((m, i) => (
                  <MovieCard key={`m-${m.tmdb_id ?? i}`} rec={movieToRec(m, i + 1)} compact={false} />
                ))}
              </div>
            </section>
          )}
          {series.length > 0 && (
            <section className="mb-8">
              <h2 className="text-xs font-bold uppercase tracking-[0.2em] mb-3" style={{ color: 'var(--accent-gold)' }}>
                Series · {series.length}
              </h2>
              <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 md:gap-4">
                {series.map((m, i) => (
                  <MovieCard key={`s-${m.tmdb_id ?? i}`} rec={movieToRec(m, i + 1)} compact={false} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}

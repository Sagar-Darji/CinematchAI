import { useState, useEffect, useCallback } from 'react'
import { Search, X } from 'lucide-react'
import { getTrending, searchMovies, discoverByGenre } from '@/lib/api'
import type { Movie } from '@/lib/api'
import { MovieCard, movieToRec } from '@/components/ui/MovieCard'

const GENRES = ['Action','Comedy','Drama','Horror','Sci-Fi','Romance','Thriller','Animation','Documentary','Crime','Adventure','Mystery']
const LANGUAGES = [
  { label: 'All', code: '' },
  { label: 'English', code: 'en' },
  { label: 'Hindi', code: 'hi' },
  { label: 'Korean', code: 'ko' },
  { label: 'Japanese', code: 'ja' },
  { label: 'Tamil', code: 'ta' },
  { label: 'Telugu', code: 'te' },
  { label: 'French', code: 'fr' },
  { label: 'Spanish', code: 'es' },
]

export default function Browse() {
  const [movies, setMovies] = useState<Movie[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [activeGenre, setActiveGenre] = useState('')
  const [activeLang, setActiveLang] = useState('')

  const load = useCallback(async (q: string, genre: string, lang: string) => {
    setLoading(true)
    try {
      let results: Movie[]
      if (q.trim()) {
        results = await searchMovies(q.trim(), 40, lang || undefined)
      } else if (genre) {
        results = await discoverByGenre(genre, 40, lang || undefined)
      } else {
        results = await getTrending(40, lang || undefined)
      }
      setMovies(results)
    } catch {
      setMovies([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load('', '', '') }, [load])

  // Debounce search; genre/lang changes are instant
  useEffect(() => {
    if (query.trim()) {
      const t = setTimeout(() => load(query, activeGenre, activeLang), 380)
      return () => clearTimeout(t)
    } else {
      load(query, activeGenre, activeLang)
    }
  }, [query, activeGenre, activeLang, load])

  const handleGenre = (g: string) => {
    setActiveGenre(g === activeGenre ? '' : g)
    setQuery('')
  }
  const handleLang = (code: string) => {
    setActiveLang(code === activeLang ? '' : code)
  }

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
      {/* Sticky filter bar — nothing-to-watch style */}
      <div
        className="sticky top-0 z-20 px-4 md:px-6 py-3 space-y-2.5"
        style={{ background: 'rgba(10,10,15,0.92)', backdropFilter: 'blur(12px)', borderBottom: '1px solid var(--border)' }}
      >
        {/* Search */}
        <div
          className="flex items-center gap-2.5 rounded-xl px-4 py-2.5"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          <Search size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <input
            type="text"
            placeholder="Search by title…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: 'var(--text-primary)' }}
          />
          {query && (
            <button onClick={() => setQuery('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0 }}>
              <X size={13} />
            </button>
          )}
        </div>

        {/* Language chips */}
        <div className="flex gap-1.5 overflow-x-auto pb-0.5 scrollbar-none">
          {LANGUAGES.map(({ label, code }) => (
            <button
              key={code}
              onClick={() => handleLang(code)}
              className="px-2.5 py-1 rounded-full text-[11px] font-semibold whitespace-nowrap flex-shrink-0"
              style={{
                background: activeLang === code ? 'var(--accent-gold)' : 'var(--bg-overlay)',
                color: activeLang === code ? '#0a0a0f' : 'var(--text-muted)',
                border: '1px solid var(--border)',
                cursor: 'pointer',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Genre chips */}
        <div className="flex gap-1.5 overflow-x-auto pb-0.5 scrollbar-none">
          {GENRES.map((g) => (
            <button
              key={g}
              onClick={() => handleGenre(g)}
              className="px-2.5 py-1 rounded-full text-[11px] font-semibold whitespace-nowrap flex-shrink-0"
              style={{
                background: activeGenre === g ? 'var(--accent-red)' : 'var(--bg-overlay)',
                color: activeGenre === g ? '#ffffff' : 'var(--text-muted)',
                border: '1px solid var(--border)',
                cursor: 'pointer',
              }}
            >
              {g}
            </button>
          ))}
        </div>
      </div>

      {/* Poster grid */}
      <div className="px-3 md:px-4 pt-4 pb-8">
        {loading ? (
          <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-7 xl:grid-cols-8 gap-2">
            {Array.from({ length: 32 }).map((_, i) => (
              <div key={i} className="skeleton aspect-[2/3] rounded-lg" />
            ))}
          </div>
        ) : movies.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="text-3xl mb-3">🎬</div>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              No movies found. Try a different search or filter.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-7 xl:grid-cols-8 gap-2">
            {movies.map((movie, i) => (
              <MovieCard
                key={movie.tmdb_id ?? i}
                rec={movieToRec(movie, i + 1)}
                compact={false}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

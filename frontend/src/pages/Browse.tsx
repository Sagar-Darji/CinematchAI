import { useState, useEffect, useCallback } from 'react'
import { Search, X, SlidersHorizontal } from 'lucide-react'
import { getTrending, searchMovies, discoverByGenre } from '@/lib/api'
import type { Movie } from '@/lib/api'
import { MovieCard, movieToRec } from '@/components/ui/MovieCard'
import { PageLoader } from '@/components/ui/PageLoader'

const GENRES = [
  'Action', 'Comedy', 'Drama', 'Horror', 'Sci-Fi', 'Romance',
  'Thriller', 'Animation', 'Documentary', 'Crime', 'Adventure', 'Mystery',
  'Fantasy', 'History', 'Music', 'War',
]

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
  { label: 'Arabic', code: 'ar' },
]

export default function Browse() {
  const [movies, setMovies] = useState<Movie[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [query, setQuery] = useState('')
  const [activeGenre, setActiveGenre] = useState('')
  const [activeLang, setActiveLang] = useState('')
  const [filtersOpen, setFiltersOpen] = useState(false)

  const load = useCallback(async (q: string, genre: string, lang: string) => {
    setLoading(true)
    setError(false)
    try {
      let results: Movie[]
      if (q.trim()) {
        results = await searchMovies(q.trim(), 48, lang || undefined)
      } else if (genre) {
        results = await discoverByGenre(genre, 48, lang || undefined)
      } else {
        results = await getTrending(48, lang || undefined)
      }
      setMovies(results)
    } catch {
      setMovies([])
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load('', '', '') }, [load])

  useEffect(() => {
    if (!query.trim()) {
      load('', activeGenre, activeLang)
      return
    }
    const t = setTimeout(() => load(query, activeGenre, activeLang), 380)
    return () => clearTimeout(t)
  }, [query, activeGenre, activeLang, load])

  const toggleGenre = (g: string) => { setActiveGenre(g === activeGenre ? '' : g); setQuery('') }
  const toggleLang = (code: string) => { setActiveLang(code === activeLang ? '' : code) }
  const clearAll = () => { setQuery(''); setActiveGenre(''); setActiveLang('') }

  const hasFilters = !!(activeGenre || activeLang || query)
  const heading = query ? `"${query}"`
    : activeGenre ? activeGenre
    : activeLang ? (LANGUAGES.find(l => l.code === activeLang)?.label ?? activeLang)
    : 'Trending'

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
      <PageLoader visible={loading} />

      {/* Sticky header */}
      <div className="sticky top-0 z-20"
        style={{ background: 'rgba(10,10,15,0.95)', backdropFilter: 'blur(14px)', borderBottom: '1px solid var(--border)' }}>

        {/* Title + search row */}
        <div className="flex items-center gap-3 px-4 md:px-6 pt-4 pb-2">
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-bold tracking-[0.3em] uppercase mb-0.5" style={{ color: 'var(--accent-gold)' }}>Browse</p>
            <h1 className="text-lg font-black text-white leading-none truncate">{heading}</h1>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Search */}
            <div className="flex items-center gap-2 rounded-xl px-3 py-2"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', width: '200px' }}>
              <Search size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
              <input
                type="text" placeholder="Search titles…" value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="flex-1 bg-transparent text-sm outline-none min-w-0"
                style={{ color: 'var(--text-primary)' }}
              />
              {query && (
                <button onClick={() => setQuery('')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0, lineHeight: 0 }}>
                  <X size={12} />
                </button>
              )}
            </div>

            {/* Filter toggle */}
            <button onClick={() => setFiltersOpen((v) => !v)}
              className="relative p-2.5 rounded-xl"
              style={{
                background: filtersOpen ? 'var(--bg-overlay)' : 'var(--bg-card)',
                border: `1px solid ${(hasFilters || filtersOpen) ? 'var(--accent-gold)' : 'var(--border)'}`,
                color: (hasFilters || filtersOpen) ? 'var(--accent-gold)' : 'var(--text-muted)',
                cursor: 'pointer',
              }}>
              <SlidersHorizontal size={15} />
              {hasFilters && (
                <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full"
                  style={{ background: 'var(--accent-gold)' }} />
              )}
            </button>
          </div>
        </div>

        {/* Filters panel */}
        {filtersOpen && (
          <div className="px-4 md:px-6 pb-3 space-y-2.5 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>Language</span>
              {hasFilters && (
                <button onClick={clearAll} className="text-[10px] font-semibold"
                  style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                  Clear all
                </button>
              )}
            </div>
            <div className="flex gap-1.5 overflow-x-auto pb-0.5" style={{ scrollbarWidth: 'none' }}>
              {LANGUAGES.map(({ label, code }) => (
                <button key={code} onClick={() => toggleLang(code)}
                  className="px-2.5 py-1 rounded-full text-[11px] font-semibold whitespace-nowrap flex-shrink-0"
                  style={{
                    background: activeLang === code ? 'var(--accent-gold)' : 'var(--bg-overlay)',
                    color: activeLang === code ? '#0a0a0f' : 'var(--text-muted)',
                    border: '1px solid var(--border)', cursor: 'pointer',
                  }}>{label}</button>
              ))}
            </div>

            <span className="text-[10px] font-bold uppercase tracking-widest block" style={{ color: 'var(--text-muted)' }}>Genre</span>
            <div className="flex gap-1.5 overflow-x-auto pb-0.5" style={{ scrollbarWidth: 'none' }}>
              {GENRES.map((g) => (
                <button key={g} onClick={() => toggleGenre(g)}
                  className="px-2.5 py-1 rounded-full text-[11px] font-semibold whitespace-nowrap flex-shrink-0"
                  style={{
                    background: activeGenre === g ? 'var(--accent-red)' : 'var(--bg-overlay)',
                    color: activeGenre === g ? '#ffffff' : 'var(--text-muted)',
                    border: `1px solid ${activeGenre === g ? 'rgba(229,9,20,0.5)' : 'var(--border)'}`,
                    cursor: 'pointer',
                  }}>{g}</button>
              ))}
            </div>
          </div>
        )}

        {/* Results count */}
        {!loading && (
          <div className="px-4 md:px-6 py-1.5 flex items-center gap-2 flex-wrap border-t" style={{ borderColor: 'var(--border)' }}>
            <span className="text-[11px] tabular-nums" style={{ color: 'var(--text-muted)' }}>
              {movies.length} {movies.length === 1 ? 'film' : 'films'}
            </span>
            {activeGenre && (
              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full"
                style={{ background: 'rgba(229,9,20,0.12)', color: '#ff6b6b', border: '1px solid rgba(229,9,20,0.25)' }}>
                {activeGenre}
                <button onClick={() => setActiveGenre('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: 0, lineHeight: 0 }}><X size={9} /></button>
              </span>
            )}
            {activeLang && (
              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full"
                style={{ background: 'rgba(245,197,24,0.1)', color: 'var(--accent-gold)', border: '1px solid rgba(245,197,24,0.2)' }}>
                {LANGUAGES.find(l => l.code === activeLang)?.label}
                <button onClick={() => setActiveLang('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: 0, lineHeight: 0 }}><X size={9} /></button>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Grid */}
      <div className="px-3 md:px-4 pt-3 pb-10">
        {loading ? (
          <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-7 xl:grid-cols-8 gap-2 md:gap-2.5">
            {Array.from({ length: 40 }).map((_, i) => (
              <div key={i} className="skeleton rounded-xl" style={{ aspectRatio: '2/3', animationDelay: `${i * 0.025}s` }} />
            ))}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-28 text-center">
            <div className="text-3xl mb-3">⚠️</div>
            <p className="text-sm font-semibold text-white mb-1">Failed to load</p>
            <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>API server may not be running</p>
            <button onClick={() => load(query, activeGenre, activeLang)}
              className="px-4 py-2 rounded-lg text-xs font-bold"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}>
              Retry
            </button>
          </div>
        ) : movies.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-28 text-center">
            <div className="text-4xl mb-3">🎬</div>
            <p className="text-sm font-semibold text-white mb-1">No films found</p>
            <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
              Try a different {activeGenre ? 'genre' : activeLang ? 'language' : 'search'}, or clear the filters.
            </p>
            {hasFilters && (
              <button onClick={clearAll} className="px-4 py-2 rounded-lg text-xs font-bold"
                style={{ background: 'var(--bg-overlay)', color: 'var(--text-muted)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-7 xl:grid-cols-8 gap-2 md:gap-2.5">
            {movies.map((movie, i) => (
              <div key={movie.tmdb_id ?? i} className="animate-fade-in" style={{ animationDelay: `${Math.min(i * 0.02, 0.6)}s` }}>
                <MovieCard rec={movieToRec(movie, i + 1)} compact={false} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

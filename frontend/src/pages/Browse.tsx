import { useState, useEffect, useCallback } from 'react'
import { Search, X, SlidersHorizontal, ChevronLeft, ChevronRight } from 'lucide-react'
import { getTrending, searchMovies, discoverByGenre } from '@/lib/api'
import type { MediaType, Movie } from '@/lib/api'
import { MovieCard, movieToRec } from '@/components/ui/MovieCard'
import { PageLoader } from '@/components/ui/PageLoader'

const MOVIE_GENRES = [
  'Action', 'Comedy', 'Drama', 'Horror', 'Sci-Fi', 'Romance',
  'Thriller', 'Animation', 'Documentary', 'Crime', 'Adventure', 'Mystery',
  'Fantasy', 'History', 'Music', 'War',
]

const TV_GENRES = [
  'Action', 'Comedy', 'Drama', 'Sci-Fi', 'Crime', 'Mystery',
  'Documentary', 'Animation', 'Family', 'Reality', 'Kids', 'War',
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
  const [mediaType, setMediaType] = useState<MediaType>('movie')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [query, setQuery] = useState('')
  const [activeGenre, setActiveGenre] = useState('')
  const [activeLang, setActiveLang] = useState('')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [hasMore, setHasMore] = useState(true)

  const genreOptions = mediaType === 'tv' ? TV_GENRES : MOVIE_GENRES
  const mediaLabel = mediaType === 'tv' ? 'series' : 'films'
  const mediaTitle = mediaType === 'tv' ? 'Series' : 'Movies'

  const load = useCallback(async (q: string, genre: string, lang: string, page: number, type: MediaType) => {
    setLoading(true)
    setError(false)
    try {
      let results: Movie[]
      if (q.trim()) {
        results = await searchMovies(q.trim(), 18, lang || undefined, page, type)
      } else if (genre) {
        results = await discoverByGenre(genre, 18, lang || undefined, page, type)
      } else {
        results = await getTrending(18, lang || undefined, page, type)
      }
      setMovies(results)
      setHasMore(results.length >= 18)
    } catch {
      setMovies([])
      setError(true)
      setHasMore(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setCurrentPage(1)
    if (!query.trim()) {
      load('', activeGenre, activeLang, 1, mediaType)
      return
    }
    const t = setTimeout(() => load(query, activeGenre, activeLang, 1, mediaType), 380)
    return () => clearTimeout(t)
  }, [query, activeGenre, activeLang, mediaType, load])

  const toggleGenre = (g: string) => { setActiveGenre(g === activeGenre ? '' : g); setQuery(''); setCurrentPage(1) }
  const toggleLang = (code: string) => { setActiveLang(code === activeLang ? '' : code); setCurrentPage(1) }
  const clearAll = () => { setQuery(''); setActiveGenre(''); setActiveLang(''); setCurrentPage(1) }
  const switchMediaType = (type: MediaType) => {
    if (type === mediaType) return
    setMediaType(type)
    setActiveGenre('')
    setCurrentPage(1)
  }

  const nextPage = () => {
    if (hasMore) {
      const newPage = currentPage + 1
      setCurrentPage(newPage)
      load(query, activeGenre, activeLang, newPage, mediaType)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }
  const prevPage = () => {
    if (currentPage > 1) {
      const newPage = currentPage - 1
      setCurrentPage(newPage)
      load(query, activeGenre, activeLang, newPage, mediaType)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const hasFilters = !!(activeGenre || activeLang || query)
  const heading = query ? `"${query}"`
    : activeGenre ? activeGenre
    : activeLang ? (LANGUAGES.find(l => l.code === activeLang)?.label ?? activeLang)
    : `Trending ${mediaTitle}`

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
      <PageLoader visible={loading} />

      {/* Sticky header */}
      <div className="sticky top-14 z-20"
        style={{ background: 'rgba(10,10,15,0.95)', backdropFilter: 'blur(14px)', borderBottom: '1px solid var(--border)' }}>

        {/* Title + search row */}
        <div className="flex items-center gap-3 px-4 md:px-6 pt-4 pb-2">
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-bold tracking-[0.3em] uppercase mb-0.5" style={{ color: 'var(--accent-gold)' }}>Discover</p>
            <h1 className="text-lg font-black text-white leading-none truncate">{heading}</h1>
            <div className="mt-2 inline-flex items-center gap-1 rounded-full p-1" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              {(['movie', 'tv'] as const).map((type) => (
                <button
                  key={type}
                  onClick={() => switchMediaType(type)}
                  className="px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-wide"
                  style={{
                    background: mediaType === type ? 'var(--accent-gold)' : 'transparent',
                    color: mediaType === type ? '#0a0a0f' : 'var(--text-muted)',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {type === 'tv' ? 'Series' : 'Movies'}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Search */}
            <div className="flex items-center gap-2 rounded-xl px-3 py-2"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', width: '200px' }}>
              <Search size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
              <input
                type="text" placeholder={`Search ${mediaType === 'tv' ? 'series' : 'movies'}…`} value={query}
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
            <select
              value={activeLang}
              onChange={(e) => toggleLang(e.target.value)}
              className="rounded-lg px-3 py-1.5 text-[12px] font-semibold outline-none"
              style={{
                background: 'var(--bg-overlay)',
                color: activeLang ? 'var(--accent-gold)' : 'var(--text-muted)',
                border: `1px solid ${activeLang ? 'var(--accent-gold)' : 'var(--border)'}`,
                cursor: 'pointer',
                maxWidth: '180px',
              }}
            >
              {LANGUAGES.map(({ label, code }) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>

            <span className="text-[10px] font-bold uppercase tracking-widest block" style={{ color: 'var(--text-muted)' }}>Genre</span>
            <div className="flex gap-1.5 overflow-x-auto pb-0.5" style={{ scrollbarWidth: 'none' }}>
              {genreOptions.map((g) => (
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
        {!loading && movies.length > 0 && (
          <div className="px-4 md:px-6 py-2 flex items-center gap-2 flex-wrap border-t" style={{ borderColor: 'var(--border)' }}>
            <span className="text-[11px] font-semibold tabular-nums" style={{ color: 'var(--accent-gold)' }}>
              {movies.length} {movies.length === 1 ? (mediaType === 'tv' ? 'series' : 'film') : mediaLabel}
            </span>
            <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>on this page</span>
            {activeGenre && (
              <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full"
                style={{ background: 'rgba(229,9,20,0.12)', color: '#ff6b6b', border: '1px solid rgba(229,9,20,0.25)' }}>
                {activeGenre}
                <button onClick={() => setActiveGenre('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: 0, lineHeight: 0 }}><X size={9} /></button>
              </span>
            )}
            {activeLang && (
              <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full"
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
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 md:gap-4">
            {Array.from({ length: 18 }).map((_, i) => (
              <div key={i} className="skeleton rounded-xl" style={{ aspectRatio: '2/3', animationDelay: `${i * 0.025}s` }} />
            ))}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-32 text-center px-4">
            <div className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
              style={{ background: 'rgba(229,9,20,0.1)', color: 'var(--accent-red)' }}>
              <span className="text-3xl">⚠️</span>
            </div>
            <p className="text-base font-bold text-white mb-2">Unable to load {mediaType === 'tv' ? 'series' : 'movies'}</p>
            <p className="text-sm mb-5 max-w-sm" style={{ color: 'var(--text-muted)' }}>
              The API server might be offline or experiencing issues. Please try again.
            </p>
            <button onClick={() => load(query, activeGenre, activeLang, currentPage, mediaType)}
              className="px-5 py-2.5 rounded-xl text-sm font-bold transition-transform hover:scale-105"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}>
              Retry
            </button>
          </div>
        ) : movies.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-32 text-center px-4">
            <div className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
              style={{ background: 'rgba(245,197,24,0.1)', color: 'var(--accent-gold)' }}>
              <span className="text-3xl">🎬</span>
            </div>
            <p className="text-base font-bold text-white mb-2">No {mediaType === 'tv' ? 'series' : 'films'} found</p>
            <p className="text-sm mb-1 max-w-sm" style={{ color: 'var(--text-muted)' }}>
              {query 
                ? `We couldn't find any ${mediaType === 'tv' ? 'series' : 'movies'} matching "${query}"`
                : activeGenre 
                ? `No ${activeGenre} ${mediaType === 'tv' ? 'series' : 'films'} available with current filters`
                : activeLang
                ? `No ${mediaType === 'tv' ? 'series' : 'films'} found in ${LANGUAGES.find(l => l.code === activeLang)?.label ?? activeLang}`
                : `No ${mediaType === 'tv' ? 'series' : 'movies'} available`}
            </p>
            <p className="text-xs mb-5" style={{ color: 'var(--text-muted)' }}>
              Try adjusting your filters or search terms.
            </p>
            {hasFilters && (
              <button onClick={clearAll} className="px-5 py-2.5 rounded-xl text-sm font-bold transition-transform hover:scale-105"
                style={{ background: 'var(--bg-overlay)', color: 'var(--text-primary)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                Clear all filters
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 md:gap-4">
              {movies.map((movie, i) => (
                <div key={movie.tmdb_id ?? i} className="animate-fade-in" style={{ animationDelay: `${Math.min(i * 0.02, 0.6)}s` }}>
                  <MovieCard rec={movieToRec(movie, i + 1)} compact={false} />
                </div>
              ))}
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-center gap-3 mt-10 mb-6">
              <button
                onClick={prevPage}
                disabled={currentPage === 1}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all hover:scale-105 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:scale-100"
                style={{
                  background: currentPage === 1 ? 'var(--bg-card)' : 'var(--accent-gold)',
                  color: currentPage === 1 ? 'var(--text-muted)' : '#0a0a0f',
                  border: currentPage === 1 ? '1px solid var(--border)' : 'none',
                  cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                }}
              >
                <ChevronLeft size={16} />
                Previous
              </button>

              <div className="flex items-center gap-2">
                <span className="px-4 py-2.5 rounded-xl text-sm font-bold tabular-nums min-w-[80px] text-center"
                  style={{ background: 'var(--bg-overlay)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                  Page <span style={{ color: 'var(--accent-gold)' }}>{currentPage}</span>
                </span>
              </div>

              <button
                onClick={nextPage}
                disabled={!hasMore}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all hover:scale-105 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:scale-100"
                style={{
                  background: !hasMore ? 'var(--bg-card)' : 'var(--accent-gold)',
                  color: !hasMore ? 'var(--text-muted)' : '#0a0a0f',
                  border: !hasMore ? '1px solid var(--border)' : 'none',
                  cursor: !hasMore ? 'not-allowed' : 'pointer',
                }}
              >
                Next
                <ChevronRight size={16} />
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

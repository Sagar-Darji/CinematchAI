import { useState, useEffect, useCallback } from 'react'
import { ChevronLeft, ChevronRight, CalendarDays, Tv2, Clapperboard } from 'lucide-react'
import { getNowPlaying, getUpcoming, getOttReleases } from '@/lib/api'
import type { Movie } from '@/lib/api'
import { MovieCard, movieToRec } from '@/components/ui/MovieCard'
import { PageLoader } from '@/components/ui/PageLoader'

// ── Static config ─────────────────────────────────────────────────────────────

const TABS = [
  { id: 'theaters', label: 'Now in Theaters', icon: Clapperboard },
  { id: 'upcoming', label: 'Coming Soon',      icon: CalendarDays  },
  { id: 'ott',      label: 'OTT / Streaming',  icon: Tv2           },
] as const
type TabId = (typeof TABS)[number]['id']

const REGIONS = [
  { label: 'Global (US)', code: 'US'  },
  { label: 'India',       code: 'IN'  },
  { label: 'UK',          code: 'GB'  },
  { label: 'Canada',      code: 'CA'  },
  { label: 'Australia',   code: 'AU'  },
  { label: 'Germany',     code: 'DE'  },
  { label: 'France',      code: 'FR'  },
  { label: 'South Korea', code: 'KR'  },
  { label: 'Japan',       code: 'JP'  },
]

const LANGUAGES = [
  { label: 'All',     code: ''   },
  { label: 'English', code: 'en' },
  { label: 'Hindi',   code: 'hi' },
  { label: 'Korean',  code: 'ko' },
  { label: 'Japanese',code: 'ja' },
  { label: 'Tamil',   code: 'ta' },
  { label: 'Telugu',  code: 'te' },
  { label: 'French',  code: 'fr' },
  { label: 'Spanish', code: 'es' },
]

const OTT_PLATFORMS = [
  { label: 'All Platforms',  id: '8|9|337|2|384|15' },
  { label: '🔴 Netflix',     id: '8'   },
  { label: '🟡 Prime Video', id: '9'   },
  { label: '🔵 Disney+',     id: '337' },
  { label: '⬛ Apple TV+',   id: '2'   },
  { label: '🟣 Max',         id: '384' },
  { label: '🟢 Hulu',        id: '15'  },
]

const OTT_DAYS = [7, 14, 30, 60, 90]

// ── Shared movie grid ─────────────────────────────────────────────────────────

function MovieGrid({ movies, loading, error, onRetry }: {
  movies: Movie[]
  loading: boolean
  error: boolean
  onRetry: () => void
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 md:gap-4 pt-4">
        {Array.from({ length: 18 }).map((_, i) => (
          <div key={i} className="skeleton rounded-xl" style={{ aspectRatio: '2/3', animationDelay: `${i * 0.025}s` }} />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-center px-4">
        <span className="text-4xl mb-4">⚠️</span>
        <p className="text-base font-bold text-white mb-2">Unable to load movies</p>
        <p className="text-sm mb-5 max-w-sm" style={{ color: 'var(--text-muted)' }}>
          The API server might be offline. Make sure it's running on port 8000.
        </p>
        <button
          onClick={onRetry}
          className="px-5 py-2.5 rounded-xl text-sm font-bold transition-transform hover:scale-105"
          style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
        >
          Retry
        </button>
      </div>
    )
  }

  if (movies.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-center px-4">
        <span className="text-4xl mb-4">🎬</span>
        <p className="text-base font-bold text-white mb-2">No movies found</p>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Try changing the region, language, or date range.
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 md:gap-4 pt-4">
      {movies.map((movie, i) => (
        <div key={movie.tmdb_id ?? i} className="animate-fade-in" style={{ animationDelay: `${Math.min(i * 0.02, 0.6)}s` }}>
          <MovieCard rec={movieToRec(movie, i + 1)} compact={false} />
        </div>
      ))}
    </div>
  )
}

// ── Pagination bar ────────────────────────────────────────────────────────────

function Pagination({ page, hasMore, onPrev, onNext }: {
  page: number; hasMore: boolean; onPrev: () => void; onNext: () => void
}) {
  return (
    <div className="flex items-center justify-center gap-3 mt-10 mb-6">
      <button
        onClick={onPrev} disabled={page === 1}
        className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all hover:scale-105 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:scale-100"
        style={{
          background: page === 1 ? 'var(--bg-card)' : 'var(--accent-gold)',
          color: page === 1 ? 'var(--text-muted)' : '#0a0a0f',
          border: page === 1 ? '1px solid var(--border)' : 'none',
          cursor: page === 1 ? 'not-allowed' : 'pointer',
        }}
      >
        <ChevronLeft size={16} /> Previous
      </button>
      <span className="px-4 py-2.5 rounded-xl text-sm font-bold tabular-nums min-w-[80px] text-center"
        style={{ background: 'var(--bg-overlay)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
        Page <span style={{ color: 'var(--accent-gold)' }}>{page}</span>
      </span>
      <button
        onClick={onNext} disabled={!hasMore}
        className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all hover:scale-105 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:scale-100"
        style={{
          background: !hasMore ? 'var(--bg-card)' : 'var(--accent-gold)',
          color: !hasMore ? 'var(--text-muted)' : '#0a0a0f',
          border: !hasMore ? '1px solid var(--border)' : 'none',
          cursor: !hasMore ? 'not-allowed' : 'pointer',
        }}
      >
        Next <ChevronRight size={16} />
      </button>
    </div>
  )
}

// ── Select helper ─────────────────────────────────────────────────────────────

function FilterSelect({ label, value, options, onChange }: {
  label: string
  value: string
  options: { label: string; code?: string; id?: string }[]
  onChange: (v: string) => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg px-3 py-2 text-xs font-semibold outline-none"
        style={{
          background: 'var(--bg-overlay)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border)',
          cursor: 'pointer',
        }}
      >
        {options.map((o) => {
          const val = (o.code !== undefined ? o.code : o.id) ?? ''
          return <option key={val} value={val}>{o.label}</option>
        })}
      </select>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ReleaseCalendar() {
  const [activeTab, setActiveTab] = useState<TabId>('theaters')

  // ─ Theaters state ─
  const [npMovies,  setNpMovies]  = useState<Movie[]>([])
  const [npLoading, setNpLoading] = useState(false)
  const [npError,   setNpError]   = useState(false)
  const [npRegion,  setNpRegion]  = useState('US')
  const [npLang,    setNpLang]    = useState('')
  const [npPage,    setNpPage]    = useState(1)
  const [npMore,    setNpMore]    = useState(true)

  // ─ Upcoming state ─
  const [upMovies,  setUpMovies]  = useState<Movie[]>([])
  const [upLoading, setUpLoading] = useState(false)
  const [upError,   setUpError]   = useState(false)
  const [upRegion,  setUpRegion]  = useState('US')
  const [upLang,    setUpLang]    = useState('')
  const [upPage,    setUpPage]    = useState(1)
  const [upMore,    setUpMore]    = useState(true)

  // ─ OTT state ─
  const [ottMovies,    setOttMovies]    = useState<Movie[]>([])
  const [ottLoading,   setOttLoading]   = useState(false)
  const [ottError,     setOttError]     = useState(false)
  const [ottPlatform,  setOttPlatform]  = useState('8|9|337|2|384|15')
  const [ottRegion,    setOttRegion]    = useState('US')
  const [ottLang,      setOttLang]      = useState('')
  const [ottDays,      setOttDays]      = useState(30)
  const [ottPage,      setOttPage]      = useState(1)
  const [ottMore,      setOttMore]      = useState(true)

  // ─ Loaders ─
  const loadNp = useCallback(async (region: string, lang: string, page: number) => {
    setNpLoading(true); setNpError(false)
    try {
      const data = await getNowPlaying(region, lang || undefined, page)
      setNpMovies(data); setNpMore(data.length >= 18)
    } catch { setNpMovies([]); setNpError(true) }
    finally { setNpLoading(false) }
  }, [])

  const loadUp = useCallback(async (region: string, lang: string, page: number) => {
    setUpLoading(true); setUpError(false)
    try {
      const data = await getUpcoming(region, lang || undefined, page)
      setUpMovies(data); setUpMore(data.length >= 18)
    } catch { setUpMovies([]); setUpError(true) }
    finally { setUpLoading(false) }
  }, [])

  const loadOtt = useCallback(async (providers: string, region: string, lang: string, days: number, page: number) => {
    setOttLoading(true); setOttError(false)
    try {
      const data = await getOttReleases(providers, region, lang || undefined, days, page)
      setOttMovies(data); setOttMore(data.length >= 18)
    } catch { setOttMovies([]); setOttError(true) }
    finally { setOttLoading(false) }
  }, [])

  // Initial loads per tab
  useEffect(() => { if (activeTab === 'theaters') loadNp(npRegion, npLang, npPage) }, [activeTab]) // eslint-disable-line
  useEffect(() => { if (activeTab === 'upcoming')  loadUp(upRegion, upLang, upPage) }, [activeTab]) // eslint-disable-line
  useEffect(() => { if (activeTab === 'ott')       loadOtt(ottPlatform, ottRegion, ottLang, ottDays, ottPage) }, [activeTab]) // eslint-disable-line

  // Re-fetch on filter change — reset page
  useEffect(() => { setNpPage(1); loadNp(npRegion, npLang, 1) }, [npRegion, npLang]) // eslint-disable-line
  useEffect(() => { setUpPage(1); loadUp(upRegion, upLang, 1) }, [upRegion, upLang]) // eslint-disable-line
  useEffect(() => { setOttPage(1); loadOtt(ottPlatform, ottRegion, ottLang, ottDays, 1) }, [ottPlatform, ottRegion, ottLang, ottDays]) // eslint-disable-line

  const npChangePage = (n: number) => { setNpPage(n); loadNp(npRegion, npLang, n); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const upChangePage = (n: number) => { setUpPage(n); loadUp(upRegion, upLang, n); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const ottChangePage = (n: number) => { setOttPage(n); loadOtt(ottPlatform, ottRegion, ottLang, ottDays, n); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  const isLoading = (activeTab === 'theaters' && npLoading) || (activeTab === 'upcoming' && upLoading) || (activeTab === 'ott' && ottLoading)

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
      <PageLoader visible={isLoading} />

      {/* Sticky header */}
      <div className="sticky top-14 z-20"
        style={{ background: 'rgba(10,10,15,0.95)', backdropFilter: 'blur(14px)', borderBottom: '1px solid var(--border)' }}>

        {/* Title */}
        <div className="px-4 md:px-6 pt-4 pb-3">
          <p className="text-[10px] font-bold tracking-[0.3em] uppercase mb-0.5" style={{ color: 'var(--accent-gold)' }}>Releases</p>
          <h1 className="text-lg font-black text-white leading-none">
            {TABS.find(t => t.id === activeTab)?.label}
          </h1>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-4 md:px-6 pb-0">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className="flex items-center gap-1.5 px-3 py-2.5 text-xs font-semibold border-b-2 transition-all"
              style={{
                borderColor: activeTab === id ? 'var(--accent-gold)' : 'transparent',
                color: activeTab === id ? 'var(--accent-gold)' : 'var(--text-muted)',
                background: 'none',
                border: 'none',
                borderBottom: `2px solid ${activeTab === id ? 'var(--accent-gold)' : 'transparent'}`,
                cursor: 'pointer',
              }}
            >
              <Icon size={14} />
              <span className="hidden sm:inline">{label}</span>
            </button>
          ))}
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4 px-4 md:px-6 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
          {activeTab === 'theaters' && (
            <>
              <FilterSelect label="Region" value={npRegion} options={REGIONS.map(r => ({ label: r.label, code: r.code }))} onChange={setNpRegion} />
              <FilterSelect label="Language" value={npLang} options={LANGUAGES} onChange={setNpLang} />
            </>
          )}
          {activeTab === 'upcoming' && (
            <>
              <FilterSelect label="Region" value={upRegion} options={REGIONS.map(r => ({ label: r.label, code: r.code }))} onChange={setUpRegion} />
              <FilterSelect label="Language" value={upLang} options={LANGUAGES} onChange={setUpLang} />
            </>
          )}
          {activeTab === 'ott' && (
            <>
              <FilterSelect label="Platform" value={ottPlatform} options={OTT_PLATFORMS.map(p => ({ label: p.label, code: p.id }))} onChange={setOttPlatform} />
              <FilterSelect label="Region" value={ottRegion} options={REGIONS.map(r => ({ label: r.label, code: r.code }))} onChange={setOttRegion} />
              <FilterSelect label="Language" value={ottLang} options={LANGUAGES} onChange={setOttLang} />
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>Released Within</span>
                <div className="flex gap-1">
                  {OTT_DAYS.map((d) => (
                    <button key={d} onClick={() => setOttDays(d)}
                      className="px-2.5 py-1.5 rounded-lg text-xs font-semibold"
                      style={{
                        background: ottDays === d ? 'var(--accent-gold)' : 'var(--bg-overlay)',
                        color: ottDays === d ? '#0a0a0f' : 'var(--text-muted)',
                        border: `1px solid ${ottDays === d ? 'transparent' : 'var(--border)'}`,
                        cursor: 'pointer',
                      }}
                    >{d}d</button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Count */}
        {!isLoading && (
          <div className="px-4 md:px-6 pb-2 flex items-center gap-2 border-t" style={{ borderColor: 'var(--border)' }}>
            <span className="text-[11px] font-semibold tabular-nums pt-2" style={{ color: 'var(--accent-gold)' }}>
              {activeTab === 'theaters' ? npMovies.length
               : activeTab === 'upcoming' ? upMovies.length
               : ottMovies.length} films
            </span>
            <span className="text-[11px] pt-2" style={{ color: 'var(--text-muted)' }}>on this page</span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="px-3 md:px-4 pb-10">
        {activeTab === 'theaters' && (
          <>
            <MovieGrid movies={npMovies} loading={npLoading} error={npError} onRetry={() => loadNp(npRegion, npLang, npPage)} />
            {!npLoading && !npError && npMovies.length > 0 && (
              <Pagination page={npPage} hasMore={npMore} onPrev={() => npChangePage(npPage - 1)} onNext={() => npChangePage(npPage + 1)} />
            )}
          </>
        )}
        {activeTab === 'upcoming' && (
          <>
            <MovieGrid movies={upMovies} loading={upLoading} error={upError} onRetry={() => loadUp(upRegion, upLang, upPage)} />
            {!upLoading && !upError && upMovies.length > 0 && (
              <Pagination page={upPage} hasMore={upMore} onPrev={() => upChangePage(upPage - 1)} onNext={() => upChangePage(upPage + 1)} />
            )}
          </>
        )}
        {activeTab === 'ott' && (
          <>
            <MovieGrid movies={ottMovies} loading={ottLoading} error={ottError} onRetry={() => loadOtt(ottPlatform, ottRegion, ottLang, ottDays, ottPage)} />
            {!ottLoading && !ottError && ottMovies.length > 0 && (
              <Pagination page={ottPage} hasMore={ottMore} onPrev={() => ottChangePage(ottPage - 1)} onNext={() => ottChangePage(ottPage + 1)} />
            )}
          </>
        )}
      </div>
    </div>
  )
}

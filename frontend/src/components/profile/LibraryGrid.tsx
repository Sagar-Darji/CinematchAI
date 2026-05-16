/**
 * Films / Series tab content: poster grid + sort + filter + search.
 * Server-side pagination via /profile/library/{user_id}. All filter
 * state is local; re-fetch fires on any control change.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { getProfileLibrary, type LibraryItem, type LibraryQuery } from '@/lib/api'
import { EmptyState } from './EmptyState'

interface Props {
  userId: string
  mediaType: 'movie' | 'tv'
  availableGenres: string[]
  availableDecades: number[]
}

type SortKey = 'rating' | 'date_watched' | 'title' | 'year'

const SORT_OPTIONS: Array<{ key: SortKey; label: string }> = [
  { key: 'date_watched', label: 'Recently watched' },
  { key: 'rating',       label: 'Rating' },
  { key: 'title',        label: 'Title (A–Z)' },
  { key: 'year',         label: 'Year' },
]

export function LibraryGrid({ userId, mediaType, availableGenres, availableDecades }: Props) {
  const [sort, setSort]       = useState<SortKey>('date_watched')
  const [genres, setGenres]   = useState<string[]>([])
  const [decades, setDecades] = useState<number[]>([])
  const [q, setQ]             = useState<string>('')
  const [items, setItems]     = useState<LibraryItem[]>([])
  const [cursor, setCursor]   = useState<number | null>(0)
  const [total, setTotal]     = useState<number>(0)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError]     = useState<string | null>(null)

  // Debounce title search so we don't fire a request per keystroke.
  const [debouncedQ, setDebouncedQ] = useState<string>('')
  const qTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (qTimer.current) clearTimeout(qTimer.current)
    qTimer.current = setTimeout(() => setDebouncedQ(q.trim()), 250)
    return () => { if (qTimer.current) clearTimeout(qTimer.current) }
  }, [q])

  const baseQuery = useMemo<LibraryQuery>(() => ({
    mediaType,
    sort,
    genres: genres.length ? genres : undefined,
    decades: decades.length ? decades : undefined,
    q: debouncedQ || undefined,
    limit: 60,
  }), [mediaType, sort, genres, decades, debouncedQ])

  // Whenever any filter changes, refetch from the start.
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getProfileLibrary(userId, { ...baseQuery, cursor: 0 })
      .then((page) => {
        if (cancelled) return
        setItems(page.items)
        setCursor(page.next_cursor)
        setTotal(page.total)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Could not load library.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [userId, baseQuery])

  const loadMore = async () => {
    if (cursor == null) return
    setLoading(true)
    try {
      const page = await getProfileLibrary(userId, { ...baseQuery, cursor })
      setItems((prev) => [...prev, ...page.items])
      setCursor(page.next_cursor)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load more.')
    } finally {
      setLoading(false)
    }
  }

  const toggleChip = <T,>(value: T, set: (next: T[]) => void, current: T[]) => {
    set(current.includes(value) ? current.filter((v) => v !== value) : [...current, value])
  }

  return (
    <div className="space-y-5">
      {/* ── Controls ─────────────────────────────────────────────── */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input
              type="search"
              placeholder={`Search ${mediaType === 'movie' ? 'films' : 'series'}…`}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="w-full rounded-lg pl-9 pr-3 py-2 text-sm"
              style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'white' }}
            />
          </div>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="rounded-lg px-3 py-2 text-sm"
            style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.key} value={o.key}>{o.label}</option>
            ))}
          </select>
        </div>
        {(availableGenres.length > 0 || availableDecades.length > 0) && (
          <div className="flex flex-col gap-2">
            {availableGenres.length > 0 && (
              <FilterChipRow
                label="Genre"
                items={availableGenres.map((g) => ({ key: g, label: g }))}
                selectedKeys={genres}
                onToggle={(k) => toggleChip(k as string, setGenres, genres)}
              />
            )}
            {availableDecades.length > 0 && (
              <FilterChipRow
                label="Decade"
                items={availableDecades.map((d) => ({ key: d, label: `${d}s` }))}
                selectedKeys={decades}
                onToggle={(k) => toggleChip(k as number, setDecades, decades)}
              />
            )}
          </div>
        )}
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {loading ? 'Loading…' : `${total.toLocaleString()} ${mediaType === 'movie' ? 'films' : 'series'} matched`}
        </p>
      </div>

      {/* ── Grid ─────────────────────────────────────────────────── */}
      {error && <p className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</p>}
      {!loading && items.length === 0 && !error ? (
        <EmptyState
          title={mediaType === 'movie' ? 'No films match' : 'No series match'}
          body={q || genres.length || decades.length ? 'Try clearing the filters.' : 'Rate something or import from Letterboxd to fill this in.'}
          ctaLabel={q || genres.length || decades.length ? undefined : 'Import'}
          ctaHref={q || genres.length || decades.length ? undefined : '/settings'}
        />
      ) : (
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
          {items.map((it) => (
            <Link
              key={it.movie_id}
              to={`/movie/${it.movie_id}`}
              className="group"
            >
              <div
                style={{ aspectRatio: '2/3', background: 'var(--bg-card)', borderRadius: '8px', overflow: 'hidden' }}
                className="relative"
              >
                {it.poster_path ? (
                  <img
                    src={`https://image.tmdb.org/t/p/w342${it.poster_path}`}
                    alt={it.title ?? ''}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-xs" style={{ color: 'var(--text-muted)' }}>
                    No poster
                  </div>
                )}
                <span
                  className="absolute top-1 right-1 text-[10px] font-bold px-1.5 py-0.5 rounded"
                  style={{ background: 'rgba(0,0,0,0.7)', color: 'var(--accent-gold)' }}
                >
                  {it.rating}★
                </span>
              </div>
              <p className="text-xs mt-1.5 truncate text-white" title={it.title ?? undefined}>
                {it.title}
              </p>
              {it.year && (
                <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{it.year}</p>
              )}
            </Link>
          ))}
        </div>
      )}

      {cursor != null && items.length > 0 && (
        <button
          type="button"
          onClick={loadMore}
          disabled={loading}
          className="w-full py-2 rounded-lg text-sm font-semibold disabled:opacity-40"
          style={{ background: 'var(--bg-overlay)', color: 'var(--text-muted)', border: '1px solid var(--border)', cursor: 'pointer' }}
        >
          {loading ? 'Loading…' : 'Show more'}
        </button>
      )}
    </div>
  )
}

function FilterChipRow<T extends string | number>({
  label,
  items,
  selectedKeys,
  onToggle,
}: {
  label: string
  items: Array<{ key: T; label: string }>
  selectedKeys: T[]
  onToggle: (key: T) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-[10px] font-bold uppercase tracking-widest mr-1" style={{ color: 'var(--text-muted)' }}>
        {label}
      </span>
      {items.map((it) => {
        const active = selectedKeys.includes(it.key)
        return (
          <button
            key={String(it.key)}
            type="button"
            onClick={() => onToggle(it.key)}
            className="text-[11px] px-2 py-0.5 rounded-full"
            style={{
              background: active ? 'var(--accent-gold)' : 'var(--bg-overlay)',
              color:      active ? '#0a0a0f'           : 'var(--text-muted)',
              border:     active ? 'none'              : '1px solid var(--border)',
              cursor:     'pointer',
            }}
          >
            {it.label}
          </button>
        )
      })}
    </div>
  )
}

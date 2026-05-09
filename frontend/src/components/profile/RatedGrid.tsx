import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Star, Loader2, ArrowDownUp } from 'lucide-react'
import { getUserRatings, type RatedItem, type RatingSort } from '@/lib/api'
import { tmdbPoster } from '@/lib/utils'

interface Props {
  userId: string
  mediaType: 'movie' | 'tv'
}

const SORT_OPTIONS: Array<{ value: RatingSort; label: string }> = [
  { value: 'date_desc', label: 'Newest first' },
  { value: 'date_asc', label: 'Oldest first' },
  { value: 'rating_desc', label: 'Highest rated' },
  { value: 'rating_asc', label: 'Lowest rated' },
  { value: 'title_asc', label: 'A → Z' },
]

const PAGE_SIZE = 24

/**
 * Letterboxd-style poster grid for the Films / Series tabs. Each card is a
 * poster with the user's rating overlaid in the corner; clicking jumps to
 * the title detail page. Sortable, paginated via "Load more".
 */
export function RatedGrid({ userId, mediaType }: Props) {
  const [items, setItems] = useState<RatedItem[]>([])
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [total, setTotal] = useState(0)
  const [sort, setSort] = useState<RatingSort>('date_desc')
  const [loading, setLoading] = useState(false)
  const [appending, setAppending] = useState(false)
  const seenSort = useRef<RatingSort>(sort)

  // Reset on sort change.
  useEffect(() => {
    if (seenSort.current === sort) return
    seenSort.current = sort
    setItems([])
    setPage(1)
  }, [sort])

  // Fetch (or refetch) when page or sort changes.
  useEffect(() => {
    let cancelled = false
    const isFirstPage = page === 1
    if (isFirstPage) setLoading(true)
    else setAppending(true)
    getUserRatings(userId, { mediaType, sort, page, limit: PAGE_SIZE })
      .then((data) => {
        if (cancelled || !data) return
        setItems((prev) => (isFirstPage ? data.items : [...prev, ...data.items]))
        setHasMore(data.has_more)
        setTotal(data.total)
      })
      .finally(() => {
        if (cancelled) return
        setLoading(false)
        setAppending(false)
      })
    return () => { cancelled = true }
  }, [userId, mediaType, sort, page])

  const headerLabel = mediaType === 'tv' ? 'Series' : 'Films'
  const skeletonCount = useMemo(() => Math.min(PAGE_SIZE, 12), [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-baseline gap-2">
          <h3 className="text-lg font-black text-white">{headerLabel}</h3>
          {total > 0 && (
            <span className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
              {total.toLocaleString()} rated
            </span>
          )}
        </div>
        <SortMenu value={sort} onChange={setSort} />
      </div>

      {loading && items.length === 0 ? (
        <SkeletonGrid count={skeletonCount} />
      ) : items.length === 0 ? (
        <div
          className="rounded-xl p-10 text-center"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            {mediaType === 'tv'
              ? "No rated series yet — rate a show from its detail page and it'll show up here."
              : "No rated films yet — rate films from the recommendations or import your Letterboxd CSV from the Overview tab."}
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-3">
            {items.map((it) => (
              <PosterCard key={`${it.movie_id}-${it.media_type}`} item={it} />
            ))}
          </div>
          {hasMore && (
            <div className="flex justify-center pt-3">
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={appending}
                className="text-sm font-bold flex items-center gap-2"
                style={{
                  padding: '10px 20px',
                  borderRadius: '12px',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-hover)',
                  color: 'var(--text-primary)',
                  cursor: appending ? 'wait' : 'pointer',
                  opacity: appending ? 0.7 : 1,
                }}
              >
                {appending ? <Loader2 size={14} className="animate-spin" /> : null}
                {appending ? 'Loading…' : 'Load more'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function PosterCard({ item }: { item: RatedItem }) {
  const poster = tmdbPoster(item.poster_path ?? undefined, 'w300')
  const mt = item.media_type ?? 'movie'
  const rating = item.rating
  // Backend stores a 1–10 scale; display as half-stars 0.5–5.0.
  const starValue = rating != null ? Math.max(0.5, Math.min(5, rating / 2)) : null
  return (
    <Link
      to={`/title/${mt}/${item.movie_id}`}
      className="block group relative"
      style={{ textDecoration: 'none' }}
    >
      <div
        className="rounded-lg overflow-hidden relative"
        style={{
          aspectRatio: '2/3',
          border: '1px solid var(--border)',
          background: 'var(--bg-overlay)',
        }}
      >
        {poster ? (
          <img
            src={poster}
            alt={item.title ?? ''}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-center p-2 text-[10px] font-bold text-white">
            {item.title ?? `#${item.movie_id}`}
          </div>
        )}
        {/* Rating overlay — bottom-left corner, gold pill */}
        {starValue != null && (
          <div
            className="absolute bottom-1.5 left-1.5 flex items-center gap-0.5 px-1.5 py-0.5 rounded-md"
            style={{
              background: 'rgba(0,0,0,0.78)',
              backdropFilter: 'blur(6px)',
              color: 'var(--accent-gold)',
              fontSize: '10px',
              fontWeight: 800,
              border: '1px solid rgba(245,197,24,0.35)',
            }}
          >
            <Star size={9} fill="currentColor" />
            {starValue.toFixed(1)}
          </div>
        )}
      </div>
      <p className="text-[11px] font-semibold text-white truncate leading-tight mt-1.5">
        {item.title ?? `#${item.movie_id}`}
      </p>
      {item.year && (
        <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
          {item.year}
        </p>
      )}
    </Link>
  )
}

function SortMenu({ value, onChange }: { value: RatingSort; onChange: (s: RatingSort) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])
  const current = SORT_OPTIONS.find((o) => o.value === value)?.label ?? 'Sort'
  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs font-semibold"
        style={{
          padding: '7px 12px',
          borderRadius: '10px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          color: 'var(--text-primary)',
          cursor: 'pointer',
        }}
      >
        <ArrowDownUp size={12} /> {current}
      </button>
      {open && (
        <div
          className="absolute right-0 top-full mt-1 rounded-lg overflow-hidden shadow-2xl"
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-hover)',
            zIndex: 10,
            minWidth: '160px',
          }}
        >
          {SORT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => { onChange(opt.value); setOpen(false) }}
              className="w-full text-left text-xs font-semibold"
              style={{
                padding: '9px 12px',
                background: value === opt.value ? 'var(--bg-overlay)' : 'transparent',
                border: 'none',
                borderBottom: '1px solid var(--border)',
                color: value === opt.value ? 'var(--accent-gold)' : 'var(--text-primary)',
                cursor: 'pointer',
                display: 'block',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function SkeletonGrid({ count }: { count: number }) {
  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i}>
          <div className="skeleton rounded-lg" style={{ aspectRatio: '2/3' }} />
          <div className="skeleton-text mt-1.5 w-3/4" />
        </div>
      ))}
    </div>
  )
}

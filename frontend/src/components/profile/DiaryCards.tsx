/**
 * Diary tab content: 4 cards (year-over-year chart, multi-year heatmap
 * with year selector, monthly highlight reel, paginated recently-watched
 * timeline grouped by month).
 *
 * Year chart / heatmap / month highlights come from the precomputed blob
 * (props). Recently-watched is paginated via getProfileDiary — kept out
 * of the blob because it can be thousands of rows.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getProfileDiary, type DiaryEntry, type ProfileDiaryPayload } from '@/lib/api'
import { Heatmap } from './Heatmap'
import { MonthHighlight } from './MonthHighlight'
import { EmptyState } from './EmptyState'

interface DiaryCardsProps {
  userId: string
  diary: ProfileDiaryPayload
}

export function DiaryCards({ userId, diary }: DiaryCardsProps) {
  const availableYears = useMemo(
    () => Object.keys(diary.heatmaps).map(Number).sort((a, b) => b - a),
    [diary.heatmaps],
  )
  const [selectedYear, setSelectedYear] = useState<number>(
    availableYears[0] ?? new Date().getFullYear(),
  )
  const heatmapCounts = diary.heatmaps[String(selectedYear)] ?? {}

  return (
    <div className="space-y-6">
      {/* ── Year-over-year ──────────────────────────────────────────── */}
      <Card title="Activity over the years">
        {Object.keys(diary.year_chart).length > 0 ? (
          <YearActivityChart data={diary.year_chart} />
        ) : (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No dated ratings yet.</p>
        )}
      </Card>

      {/* ── Heatmap with year selector ──────────────────────────────── */}
      <Card
        title={`Activity in ${selectedYear}`}
        right={
          availableYears.length > 1 ? (
            <select
              value={selectedYear}
              onChange={(e) => setSelectedYear(parseInt(e.target.value, 10))}
              className="rounded-md px-2 py-1 text-xs"
              style={{
                background: 'var(--bg-overlay)',
                border: '1px solid var(--border)',
                color: 'var(--text-muted)',
              }}
            >
              {availableYears.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          ) : null
        }
      >
        {availableYears.length > 0 ? (
          <Heatmap counts={heatmapCounts} year={selectedYear} />
        ) : (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            No watch dates yet — rate a few films or import from Letterboxd.
          </p>
        )}
      </Card>

      {/* ── Monthly highlight reel ──────────────────────────────────── */}
      {diary.monthly_highlights.length > 0 && (
        <Card title="Monthly highlights">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {diary.monthly_highlights.map((h) => (
              <MonthHighlight
                key={h.month}
                month={h.month}
                total={h.total}
                topFilm={h.top_film}
                dominantGenre={h.dominant_genre}
              />
            ))}
          </div>
        </Card>
      )}

      {/* ── Recently watched timeline ───────────────────────────────── */}
      <Card title="Recently watched">
        <RecentlyWatchedTimeline userId={userId} />
      </Card>
    </div>
  )
}

function Card({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section
      className="rounded-2xl p-5"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
          {title}
        </h2>
        {right}
      </div>
      {children}
    </section>
  )
}

// ── Tiny year activity chart (decoupled from UserStats) ─────────────

function YearActivityChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data)
    .map(([y, c]) => ({ year: parseInt(y, 10), count: c }))
    .filter((e) => !Number.isNaN(e.year))
    .sort((a, b) => a.year - b.year)
  if (entries.length === 0) return null
  const max = Math.max(...entries.map((e) => e.count))
  const currentYear = new Date().getUTCFullYear()
  return (
    <div className="flex items-end gap-1.5 overflow-x-auto hide-scrollbar" style={{ height: '120px' }}>
      {entries.map((e) => {
        const pct = max > 0 ? Math.max(4, Math.round((e.count / max) * 100)) : 4
        const isCurrent = e.year === currentYear
        return (
          <div key={e.year} className="flex flex-col items-center gap-1" style={{ minWidth: '24px' }}>
            <div
              className="w-full rounded-t-sm"
              title={`${e.year}: ${e.count}`}
              style={{
                height: `${pct}%`,
                background: isCurrent ? 'var(--accent-gold)' : 'rgba(255,255,255,0.18)',
              }}
            />
            <span className="text-[9px]" style={{ color: 'var(--text-muted)' }}>
              {String(e.year).slice(2)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── Recently-watched timeline (paginated, grouped by month) ─────────

function monthLabel(iso: string | null): string {
  if (!iso) return 'Undated'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Undated'
  return `${MONTH_FULL[d.getUTCMonth()]} ${d.getUTCFullYear()}`
}

const MONTH_FULL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

function RecentlyWatchedTimeline({ userId }: { userId: string }) {
  const [pages, setPages] = useState<DiaryEntry[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [firstFetched, setFirstFetched] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getProfileDiary(userId, { limit: 60 })
      .then((page) => {
        if (cancelled) return
        setPages(page.items)
        setCursor(page.next_cursor)
        setHasMore(page.has_more)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Could not load diary.')
      })
      .finally(() => {
        if (cancelled) return
        setLoading(false)
        setFirstFetched(true)
      })
    return () => { cancelled = true }
  }, [userId])

  const loadMore = async () => {
    if (!cursor || !hasMore || loading) return
    setLoading(true)
    try {
      const page = await getProfileDiary(userId, { cursor, limit: 60 })
      setPages((prev) => [...prev, ...page.items])
      setCursor(page.next_cursor)
      setHasMore(page.has_more)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load more.')
    } finally {
      setLoading(false)
    }
  }

  // Group by month -> array of entries
  const grouped = useMemo(() => {
    const map = new Map<string, DiaryEntry[]>()
    for (const e of pages) {
      const k = monthLabel(e.timestamp)
      if (!map.has(k)) map.set(k, [])
      map.get(k)!.push(e)
    }
    return Array.from(map.entries())
  }, [pages])

  if (firstFetched && pages.length === 0 && !error) {
    return (
      <EmptyState
        title="Nothing watched yet"
        body="Start rating films or import your Letterboxd diary to see your history here."
        ctaLabel="Import"
        ctaHref="/settings"
      />
    )
  }

  return (
    <div className="space-y-6">
      {error && (
        <p className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</p>
      )}
      {grouped.map(([month, entries]) => (
        <div key={month}>
          <h3
            className="text-[11px] font-bold uppercase tracking-widest mb-2 pb-1"
            style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}
          >
            {month}
          </h3>
          <ul className="space-y-2">
            {entries.map((e) => (
              <li key={`${e.movie_id}-${e.timestamp}`}>
                <Link
                  to={`/movie/${e.movie_id}`}
                  className="flex items-center gap-3 rounded-lg p-2 transition-colors hover:opacity-90"
                  style={{ background: 'var(--bg-overlay)' }}
                >
                  {e.poster_path ? (
                    <img
                      src={`https://image.tmdb.org/t/p/w92${e.poster_path}`}
                      alt=""
                      width={36}
                      height={54}
                      style={{ borderRadius: '4px', objectFit: 'cover' }}
                    />
                  ) : (
                    <div
                      style={{ width: 36, height: 54, borderRadius: '4px', background: 'var(--bg-card)' }}
                    />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-white truncate">
                      {e.title ?? `#${e.movie_id}`}
                      {e.year && <span className="font-normal ml-1" style={{ color: 'var(--text-muted)' }}>({e.year})</span>}
                    </p>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {e.timestamp ? new Date(e.timestamp).toLocaleDateString() : '—'}
                      {' · '}
                      <span style={{ color: 'var(--accent-gold)' }}>{e.rating}★</span>
                    </p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {hasMore && (
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

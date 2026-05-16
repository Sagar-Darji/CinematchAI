/**
 * One month card for the Diary tab's monthly-highlight reel. Shows the
 * month name, total films watched, dominant genre, and the top-rated
 * pick for that month. Precomputed in the backend; this is pure render.
 */

interface Props {
  /** "YYYY-MM" e.g. "2026-04" */
  month: string
  total: number
  topFilm: { title: string | null; year: number | null; rating: number | null }
  dominantGenre: string | null
}

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

export function MonthHighlight({ month, total, topFilm, dominantGenre }: Props) {
  const [yr, mn] = month.split('-')
  const label = `${MONTH_NAMES[Math.max(0, parseInt(mn, 10) - 1)]} ${yr}`
  return (
    <div
      className="rounded-xl p-4 flex flex-col justify-between"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      <div>
        <p className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
          {label}
        </p>
        <p className="text-2xl font-bold text-white mt-1">
          {total} <span className="text-sm font-normal" style={{ color: 'var(--text-muted)' }}>watched</span>
        </p>
        {dominantGenre && (
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            Mostly {dominantGenre}
          </p>
        )}
      </div>
      {topFilm.title && (
        <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
          <p className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>Top pick</p>
          <p className="text-sm font-semibold text-white truncate" title={topFilm.title}>
            {topFilm.title}
          </p>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {topFilm.year ?? '—'}
            {topFilm.rating != null && (
              <> · <span style={{ color: 'var(--accent-gold)' }}>{topFilm.rating}★</span></>
            )}
          </p>
        </div>
      )}
    </div>
  )
}

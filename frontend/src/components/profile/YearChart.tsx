import { Calendar } from 'lucide-react'
import type { UserStats } from '@/lib/api'

interface Props {
  stats: UserStats
}

/** Year-by-year activity chart. Renders one bar per year that appears in
 * stats.year_breakdown (which counts ratings by their *watch* timestamp,
 * not film release year). The current year sits at the right and gets
 * gold treatment to draw the eye to the user's most recent activity. */
export function YearChart({ stats }: Props) {
  const breakdown = stats.year_breakdown ?? {}
  const entries = Object.entries(breakdown)
    .map(([y, c]) => ({ year: parseInt(y, 10), count: c }))
    .filter((e) => !isNaN(e.year))
    .sort((a, b) => a.year - b.year)
  if (entries.length < 2) return null

  const max = Math.max(...entries.map((e) => e.count))
  const currentYear = new Date().getUTCFullYear()

  return (
    <div
      className="rounded-2xl p-5"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2 mb-4">
        <Calendar size={14} style={{ color: 'var(--accent-gold)' }} />
        <h3
          className="text-xs font-bold uppercase tracking-widest"
          style={{ color: 'var(--text-muted)' }}
        >
          By year watched
        </h3>
      </div>
      <div className="flex items-end gap-1.5 overflow-x-auto hide-scrollbar" style={{ height: '120px' }}>
        {entries.map((e) => {
          const pct = (e.count / max) * 100
          const isCurrent = e.year === currentYear
          return (
            <div
              key={e.year}
              className="flex-1 flex flex-col items-center gap-1 min-w-[24px]"
              title={`${e.year}: ${e.count} ${e.count === 1 ? 'rating' : 'ratings'}`}
            >
              <span
                className="text-[10px] font-bold"
                style={{ color: isCurrent ? 'var(--accent-gold)' : 'var(--text-muted)' }}
              >
                {e.count}
              </span>
              <div
                className="w-full rounded-t-sm transition-all"
                style={{
                  height: `${pct}%`,
                  minHeight: '3px',
                  background: isCurrent ? 'var(--accent-gold)' : 'rgba(245,197,24,0.45)',
                }}
              />
            </div>
          )
        })}
      </div>
      <div className="flex gap-1.5 mt-1.5 overflow-x-auto hide-scrollbar">
        {entries.map((e) => (
          <div
            key={e.year}
            className="flex-1 text-[10px] font-semibold text-center min-w-[24px]"
            style={{
              color:
                e.year === currentYear ? 'var(--accent-gold)' : 'var(--text-muted)',
            }}
          >
            {String(e.year).slice(-2)}
          </div>
        ))}
      </div>
    </div>
  )
}

import { Star } from 'lucide-react'
import type { HistogramBucket } from '@/lib/profileStats'

interface Props {
  buckets: HistogramBucket[]
}

/** Vertical bar chart of rating distribution — 10 half-star buckets. */
export function RatingHistogram({ buckets }: Props) {
  const max = Math.max(1, ...buckets.map((b) => b.count))
  const total = buckets.reduce((sum, b) => sum + b.count, 0)

  if (total === 0) {
    return (
      <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
        No ratings yet — rate a few films to see your distribution.
      </p>
    )
  }

  return (
    <div>
      <div className="flex items-end gap-1.5" style={{ height: '120px' }}>
        {buckets.map((b) => {
          const pct = (b.count / max) * 100
          return (
            <div key={b.rating} className="flex-1 flex flex-col items-center gap-1.5 min-w-0">
              <span className="text-[10px] font-bold" style={{ color: b.count > 0 ? 'var(--accent-gold)' : 'var(--text-muted)' }}>
                {b.count || ''}
              </span>
              <div
                className="w-full rounded-t-sm transition-all"
                style={{
                  height: `${pct}%`,
                  minHeight: b.count > 0 ? '4px' : '2px',
                  background: b.count > 0 ? 'var(--accent-gold)' : 'var(--bg-overlay)',
                  opacity: b.count > 0 ? 1 : 0.5,
                }}
                title={`${b.rating}★ — ${b.count} ${b.count === 1 ? 'rating' : 'ratings'}`}
              />
            </div>
          )
        })}
      </div>
      <div className="flex items-end gap-1.5 mt-1.5">
        {buckets.map((b) => (
          <div key={b.rating} className="flex-1 flex items-center justify-center gap-0.5 min-w-0">
            <span className="text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
              {b.rating % 1 === 0 ? b.rating.toFixed(0) : b.rating.toFixed(1)}
            </span>
            <Star size={8} style={{ color: 'var(--text-muted)' }} fill="currentColor" />
          </div>
        ))}
      </div>
    </div>
  )
}

import { Calendar, Trophy, Film } from 'lucide-react'
import type { YearInReview as Stats } from '@/lib/profileStats'

interface Props {
  stats: Stats
}

export function YearInReview({ stats }: Props) {
  if (stats.filmCount === 0) {
    return (
      <div
        className="rounded-xl p-5"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2 mb-2">
          <Calendar size={14} style={{ color: 'var(--accent-gold)' }} />
          <h3 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
            {stats.year} in review
          </h3>
        </div>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Nothing rated this year yet. The story's still being written.
        </p>
      </div>
    )
  }

  const avgStars = stats.filmCount > 0 ? (stats.totalHalfStars / stats.filmCount).toFixed(1) : '—'

  return (
    <div
      className="rounded-xl p-5 relative overflow-hidden"
      style={{
        background: 'linear-gradient(135deg, rgba(245,197,24,0.08) 0%, var(--bg-card) 50%)',
        border: '1px solid rgba(245,197,24,0.2)',
      }}
    >
      <div className="flex items-center gap-2 mb-4">
        <Calendar size={14} style={{ color: 'var(--accent-gold)' }} />
        <h3 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
          {stats.year} in review
        </h3>
      </div>

      <div className="flex items-baseline gap-2 mb-3">
        <span className="text-4xl font-black text-white">{stats.filmCount}</span>
        <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
          {stats.filmCount === 1 ? 'film' : 'films'} rated · avg {avgStars}★
        </span>
      </div>

      <div className="space-y-2 text-sm">
        {stats.topGenre && (
          <div className="flex items-center gap-2">
            <Film size={12} style={{ color: 'var(--accent-gold)' }} />
            <span style={{ color: 'var(--text-muted)' }}>Most-watched genre:</span>
            <span className="font-semibold text-white">{stats.topGenre}</span>
          </div>
        )}
        {stats.topRating && (
          <div className="flex items-center gap-2">
            <Trophy size={12} style={{ color: 'var(--accent-gold)' }} />
            <span style={{ color: 'var(--text-muted)' }}>Highest rating:</span>
            <span className="font-semibold text-white truncate">{stats.topRating.title}</span>
            {stats.topRating.year && (
              <span style={{ color: 'var(--text-muted)' }}>({stats.topRating.year})</span>
            )}
          </div>
        )}
        {stats.oldestFilm && stats.newestFilm && stats.oldestFilm.year !== stats.newestFilm.year && (
          <div className="flex items-center gap-2 flex-wrap">
            <Calendar size={12} style={{ color: 'var(--accent-gold)' }} />
            <span style={{ color: 'var(--text-muted)' }}>Range:</span>
            <span className="font-semibold text-white">
              {stats.oldestFilm.year} → {stats.newestFilm.year}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

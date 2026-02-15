import type { Recommendation } from '@/lib/api'
import { scoreColor } from '@/lib/utils'

interface MovieRevealProps {
  recommendations: Recommendation[]
}

export function MovieReveal({ recommendations }: MovieRevealProps) {
  return (
    <div className="space-y-2">
      <div className="font-bold text-sm mb-3" style={{ color: 'var(--accent-gold)', fontFamily: 'monospace' }}>
        ✅ Pipeline complete — your picks:
      </div>
      {recommendations.slice(0, 10).map((rec, i) => {
        const pct = Math.round(rec.score * 100)
        const barColor = scoreColor(rec.score)
        const genres = rec.movie.genres?.slice(0, 2).join(', ') ?? ''

        return (
          <div
            key={rec.movie.tmdb_id ?? i}
            className="flex items-center gap-3 rounded-lg px-4 py-3 animate-slide-in"
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              animationDelay: `${i * 0.1}s`,
            }}
          >
            <span
              className="font-bold text-sm w-7 flex-shrink-0 text-center"
              style={{ color: 'var(--accent-gold)' }}
            >
              #{i + 1}
            </span>
            <span className="font-semibold text-sm flex-1 text-white truncate">
              {rec.movie.title}
            </span>
            <span className="text-xs hidden sm:block" style={{ color: 'var(--text-muted)', minWidth: '120px' }}>
              {rec.movie.year ? `${rec.movie.year} · ` : ''}{genres}
            </span>
            <span className="text-xs font-bold flex-shrink-0" style={{ color: barColor }}>
              {pct}%
            </span>
          </div>
        )
      })}
    </div>
  )
}

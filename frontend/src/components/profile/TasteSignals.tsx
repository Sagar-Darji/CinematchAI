import { Clock, Globe2, TrendingUp, TrendingDown } from 'lucide-react'
import type { UserStats } from '@/lib/api'

interface Props {
  stats: UserStats
}

/**
 * Compact strip of numeric "taste signals" — total runtime in hours, foreign
 * cinema %, and how generous the user rates compared to the TMDB crowd.
 * All three come from the persisted-stats compute job.
 */
export function TasteSignals({ stats }: Props) {
  const totalHours = stats.total_runtime_minutes
    ? Math.round(stats.total_runtime_minutes / 60).toLocaleString()
    : null
  const totalDays = stats.total_runtime_minutes
    ? (stats.total_runtime_minutes / 60 / 24).toFixed(1)
    : null
  const foreign = stats.foreign_pct
  const gen = stats.generosity_score ?? 0
  const generosityLabel =
    gen > 0.1
      ? `+${gen.toFixed(1)}★ vs TMDB`
      : gen < -0.1
      ? `${gen.toFixed(1)}★ vs TMDB`
      : 'on consensus'

  return (
    <div className="grid grid-cols-3 gap-3">
      <Signal
        icon={Clock}
        label="Runtime"
        value={totalHours ? `${totalHours}h` : '—'}
        context={totalDays ? `≈ ${totalDays} days of film` : 'no runtime data yet'}
      />
      <Signal
        icon={Globe2}
        label="Foreign cinema"
        value={foreign != null ? `${foreign.toFixed(0)}%` : '—'}
        context={
          foreign >= 30
            ? 'world-cinema fan'
            : foreign >= 10
            ? 'some world cinema'
            : 'mostly English'
        }
      />
      <Signal
        icon={gen >= 0 ? TrendingUp : TrendingDown}
        label="Generosity"
        value={Math.abs(gen) < 0.1 ? '0.0★' : `${gen > 0 ? '+' : ''}${gen.toFixed(1)}★`}
        context={generosityLabel}
      />
    </div>
  )
}

function Signal({
  icon: Icon,
  label,
  value,
  context,
}: {
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>
  label: string
  value: string
  context: string
}) {
  return (
    <div
      className="rounded-2xl p-4"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon size={12} style={{ color: 'var(--accent-gold)' }} />
        <span
          className="text-[10px] font-bold uppercase tracking-widest"
          style={{ color: 'var(--text-muted)' }}
        >
          {label}
        </span>
      </div>
      <p className="text-xl font-black text-white leading-none">{value}</p>
      <p className="text-[11px] mt-1.5 leading-snug" style={{ color: 'var(--text-muted)' }}>
        {context}
      </p>
    </div>
  )
}

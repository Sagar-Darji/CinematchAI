import { Film, Calendar, Gem, Scale, Sparkles, RefreshCw, Loader2 } from 'lucide-react'
import type { UserStats } from '@/lib/api'

interface Props {
  stats: UserStats
  onRegenerate?: () => void
  regenerating?: boolean
}

const ICONS: Record<string, React.ComponentType<{ size?: number; style?: React.CSSProperties }>> = {
  director_loyalty: Film,
  decade_obsession: Calendar,
  hidden_gem: Gem,
  genre_lean: Scale,
}

/**
 * 2x2 grid of quantitative cinephile insights derived from the user's full
 * library + a full-width LLM-generated taste reading. Reads from
 * stats.insights_json and stats.llm_personality (both populated by the
 * persisted-stats compute job).
 */
export function InsightCards({ stats, onRegenerate, regenerating }: Props) {
  const insights = stats.insights_json ?? []
  return (
    <div className="space-y-4">
      {insights.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {insights.map((it) => {
            const Icon = ICONS[it.type] ?? Sparkles
            return (
              <div
                key={it.type}
                className="rounded-2xl p-4"
                style={{
                  background:
                    'linear-gradient(160deg, rgba(245,197,24,0.07) 0%, var(--bg-card) 60%)',
                  border: '1px solid rgba(245,197,24,0.2)',
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon size={14} style={{ color: 'var(--accent-gold)' }} />
                  <span
                    className="text-[10px] font-bold uppercase tracking-widest"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    {it.title}
                  </span>
                </div>
                <p className="text-base font-bold text-white leading-tight truncate">
                  {it.value}
                </p>
                {it.context && (
                  <p
                    className="text-xs mt-1.5 leading-snug"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    {it.context}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}

      {(stats.llm_personality || regenerating) && (
        <div
          className="rounded-2xl p-5 relative"
          style={{
            background:
              'linear-gradient(160deg, rgba(245,197,24,0.04) 0%, var(--bg-card) 100%)',
            border: '1px solid var(--border)',
          }}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Sparkles size={14} style={{ color: 'var(--accent-gold)' }} />
              <h3
                className="text-xs font-bold uppercase tracking-widest"
                style={{ color: 'var(--text-muted)' }}
              >
                Your taste in 4 sentences
              </h3>
            </div>
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                disabled={regenerating}
                aria-label="Regenerate"
                title="Regenerate"
                className="flex items-center gap-1 text-[10px] font-semibold"
                style={{
                  background: 'none',
                  border: 'none',
                  color: regenerating ? 'var(--text-muted)' : 'var(--accent-gold)',
                  cursor: regenerating ? 'wait' : 'pointer',
                  padding: 0,
                }}
              >
                {regenerating ? (
                  <Loader2 size={11} className="animate-spin" />
                ) : (
                  <RefreshCw size={11} />
                )}
                {regenerating ? 'Regenerating…' : 'Regenerate'}
              </button>
            )}
          </div>
          <p
            className="text-sm md:text-[15px] leading-relaxed"
            style={{ color: 'var(--text-primary)', fontStyle: 'italic' }}
          >
            {regenerating && !stats.llm_personality
              ? 'Reading your library…'
              : stats.llm_personality}
          </p>
        </div>
      )}
    </div>
  )
}

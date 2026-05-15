import { Film, Calendar, Gem, Scale, Sparkles, RefreshCw, Loader2 } from 'lucide-react'
import type { UserStats } from '@/lib/api'

interface Props {
  stats: UserStats
  onRegenerate?: () => void
  regenerating?: boolean
}

/** Friendly skeleton shown while the stats worker is computing the user's
 * personality reading + insight tiles for the first time. Matches the
 * final layout. */
export function InsightCardsSkeleton({ message }: { message?: string } = {}) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {[Film, Calendar, Gem, Scale].map((Icon, i) => (
          <div
            key={i}
            className="rounded-2xl p-4"
            style={{
              background:
                'linear-gradient(160deg, rgba(245,197,24,0.04) 0%, var(--bg-card) 60%)',
              border: '1px solid var(--border)',
            }}
          >
            <div className="flex items-center gap-2 mb-2">
              <Icon size={14} style={{ color: 'var(--text-muted)' }} />
              <div className="skeleton-text w-20" style={{ opacity: 0.5 }} />
            </div>
            <div className="skeleton-text mt-1 w-32" style={{ height: '18px' }} />
            <div className="skeleton-text mt-2 w-24" style={{ opacity: 0.45 }} />
          </div>
        ))}
      </div>
      <div
        className="rounded-2xl p-5 flex items-start gap-3"
        style={{
          background:
            'linear-gradient(160deg, rgba(245,197,24,0.04) 0%, var(--bg-card) 100%)',
          border: '1px solid var(--border)',
        }}
      >
        <Sparkles
          size={14}
          style={{ color: 'var(--accent-gold)', marginTop: 2, flexShrink: 0 }}
          className="animate-pulse-glow"
        />
        <div className="flex-1">
          <p
            className="text-[10px] font-bold uppercase tracking-widest mb-2"
            style={{ color: 'var(--text-muted)' }}
          >
            Reading your library…
          </p>
          <p className="text-sm" style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
            {message ?? 'Resolving titles in batches of 200 and writing your taste reading. This takes ~30 seconds on the first visit; instant after that.'}
          </p>
        </div>
      </div>
    </div>
  )
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
          <div className="flex items-center justify-between mb-3 gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <Sparkles size={14} style={{ color: 'var(--accent-gold)', flexShrink: 0 }} />
              <h3
                className="text-xs font-bold uppercase tracking-widest truncate"
                style={{ color: 'var(--text-muted)' }}
              >
                Your taste in 4 sentences
              </h3>
              {/* Subtle inline status: keep the essay visible, just badge
                  that a fresh reading is on its way. */}
              {regenerating && stats.llm_personality && (
                <span
                  className="flex items-center gap-1 text-[10px] font-semibold flex-shrink-0"
                  style={{
                    padding: '2px 8px',
                    borderRadius: '999px',
                    background: 'rgba(245,197,24,0.12)',
                    color: 'var(--accent-gold)',
                    border: '1px solid rgba(245,197,24,0.28)',
                  }}
                >
                  <Loader2 size={9} className="animate-spin" /> Refreshing
                </span>
              )}
            </div>
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                disabled={regenerating}
                aria-label="Regenerate"
                title="Regenerate"
                className="flex items-center gap-1 text-[10px] font-semibold flex-shrink-0"
                style={{
                  background: 'none',
                  border: 'none',
                  color: regenerating ? 'var(--text-muted)' : 'var(--accent-gold)',
                  cursor: regenerating ? 'wait' : 'pointer',
                  padding: 0,
                }}
              >
                <RefreshCw size={11} />
                Regenerate
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

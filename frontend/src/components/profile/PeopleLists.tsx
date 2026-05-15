import { Film, User } from 'lucide-react'
import type { UserStats } from '@/lib/api'

interface Props {
  stats: UserStats
}

export function PeopleListsSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {[Film, User].map((Icon, panelIdx) => (
        <div
          key={panelIdx}
          className="rounded-2xl p-5"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-2 mb-4">
            <Icon size={14} style={{ color: 'var(--text-muted)' }} />
            <div className="skeleton-text w-20" style={{ opacity: 0.5 }} />
          </div>
          <div className="space-y-2.5">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="skeleton-text w-3" style={{ opacity: 0.4 }} />
                <div className="skeleton-text flex-1" style={{ opacity: 0.55 }} />
                <div className="skeleton-text w-6" style={{ opacity: 0.4 }} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/** Side-by-side Top Directors + Top Actors panels, surfaced from
 * stats.top_directors / stats.top_actors which the compute pipeline
 * builds over the user's entire library. */
export function PeopleLists({ stats }: Props) {
  const directors = (stats.top_directors ?? []).slice(0, 8)
  const actors = (stats.top_actors ?? []).slice(0, 8)
  if (directors.length === 0 && actors.length === 0) return null

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {directors.length > 0 && (
        <Panel
          icon={Film}
          title="Top directors"
          rows={directors.map((d, i) => ({
            rank: i + 1,
            name: d.name,
            count: d.count,
            sub: d.avg_rating != null ? `avg ${d.avg_rating.toFixed(1)}★` : undefined,
          }))}
        />
      )}
      {actors.length > 0 && (
        <Panel
          icon={User}
          title="Top actors"
          rows={actors.map((a, i) => ({
            rank: i + 1,
            name: a.name,
            count: a.count,
            sub: undefined,
          }))}
        />
      )}
    </div>
  )
}

function Panel({
  icon: Icon,
  title,
  rows,
}: {
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>
  title: string
  rows: Array<{ rank: number; name: string; count: number; sub?: string }>
}) {
  const max = Math.max(1, ...rows.map((r) => r.count))
  return (
    <div
      className="rounded-2xl p-5"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2 mb-4">
        <Icon size={14} style={{ color: 'var(--accent-gold)' }} />
        <h3
          className="text-xs font-bold uppercase tracking-widest"
          style={{ color: 'var(--text-muted)' }}
        >
          {title}
        </h3>
      </div>
      <div className="space-y-2.5">
        {rows.map((r) => (
          <div key={r.name} className="flex items-center gap-3">
            <span
              className="text-[10px] font-black w-4 text-right flex-shrink-0"
              style={{ color: 'var(--text-muted)' }}
            >
              {r.rank}
            </span>
            <span className="text-sm text-white font-semibold truncate flex-1 min-w-0">
              {r.name}
            </span>
            <div className="flex items-center gap-2 flex-shrink-0">
              <div
                className="rounded-full"
                style={{
                  width: `${Math.max(8, (r.count / max) * 80)}px`,
                  height: '4px',
                  background: 'var(--accent-gold)',
                  opacity: 0.7,
                }}
              />
              <span
                className="text-xs font-bold w-5 text-right"
                style={{ color: 'var(--accent-gold)' }}
              >
                {r.count}
              </span>
              {r.sub && (
                <span
                  className="text-[10px] font-semibold w-16 text-right"
                  style={{ color: 'var(--text-muted)' }}
                >
                  {r.sub}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'

const ALL_AGENTS = [
  { key: 'Profile Analyzer',     icon: '🧠', label: 'Profile Analyzer' },
  { key: 'Context-Aware',        icon: '🌍', label: 'Context-Aware' },
  { key: 'Retrieval',            icon: '🔍', label: 'Retrieval' },
  { key: 'Content Intelligence', icon: '🎯', label: 'Content Intel' },
  { key: 'Serendipity',          icon: '✨', label: 'Serendipity' },
  { key: 'Explanation',          icon: '💬', label: 'Explanation' },
  { key: 'Aggregation',          icon: '📊', label: 'Aggregation' },
]

const TOTAL = ALL_AGENTS.length

interface Step {
  step: string
  detail: string
}

interface TraceDisplayProps {
  steps: Step[]
  runningStep?: string | null
  isComplete?: boolean
}

export function TraceDisplay({ steps, runningStep, isComplete }: TraceDisplayProps) {
  const completedSet = new Set(steps.map((s) => s.step))
  const [visibleCount, setVisibleCount] = useState(0)

  // Cascade: each new completed step appears after a short delay
  useEffect(() => {
    if (steps.length > visibleCount) {
      const t = setTimeout(() => setVisibleCount((n) => n + 1), 110)
      return () => clearTimeout(t)
    }
  }, [steps.length, visibleCount])

  const done = completedSet.size
  const progressPct = isComplete ? 100 : Math.round((done / TOTAL) * 100)

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      {/* Header with progress */}
      <div
        className="px-5 py-3.5 border-b"
        style={{ borderColor: 'var(--border)', background: 'var(--bg-overlay)' }}
      >
        <div className="flex items-center justify-between mb-2.5">
          <span className="text-sm font-black tracking-wide" style={{ color: 'var(--accent-gold)' }}>
            {isComplete ? 'Pipeline complete' : 'AI pipeline running'}
          </span>
          <span className="text-xs font-bold tabular-nums" style={{ color: isComplete ? 'var(--accent-gold)' : 'var(--text-muted)' }}>
            {done} / {TOTAL}
          </span>
        </div>

        {/* Progress bar */}
        <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
          <div
            className="h-full rounded-full"
            style={{
              width: `${progressPct}%`,
              background: isComplete
                ? 'var(--accent-gold)'
                : 'linear-gradient(90deg, var(--accent-gold) 0%, #fde68a 100%)',
              transition: 'width 0.5s cubic-bezier(0.4,0,0.2,1)',
              boxShadow: progressPct > 0 ? '0 0 8px rgba(245,197,24,0.4)' : 'none',
            }}
          />
        </div>

        {/* Pulsing dots while running */}
        {!isComplete && (
          <div className="flex gap-1 mt-2">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="w-1.5 h-1.5 rounded-full inline-block"
                style={{
                  background: 'var(--accent-gold)',
                  animation: `pulseGlow 1.2s ease-in-out ${i * 0.2}s infinite`,
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Steps list */}
      <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
        {ALL_AGENTS.map(({ key, icon, label }, idx) => {
          const isCompleted = completedSet.has(key)
          const isRunning = key === runningStep
          const detail = steps.find((s) => s.step === key)?.detail
          // Show step only after its cascade delay
          const revealed = isCompleted || isRunning || idx < visibleCount + (isRunning ? 1 : 0) || idx <= done

          return (
            <div
              key={key}
              className="flex items-start gap-4 px-5 py-3"
              style={{
                opacity: revealed ? 1 : 0.15,
                transition: 'opacity 0.25s ease',
                background: isRunning ? 'rgba(245,197,24,0.04)' : 'transparent',
              }}
            >
              {/* Icon / status */}
              <div className="mt-0.5 w-5 flex-shrink-0 text-center">
                {isCompleted ? (
                  <span className="text-base leading-none">{icon}</span>
                ) : isRunning ? (
                  <span
                    className="text-base leading-none inline-block"
                    style={{ animation: 'pulseGlow 0.9s ease-in-out infinite' }}
                  >⚙️</span>
                ) : (
                  <span
                    className="block w-3.5 h-3.5 rounded-full border-2 mx-auto mt-0.5"
                    style={{ borderColor: 'var(--border-hover)' }}
                  />
                )}
              </div>

              {/* Label + detail */}
              <div className="flex-1 min-w-0">
                <p
                  className="text-sm font-semibold leading-snug"
                  style={{
                    color: isCompleted
                      ? 'var(--text-primary)'
                      : isRunning
                      ? 'var(--accent-gold)'
                      : 'var(--text-muted)',
                  }}
                >
                  {label}
                </p>
                {isCompleted && detail && (
                  <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                    {detail}
                  </p>
                )}
                {isRunning && (
                  <p className="text-xs mt-0.5" style={{ color: 'var(--accent-gold)', opacity: 0.65 }}>
                    processing…
                  </p>
                )}
              </div>

              {/* Checkmark */}
              {isCompleted && (
                <span className="text-xs font-bold mt-0.5 flex-shrink-0" style={{ color: 'var(--accent-gold)' }}>✓</span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

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
  const [visibleSteps, setVisibleSteps] = useState(0)

  // Reveal completed steps one at a time for a cascading effect
  useEffect(() => {
    if (steps.length > visibleSteps) {
      const t = setTimeout(() => setVisibleSteps((n) => n + 1), 120)
      return () => clearTimeout(t)
    }
  }, [steps.length, visibleSteps])

  const shownCount = Math.max(visibleSteps, steps.length)

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      {/* Header bar */}
      <div
        className="flex items-center gap-2.5 px-5 py-3.5 border-b"
        style={{ borderColor: 'var(--border)', background: 'var(--bg-overlay)' }}
      >
        <span className="text-sm font-black tracking-wide" style={{ color: 'var(--accent-gold)' }}>
          {isComplete ? 'Pipeline complete' : 'AI pipeline running'}
        </span>
        {!isComplete && (
          <span className="flex gap-1 ml-auto">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  background: 'var(--accent-gold)',
                  animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                  opacity: 0.6,
                }}
              />
            ))}
          </span>
        )}
        {isComplete && <span className="ml-auto text-xs" style={{ color: 'var(--text-muted)' }}>✓ done</span>}
      </div>

      {/* Steps list */}
      <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
        {ALL_AGENTS.map(({ key, icon, label }, idx) => {
          const isCompleted = completedSet.has(key)
          const isRunning = key === runningStep
          const detail = steps.find((s) => s.step === key)?.detail
          const shouldShow = isCompleted || isRunning || idx <= shownCount

          return (
            <div
              key={key}
              className="flex items-start gap-4 px-5 py-3 transition-all duration-300"
              style={{
                opacity: !shouldShow ? 0.18 : 1,
                background: isRunning ? 'rgba(245,197,24,0.04)' : 'transparent',
              }}
            >
              {/* Status dot */}
              <div className="mt-0.5 flex-shrink-0">
                {isCompleted ? (
                  <span className="text-base">{icon}</span>
                ) : isRunning ? (
                  <span className="text-base" style={{ animation: 'pulse 1s ease-in-out infinite' }}>⚙️</span>
                ) : (
                  <span
                    className="block w-4 h-4 rounded-full border-2 mt-0.5"
                    style={{ borderColor: 'var(--border)' }}
                  />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p
                  className="text-sm font-semibold leading-snug"
                  style={{
                    color: isCompleted ? 'var(--text-primary)' : isRunning ? 'var(--accent-gold)' : 'var(--text-muted)',
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
                  <p className="text-xs mt-0.5" style={{ color: 'var(--accent-gold)', opacity: 0.7 }}>
                    processing…
                  </p>
                )}
              </div>

              {/* Right indicator */}
              {isCompleted && (
                <span className="text-xs font-bold flex-shrink-0 mt-0.5" style={{ color: 'var(--accent-gold)' }}>✓</span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

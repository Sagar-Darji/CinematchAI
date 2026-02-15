import { cn } from '@/lib/utils'

const ALL_AGENTS = [
  { key: 'Profile Analyzer',     icon: '🧠' },
  { key: 'Context-Aware',        icon: '🌍' },
  { key: 'Retrieval',            icon: '🔍' },
  { key: 'Content Intelligence', icon: '🎯' },
  { key: 'Serendipity',          icon: '✨' },
  { key: 'Explanation',          icon: '💬' },
  { key: 'Aggregation',          icon: '📊' },
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

  return (
    <div
      className="rounded-xl p-5 font-mono text-sm"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="font-bold text-sm mb-4" style={{ color: 'var(--accent-gold)' }}>
        {isComplete ? '✅ Pipeline complete — your picks:' : '🎬 CineMatch is thinking…'}
      </div>

      <div className="space-y-2">
        {ALL_AGENTS.map(({ key, icon }) => {
          const isCompleted = completedSet.has(key)
          const isRunning = key === runningStep
          const detail = steps.find((s) => s.step === key)?.detail

          return (
            <div
              key={key}
              className={cn(
                'flex items-baseline gap-3',
                isRunning && 'animate-pulse-glow',
                !isCompleted && !isRunning && 'opacity-25',
              )}
            >
              <span className="text-base w-5 flex-shrink-0">
                {isCompleted ? icon : isRunning ? '⚙️' : '○'}
              </span>
              <span
                className="font-semibold"
                style={{
                  color: isCompleted ? 'var(--accent-gold)' : isRunning ? '#ffffff' : 'var(--text-muted)',
                  minWidth: '160px',
                }}
              >
                {key}
              </span>
              <span className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
                {isCompleted && detail ? `— ${detail}` : isRunning ? '— processing…' : ''}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

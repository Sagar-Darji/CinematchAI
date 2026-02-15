import { useEffect, useRef, useState } from 'react'

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

interface Step { step: string; detail: string }

interface TraceDisplayProps {
  steps: Step[]
  runningStep?: string | null
  isComplete?: boolean
}

// Typewriter hook — types detail text character by character when a step completes
function useTypewriter(text: string, active: boolean) {
  const [displayed, setDisplayed] = useState('')
  const ref = useRef(0)

  useEffect(() => {
    if (!active || !text) { setDisplayed(text); return }
    setDisplayed('')
    ref.current = 0
    const t = setInterval(() => {
      ref.current += 1
      setDisplayed(text.slice(0, ref.current))
      if (ref.current >= text.length) clearInterval(t)
    }, 16)
    return () => clearInterval(t)
  }, [text, active])

  return { displayed, typing: displayed.length < text.length }
}

function StepRow({ icon, label, isCompleted, isRunning, detail, revealed, index }: {
  icon: string; label: string
  isCompleted: boolean; isRunning: boolean
  detail?: string; revealed: boolean; index: number
}) {
  const { displayed, typing } = useTypewriter(detail ?? '', isCompleted && !!detail)

  return (
    <div
      className={revealed ? 'animate-step-in' : ''}
      style={{
        opacity: revealed ? 1 : 0.1,
        animationDelay: `${index * 0.05}s`,
        display: 'flex', alignItems: 'flex-start', gap: '14px',
        padding: '10px 20px',
        borderBottom: '1px solid var(--border)',
        background: isRunning ? 'rgba(245,197,24,0.04)' : 'transparent',
      }}
    >
      <div style={{ marginTop: '2px', width: '20px', flexShrink: 0, textAlign: 'center' }}>
        {isCompleted ? (
          <span style={{ fontSize: '15px', lineHeight: 1 }}>{icon}</span>
        ) : isRunning ? (
          <span style={{ fontSize: '15px', lineHeight: 1, display: 'inline-block', animation: 'pulseGlow 0.9s ease-in-out infinite' }}>⚙️</span>
        ) : (
          <span style={{ display: 'block', width: '12px', height: '12px', borderRadius: '50%', border: '2px solid var(--border-hover)', margin: '2px auto 0' }} />
        )}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{
          fontSize: '14px', fontWeight: 600, lineHeight: 1.3,
          color: isCompleted ? 'var(--text-primary)' : isRunning ? 'var(--accent-gold)' : 'var(--text-muted)',
        }}>
          {label}
        </p>

        {isCompleted && detail && (
          <p style={{ fontSize: '11px', marginTop: '2px', lineHeight: 1.5, color: 'var(--text-muted)' }}>
            {displayed}
            {typing && <span className="cursor-blink" style={{ color: 'var(--accent-gold)' }}>▌</span>}
          </p>
        )}

        {isRunning && (
          <p style={{ fontSize: '11px', marginTop: '2px', color: 'var(--accent-gold)', opacity: 0.7 }}>
            processing<span className="cursor-blink">…</span>
          </p>
        )}
      </div>

      {isCompleted && (
        <span style={{ fontSize: '11px', fontWeight: 700, marginTop: '2px', flexShrink: 0, color: 'var(--accent-gold)' }}>✓</span>
      )}
    </div>
  )
}

export function TraceDisplay({ steps, runningStep, isComplete }: TraceDisplayProps) {
  const completedSet = new Set(steps.map((s) => s.step))
  const [visibleCount, setVisibleCount] = useState(0)

  useEffect(() => {
    if (steps.length > visibleCount) {
      const t = setTimeout(() => setVisibleCount((n) => n + 1), 100)
      return () => clearTimeout(t)
    }
  }, [steps.length, visibleCount])

  const done = completedSet.size
  const progressPct = isComplete ? 100 : Math.round((done / TOTAL) * 100)

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      {/* Header */}
      <div className="px-5 py-3.5 border-b" style={{ borderColor: 'var(--border)', background: 'var(--bg-overlay)' }}>
        <div className="flex items-center justify-between mb-2.5">
          <span className="text-sm font-black tracking-wide" style={{ color: 'var(--accent-gold)' }}>
            {isComplete ? 'Pipeline complete' : 'AI pipeline running'}
          </span>
          <span className="text-xs font-bold tabular-nums" style={{ color: isComplete ? 'var(--accent-gold)' : 'var(--text-muted)' }}>
            {done} / {TOTAL}
          </span>
        </div>

        <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
          <div className="h-full rounded-full" style={{
            width: `${progressPct}%`,
            background: isComplete ? 'var(--accent-gold)' : 'linear-gradient(90deg,var(--accent-gold),#fde68a)',
            transition: 'width 0.5s cubic-bezier(0.4,0,0.2,1)',
            boxShadow: progressPct > 0 ? '0 0 8px rgba(245,197,24,0.45)' : 'none',
          }} />
        </div>

        {!isComplete && (
          <div className="flex gap-1 mt-2">
            {[0, 1, 2].map((i) => (
              <span key={i} className="w-1.5 h-1.5 rounded-full inline-block"
                style={{ background: 'var(--accent-gold)', animation: `pulseGlow 1.2s ease-in-out ${i * 0.2}s infinite` }} />
            ))}
          </div>
        )}
      </div>

      {/* Steps */}
      <div>
        {ALL_AGENTS.map(({ key, icon, label }, idx) => {
          const isCompleted = completedSet.has(key)
          const isRunning = key === runningStep
          const detail = steps.find((s) => s.step === key)?.detail
          const revealed = isCompleted || isRunning || idx <= done

          return (
            <StepRow
              key={key} icon={icon} label={label}
              isCompleted={isCompleted} isRunning={isRunning}
              detail={detail} revealed={revealed} index={idx}
            />
          )
        })}
      </div>
    </div>
  )
}

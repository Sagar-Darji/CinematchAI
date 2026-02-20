import { useEffect, useRef, useState } from 'react'

// ── Agent registry ────────────────────────────────────────────────────────────
const ALL_AGENTS = [
  { key: 'Profile Analyzer',     icon: '🧠', label: 'Profile Analyzer',     accent: '#a855f7' },
  { key: 'Context-Aware',        icon: '🌍', label: 'Context-Aware',        accent: '#3b82f6' },
  { key: 'Retrieval',            icon: '🔍', label: 'Retrieval',            accent: '#06b6d4' },
  { key: 'Content Intelligence', icon: '🎯', label: 'Content Intelligence', accent: '#f59e0b' },
  { key: 'Serendipity',          icon: '✨', label: 'Serendipity',          accent: '#10b981' },
  { key: 'Adversarial Critic',   icon: '⚖️', label: 'Adversarial Critic',   accent: '#ef4444' },
  { key: 'Explanation',          icon: '💬', label: 'Explanation',          accent: '#8b5cf6' },
  { key: 'Aggregation',          icon: '📊', label: 'Aggregation',          accent: '#f5c518' },
]
const TOTAL = ALL_AGENTS.length
const BRIEF_MS = 2400 // how long a newly-completed step stays expanded

// ── Detail parsing ────────────────────────────────────────────────────────────
interface ParsedDetail {
  text: string
  considered?: string[]
  selected?: string[]
  rejected?: string[]
  approved?: string[]
  exploration?: string[]
}

function parseDetail(raw: string | undefined): ParsedDetail {
  if (!raw) return { text: '' }
  if (raw.startsWith('{')) {
    try { return JSON.parse(raw) as ParsedDetail } catch { /* fall through */ }
  }
  return { text: raw }
}

// ── Typewriter — once text is fully shown it never restarts ───────────────────
function useTypewriter(text: string, active: boolean) {
  const [displayed, setDisplayed] = useState('')
  const idxRef = useRef(0)

  useEffect(() => {
    if (!text) { setDisplayed(''); return }
    // If not active OR already reached end: show immediately
    if (!active || idxRef.current >= text.length) {
      setDisplayed(text)
      idxRef.current = text.length
      return
    }
    idxRef.current = 0
    setDisplayed('')
    const t = setInterval(() => {
      idxRef.current += 1
      setDisplayed(text.slice(0, idxRef.current))
      if (idxRef.current >= text.length) clearInterval(t)
    }, 14)
    return () => clearInterval(t)
  }, [text, active])

  return { displayed, done: displayed.length >= text.length }
}

// ── Movie pill group ──────────────────────────────────────────────────────────
type PillVariant = 'considered' | 'selected' | 'rejected' | 'approved' | 'exploration'

const PILL: Record<PillVariant, { bg: string; border: string; color: string; prefix: string; line?: boolean }> = {
  considered:  { bg: 'rgba(255,255,255,0.04)', border: 'rgba(255,255,255,0.10)', color: 'rgba(255,255,255,0.38)', prefix: '' },
  selected:    { bg: 'rgba(245,197,24,0.13)',  border: 'rgba(245,197,24,0.36)',  color: '#f5c518',               prefix: '✓ ' },
  approved:    { bg: 'rgba(245,197,24,0.13)',  border: 'rgba(245,197,24,0.36)',  color: '#f5c518',               prefix: '✓ ' },
  rejected:    { bg: 'rgba(239,68,68,0.10)',   border: 'rgba(239,68,68,0.28)',   color: '#f87171',               prefix: '✗ ', line: true },
  exploration: { bg: 'rgba(6,182,212,0.10)',   border: 'rgba(6,182,212,0.28)',   color: '#22d3ee',               prefix: '✦ ' },
}

function PillGroup({ titles, variant, delay = 0, max = 10 }: {
  titles: string[]; variant: PillVariant; delay?: number; max?: number
}) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (delay === 0) { setVisible(true); return }
    const t = setTimeout(() => setVisible(true), delay)
    return () => clearTimeout(t)
  }, [delay]) // when delay → 0 the cleanup clears old timer and shows immediately

  if (!titles.length) return null
  const s = PILL[variant]
  const shown = titles.slice(0, max)
  const extra = titles.length - shown.length

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '5px' }}>
      {shown.map((title, i) => (
        <span key={i} style={{
          display: 'inline-flex', alignItems: 'center',
          padding: '2px 8px', borderRadius: '999px',
          fontSize: '10px', fontWeight: 600, letterSpacing: '0.01em',
          background: s.bg, border: `1px solid ${s.border}`, color: s.color,
          textDecoration: s.line ? 'line-through' : 'none',
          maxWidth: '148px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          opacity: visible ? 1 : 0,
          transform: visible ? 'translateY(0) scale(1)' : 'translateY(5px) scale(0.88)',
          transition: `opacity 0.2s ease ${i * 0.04}s, transform 0.2s ease ${i * 0.04}s`,
        }}>
          {s.prefix}{title}
        </span>
      ))}
      {extra > 0 && (
        <span style={{
          padding: '2px 7px', borderRadius: '999px', fontSize: '10px',
          fontWeight: 600, color: 'var(--text-muted)',
          opacity: visible ? 0.65 : 0,
          transition: `opacity 0.2s ease ${shown.length * 0.04}s`,
        }}>+{extra}</span>
      )}
    </div>
  )
}

// ── Inline mini pills shown in collapsed header ───────────────────────────────
function MiniPills({ parsed, accent }: { parsed: ParsedDetail; accent: string }) {
  const titles = [
    ...(parsed.selected  || []),
    ...(parsed.approved  || []),
    ...(parsed.considered || []),
  ].slice(0, 3)

  if (!titles.length) return null

  return (
    <>
      {titles.map((t, i) => (
        <span key={i} style={{
          padding: '1px 6px', borderRadius: '999px', fontSize: '9px', fontWeight: 600,
          background: `${accent}15`, border: `1px solid ${accent}32`, color: accent,
          maxWidth: '72px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          flexShrink: 0,
        }}>{t}</span>
      ))}
      {([...(parsed.selected || []), ...(parsed.approved || []), ...(parsed.considered || [])].length > 3) && (
        <span style={{ fontSize: '9px', color: 'var(--text-muted)', flexShrink: 0 }}>
          +{[...(parsed.selected || []), ...(parsed.approved || []), ...(parsed.considered || [])].length - 3}
        </span>
      )}
    </>
  )
}

// ── Single step row ───────────────────────────────────────────────────────────
function StepRow({
  icon, label, accent, isCompleted, isRunning, rawDetail,
  isExpanded, isBriefExpanded, onToggle, revealed, index,
}: {
  icon: string; label: string; accent: string
  isCompleted: boolean; isRunning: boolean; rawDetail?: string
  isExpanded: boolean; isBriefExpanded: boolean
  onToggle: () => void; revealed: boolean; index: number
}) {
  const parsed = parseDetail(rawDetail)

  // Typewriter: run only when expanded normally (not brief mode, not collapsed)
  const twActive = isCompleted && !!parsed.text && isExpanded && !isBriefExpanded
  const { displayed, done: twDone } = useTypewriter(parsed.text, twActive)
  const shownText = isBriefExpanded ? parsed.text : displayed
  const textReady = isBriefExpanded ? true : twDone

  // Pills: delay 0 in brief mode (immediate), else after typewriter
  const pillDelay = isBriefExpanded ? 0 : (parsed.text.length * 14 + 60)
  const selectedTitles = [...(parsed.selected || []), ...(parsed.approved || [])]

  return (
    <div
      onClick={isCompleted ? onToggle : undefined}
      style={{
        cursor: isCompleted ? 'pointer' : 'default',
        borderBottom: '1px solid var(--border)',
        background: isRunning ? `linear-gradient(90deg, ${accent}0d 0%, transparent 65%)` : 'transparent',
        opacity: revealed ? 1 : 0.12,
        transform: revealed ? 'translateX(0)' : 'translateX(-8px)',
        transition: `opacity 0.28s ease ${index * 0.05}s, transform 0.28s ease ${index * 0.05}s, background 0.3s`,
        position: 'relative', overflow: 'hidden',
      }}
    >
      {/* Accent bar */}
      {(isCompleted || isRunning) && (
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0, width: '2px',
          background: isRunning
            ? `linear-gradient(180deg, ${accent} 0%, transparent 100%)`
            : accent,
          opacity: isRunning ? 1 : 0.45,
          transition: 'opacity 0.3s',
        }} />
      )}

      {/* ── Header row (always visible) ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '9px',
        padding: '8px 14px 8px 16px', minHeight: '38px',
      }}>

        {/* Status icon */}
        <div style={{ width: '18px', flexShrink: 0, display: 'flex', justifyContent: 'center' }}>
          {isCompleted ? (
            <span style={{ fontSize: '13px', lineHeight: 1 }}>{icon}</span>
          ) : isRunning ? (
            <span style={{
              fontSize: '13px', lineHeight: 1, display: 'inline-block',
              animation: 'traceSpin 1.3s linear infinite',
            }}>⚙️</span>
          ) : (
            <span style={{
              display: 'block', width: '8px', height: '8px',
              borderRadius: '50%', border: '1.5px solid var(--border)',
            }} />
          )}
        </div>

        {/* Label */}
        <span style={{
          fontSize: '12px', fontWeight: 700, flexShrink: 0,
          color: isRunning ? accent : isCompleted ? 'var(--text-primary)' : 'var(--text-muted)',
          transition: 'color 0.25s',
        }}>{label}</span>

        {/* Running badge */}
        {isRunning && (
          <span style={{
            fontSize: '8px', fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase',
            color: accent, background: `${accent}1c`, border: `1px solid ${accent}40`,
            padding: '1px 5px', borderRadius: '3px', flexShrink: 0,
            animation: 'tracePulse 1.15s ease-in-out infinite',
          }}>live</span>
        )}

        {/* Spacer */}
        <div style={{ flex: 1, minWidth: 0, overflow: 'hidden' }} />

        {/* Inline mini pills (collapsed completed) */}
        {isCompleted && !isExpanded && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', overflow: 'hidden', maxWidth: '190px', flexShrink: 1 }}>
            <MiniPills parsed={parsed} accent={accent} />
          </div>
        )}

        {/* Checkmark + chevron */}
        {isCompleted && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0, marginLeft: '6px' }}>
            <span style={{ fontSize: '9px', color: accent, opacity: 0.8 }}>✓</span>
            <span style={{
              fontSize: '10px', color: 'var(--text-muted)', display: 'inline-block',
              transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.22s ease',
              lineHeight: 1,
            }}>▾</span>
          </div>
        )}
      </div>

      {/* ── Expandable body ── */}
      <div style={{
        maxHeight: isExpanded ? '380px' : '0px',
        overflow: 'hidden',
        transition: 'max-height 0.32s cubic-bezier(0.4, 0, 0.2, 1)',
      }}>
        <div style={{ padding: '0 14px 11px 43px' }}>

          {/* Detail text */}
          {isCompleted && shownText && (
            <p style={{ fontSize: '11px', lineHeight: 1.6, color: 'var(--text-muted)', marginBottom: '2px' }}>
              {shownText}
              {!textReady && (
                <span style={{ color: accent, animation: 'traceBlink 0.7s step-end infinite' }}>▌</span>
              )}
            </p>
          )}

          {/* Running message */}
          {isRunning && (
            <p style={{ fontSize: '11px', color: accent, opacity: 0.6, marginBottom: '2px' }}>
              analyzing<span style={{ animation: 'traceBlink 0.9s step-end infinite' }}>…</span>
            </p>
          )}

          {/* Movie pills — show once text is ready */}
          {isCompleted && textReady && (
            <>
              {/* Considered: only if no selected/rejected */}
              {parsed.considered && !selectedTitles.length && !parsed.rejected?.length && (
                <PillGroup titles={parsed.considered} variant="considered" delay={pillDelay} max={8} />
              )}
              {selectedTitles.length > 0 && (
                <PillGroup titles={selectedTitles} variant="selected" delay={pillDelay} />
              )}
              {(parsed.rejected?.length ?? 0) > 0 && (
                <PillGroup titles={parsed.rejected!} variant="rejected" delay={isBriefExpanded ? 60 : pillDelay + 100} />
              )}
              {(parsed.exploration?.length ?? 0) > 0 && (
                <PillGroup titles={parsed.exploration!} variant="exploration" delay={isBriefExpanded ? 30 : pillDelay + 60} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
interface Step { step: string; detail: string }

interface TraceDisplayProps {
  steps: Step[]
  runningStep?: string | null
  isComplete?: boolean
}

export function TraceDisplay({ steps, runningStep, isComplete }: TraceDisplayProps) {
  const completedSet = new Set(steps.map((s) => s.step))
  const done = completedSet.size
  const progressPct = isComplete ? 100 : Math.round((done / TOTAL) * 100)

  // Brief auto-expand: newly completed steps stay open for BRIEF_MS then collapse
  const [briefExpanded, setBriefExpanded] = useState<Set<string>>(new Set())
  const prevRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    const newKeys = steps.map((s) => s.step).filter((k) => !prevRef.current.has(k))
    if (!newKeys.length) return
    setBriefExpanded((prev) => new Set([...prev, ...newKeys]))
    newKeys.forEach((key) => {
      setTimeout(() => {
        setBriefExpanded((prev) => { const n = new Set(prev); n.delete(key); return n })
      }, BRIEF_MS)
    })
    prevRef.current = new Set(steps.map((s) => s.step))
  }, [steps])

  // User-controlled expansions
  const [userExpanded, setUserExpanded] = useState<Set<string>>(new Set())
  const toggle = (key: string) =>
    setUserExpanded((prev) => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n })

  return (
    <>
      <style>{`
        @keyframes traceSpin  { to { transform: rotate(360deg); } }
        @keyframes tracePulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
        @keyframes traceBlink { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes traceBeam  { 0%{transform:translateX(-100%)} 100%{transform:translateX(400%)} }
      `}</style>

      <div style={{
        borderRadius: '14px', overflow: 'hidden',
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        boxShadow: isComplete
          ? '0 0 0 1px rgba(245,197,24,0.18), 0 4px 28px rgba(0,0,0,0.35)'
          : '0 4px 20px rgba(0,0,0,0.25)',
        transition: 'box-shadow 0.5s',
      }}>

        {/* ── Header ── */}
        <div style={{
          padding: '11px 16px', borderBottom: '1px solid var(--border)',
          background: 'var(--bg-overlay)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '7px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
              <span style={{ fontSize: '13px' }}>🎬</span>
              <span style={{
                fontSize: '11px', fontWeight: 800, letterSpacing: '0.09em',
                textTransform: 'uppercase', color: 'var(--accent-gold)',
              }}>
                {isComplete ? 'Pipeline Complete' : 'AI Pipeline'}
              </span>
            </div>
            <span style={{
              fontSize: '10px', fontWeight: 700,
              color: isComplete ? 'var(--accent-gold)' : 'var(--text-muted)',
            }}>
              {done}/{TOTAL}
            </span>
          </div>

          {/* Progress bar */}
          <div style={{
            height: '3px', borderRadius: '99px', overflow: 'hidden',
            background: 'rgba(255,255,255,0.06)', position: 'relative',
          }}>
            <div style={{
              height: '100%', borderRadius: '99px',
              width: `${progressPct}%`,
              background: isComplete ? 'var(--accent-gold)' : 'linear-gradient(90deg, #f5c518, #fde68a)',
              boxShadow: progressPct > 0 ? '0 0 8px rgba(245,197,24,0.5)' : 'none',
              transition: 'width 0.5s cubic-bezier(0.4,0,0.2,1)',
              position: 'relative', overflow: 'hidden',
            }}>
              {!isComplete && progressPct > 0 && (
                <div style={{
                  position: 'absolute', inset: 0, width: '30%',
                  background: 'linear-gradient(90deg,transparent,rgba(255,255,255,0.55),transparent)',
                  animation: 'traceBeam 1.8s ease-in-out infinite',
                }} />
              )}
            </div>
          </div>

          {/* Active step label */}
          {!isComplete && runningStep && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginTop: '6px' }}>
              {[0, 1, 2].map((i) => (
                <span key={i} style={{
                  width: '4px', height: '4px', borderRadius: '50%',
                  background: 'var(--accent-gold)', display: 'inline-block',
                  animation: `tracePulse 1.3s ease-in-out ${i * 0.18}s infinite`,
                }} />
              ))}
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 600, marginLeft: '3px' }}>
                {runningStep}
              </span>
            </div>
          )}
        </div>

        {/* ── Steps ── */}
        <div>
          {ALL_AGENTS.map(({ key, icon, label, accent }, idx) => {
            const isCompleted = completedSet.has(key)
            const isRunning = key === runningStep
            const rawDetail = steps.find((s) => s.step === key)?.detail
            const revealed = isCompleted || isRunning || idx <= done
            const isBriefExpanded = briefExpanded.has(key)
            const isExpanded = isRunning || isBriefExpanded || userExpanded.has(key)

            return (
              <StepRow
                key={key}
                icon={icon} label={label} accent={accent}
                isCompleted={isCompleted} isRunning={isRunning}
                rawDetail={rawDetail}
                isExpanded={isExpanded} isBriefExpanded={isBriefExpanded}
                onToggle={() => toggle(key)}
                revealed={revealed} index={idx}
              />
            )
          })}
        </div>

        {/* ── Complete footer ── */}
        {isComplete && (
          <div style={{
            padding: '9px 16px', borderTop: '1px solid var(--border)',
            background: 'rgba(245,197,24,0.04)',
            display: 'flex', alignItems: 'center', gap: '6px',
          }}>
            <span style={{ fontSize: '11px' }}>🎉</span>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-gold)' }}>
              Recommendations ready · tap any step to expand
            </span>
          </div>
        )}
      </div>
    </>
  )
}

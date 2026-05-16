/**
 * Full-screen reading view for the long-form taste-as-personality essay.
 * Renders the four sections produced by the layered Groq generation:
 *   - Longitudinal arc (3 paragraphs: who you were, how taste shifted,
 *     what it says about you now)
 *   - Dense paragraph (synthesis)
 *   - Letter (stylized, second-person)
 *   - Quarterly journal entries
 *
 * Layout: centered modal up to 720px wide / 90vh tall with internal
 * scroll, fixed close button in the modal's top-right corner. On
 * narrow viewports the modal expands to fill the screen so the body
 * copy remains readable without horizontal overflow.
 */
import { useEffect } from 'react'
import { X } from 'lucide-react'
import type { ProfilePersonality } from '@/lib/api'

interface Props {
  personality: ProfilePersonality
  onClose: () => void
}

/**
 * Older personality blobs (computed before today's normalizer fix) can
 * arrive shaped like "{'text': 'paragraph body'}" — a Python dict repr
 * that leaked through when the LLM wrapped each entry instead of
 * returning bare strings. Strip that wrapper at render time so users
 * see clean prose without waiting for a recompute.
 */
function unwrapText(s: string): string {
  if (!s) return s
  const t = s.trim()
  // Python repr: {'text': '...'} / {'paragraph': '...'} / {'content': '...'}
  const m = t.match(/^\{\s*['"](?:text|paragraph|content|body|value)['"]\s*:\s*['"]([\s\S]*)['"]\s*\}$/)
  if (m) return m[1].replace(/\\'/g, "'").replace(/\\"/g, '"').trim()
  // JSON repr — same shape but with proper JSON quoting.
  if (t.startsWith('{') && t.endsWith('}')) {
    try {
      const parsed = JSON.parse(t)
      if (parsed && typeof parsed === 'object') {
        for (const k of ['text', 'paragraph', 'content', 'body', 'value']) {
          if (typeof parsed[k] === 'string' && parsed[k].trim()) return parsed[k].trim()
        }
      }
    } catch { /* fall through */ }
  }
  return s
}

export function PersonalityModal({ personality, onClose }: Props) {
  // Escape-to-close + lock body scroll while open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  const lf = personality.longform
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Your taste essay"
      className="fixed inset-0 z-50 flex items-center justify-center p-0 sm:p-4 md:p-8"
      style={{
        background: 'rgba(0,0,0,0.80)',
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
      }}
      onClick={onClose}
    >
      <style>{`
        .modal-shell { height: 100dvh; max-height: 100dvh; }
        @media (min-width: 640px) { .modal-shell { height: 90dvh; max-height: 90dvh; } }
      `}</style>
      <div
        className="relative w-full sm:max-w-2xl md:max-w-3xl rounded-none sm:rounded-2xl flex flex-col modal-shell"
        style={{
          // Mostly opaque dark surface with a hint of translucency so
          // the page behind shows as a soft blur through the modal
          // glass — substantial enough to read against, transparent
          // enough to feel like a layer.
          background: 'rgba(18, 18, 26, 0.92)',
          border: '1px solid var(--border)',
          boxShadow: '0 20px 60px rgba(0,0,0,0.55)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Fixed header so the close button never drifts off-screen. */}
        <div
          className="flex items-center justify-between gap-3 px-5 sm:px-8 py-4 flex-shrink-0"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <h2 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
            Your taste essay
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex items-center justify-center w-9 h-9 rounded-full flex-shrink-0"
            style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable body — single overflow container, never pushes the
            modal past the viewport. */}
        <div className="overflow-y-auto px-5 sm:px-8 md:px-10 py-8 space-y-10">
          {personality.teaser && (
            <section>
              <p className="text-base sm:text-lg leading-relaxed text-white">
                {unwrapText(personality.teaser)}
              </p>
            </section>
          )}
          {lf.longitudinal_arc.length > 0 && (
            <Section title="Where you've been">
              {lf.longitudinal_arc.map((para, i) => (
                <p key={i} className="text-[15px] leading-relaxed">{unwrapText(para)}</p>
              ))}
            </Section>
          )}
          {lf.dense_paragraph && (
            <Section title="The synthesis">
              <p className="text-[15px] leading-relaxed">{unwrapText(lf.dense_paragraph)}</p>
            </Section>
          )}
          {lf.letter && (
            <Section title="A letter">
              <p className="text-[15px] leading-relaxed whitespace-pre-line">
                {unwrapText(lf.letter)}
              </p>
            </Section>
          )}
          {lf.quarterly_entries.length > 0 && (
            <Section title="Quarterly journal">
              <ul className="space-y-5">
                {lf.quarterly_entries.map((q, i) => (
                  <li key={i}>
                    <div className="text-xs uppercase tracking-widest mb-1" style={{ color: 'var(--accent-gold)' }}>
                      {q.quarter}
                    </div>
                    <p className="text-[15px] leading-relaxed">{unwrapText(q.text)}</p>
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </div>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3" style={{ color: 'var(--text-muted)' }}>
      <h3 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
        {title}
      </h3>
      <div className="text-white space-y-3 break-words">{children}</div>
    </section>
  )
}

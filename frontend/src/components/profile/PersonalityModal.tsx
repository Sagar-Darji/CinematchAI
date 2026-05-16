/**
 * Full-screen reading view for the long-form taste-as-personality essay.
 * Renders the four sections produced by the layered Groq generation:
 *   - Longitudinal arc (3 paragraphs: who you were, how taste shifted,
 *     what it says about you now)
 *   - Dense paragraph (synthesis)
 *   - Letter (stylized, second-person)
 *   - Quarterly journal entries
 *
 * Each section is wrapped in a heading so the user can skim. Sections
 * the LLM didn't fill render nothing instead of empty headers.
 */
import { useEffect } from 'react'
import { X } from 'lucide-react'
import type { ProfilePersonality } from '@/lib/api'

interface Props {
  personality: ProfilePersonality
  onClose: () => void
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
      className="fixed inset-0 z-50 flex items-stretch justify-center md:items-center md:p-8"
      style={{ background: 'rgba(0,0,0,0.78)' }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-3xl overflow-y-auto md:rounded-2xl"
        style={{ background: 'var(--bg-page)', border: '1px solid var(--border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="sticky top-4 ml-auto mr-4 mt-4 z-10 flex items-center justify-center w-9 h-9 rounded-full"
          style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}
        >
          <X size={18} />
        </button>
        <div className="px-6 md:px-10 pb-12 pt-2 space-y-10">
          {personality.teaser && (
            <section>
              <p className="text-lg leading-relaxed text-white">{personality.teaser}</p>
            </section>
          )}
          {lf.longitudinal_arc.length > 0 && (
            <Section title="Where you've been">
              {lf.longitudinal_arc.map((para, i) => (
                <p key={i} className="text-[15px] leading-relaxed">{para}</p>
              ))}
            </Section>
          )}
          {lf.dense_paragraph && (
            <Section title="The synthesis">
              <p className="text-[15px] leading-relaxed">{lf.dense_paragraph}</p>
            </Section>
          )}
          {lf.letter && (
            <Section title="A letter">
              <p className="text-[15px] leading-relaxed whitespace-pre-line">{lf.letter}</p>
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
                    <p className="text-[15px] leading-relaxed">{q.text}</p>
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
      <div className="text-white space-y-3">{children}</div>
    </section>
  )
}

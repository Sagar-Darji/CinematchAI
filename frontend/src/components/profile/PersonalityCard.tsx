/**
 * Layered LLM essay card. Shows the teaser paragraph + up to 3 evidence
 * bullets, with an "Explore more" button that opens the full multi-section
 * essay in a modal.
 *
 * When the personality blob is empty (cold-start user, LLM disabled, or
 * Groq failure) we render nothing -- the card silently disappears rather
 * than showing a half-baked placeholder.
 */
import { useState } from 'react'
import { Sparkles } from 'lucide-react'
import type { ProfilePersonality } from '@/lib/api'
import { PersonalityModal } from './PersonalityModal'

// Inline copy of PersonalityModal's `unwrapText` — older personality
// blobs can ship "{'text': '...'}" strings (LLM ignored the schema +
// older normalizer just str()'d the object). Strip the wrapper so we
// never display Python dict repr to the user.
function unwrapText(s: string): string {
  if (!s) return s
  const t = s.trim()
  const m = t.match(/^\{\s*['"](?:text|paragraph|content|body|value)['"]\s*:\s*['"]([\s\S]*)['"]\s*\}$/)
  if (m) return m[1].replace(/\\'/g, "'").replace(/\\"/g, '"').trim()
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

export function PersonalityCard({ personality }: { personality: ProfilePersonality }) {
  const [open, setOpen] = useState(false)
  if (!personality?.teaser) return null

  const hasLongform =
    personality.longform &&
    (
      personality.longform.longitudinal_arc.length > 0 ||
      personality.longform.dense_paragraph ||
      personality.longform.letter ||
      personality.longform.quarterly_entries.length > 0
    )

  return (
    <>
      <section
        className="rounded-2xl p-6 flex flex-col gap-4"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2">
          <Sparkles size={18} style={{ color: 'var(--accent-gold)' }} />
          <h2 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
            Your taste, read back to you
          </h2>
        </div>
        <p className="text-[15px] leading-relaxed text-white">{unwrapText(personality.teaser)}</p>
        {personality.bullets.length > 0 && (
          <ul className="space-y-1.5 pl-1">
            {personality.bullets.map((b, i) => (
              <li
                key={i}
                className="text-sm leading-snug flex gap-2"
                style={{ color: 'var(--text-muted)' }}
              >
                <span style={{ color: 'var(--accent-gold)' }}>·</span>
                <span>{unwrapText(b)}</span>
              </li>
            ))}
          </ul>
        )}
        {hasLongform && (
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="self-start text-sm font-semibold mt-1"
            style={{ background: 'none', border: 'none', color: 'var(--accent-gold)', cursor: 'pointer', padding: 0 }}
          >
            Explore more →
          </button>
        )}
      </section>
      {open && (
        <PersonalityModal personality={personality} onClose={() => setOpen(false)} />
      )}
    </>
  )
}

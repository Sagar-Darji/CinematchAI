/**
 * Friendly empty-state for tabs with no relevant data yet. One CTA button,
 * one supporting line of copy, an icon. Same component across every tab
 * so cold-start UX feels consistent.
 */
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  body?: string
  ctaLabel?: string
  ctaHref?: string
  onCtaClick?: () => void
}

export function EmptyState({ icon, title, body, ctaLabel, ctaHref, onCtaClick }: EmptyStateProps) {
  const cta = ctaLabel ? (
    ctaHref ? (
      <Link
        to={ctaHref}
        className="inline-block mt-4 px-5 py-2.5 rounded-xl text-sm font-bold"
        style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}
      >
        {ctaLabel}
      </Link>
    ) : (
      <button
        type="button"
        onClick={onCtaClick}
        className="inline-block mt-4 px-5 py-2.5 rounded-xl text-sm font-bold"
        style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
      >
        {ctaLabel}
      </button>
    )
  ) : null

  return (
    <div
      className="rounded-xl p-8 text-center flex flex-col items-center justify-center"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      {icon && <div className="mb-4" style={{ color: 'var(--text-muted)' }}>{icon}</div>}
      <h3 className="text-base font-semibold text-white">{title}</h3>
      {body && (
        <p className="text-sm mt-2 max-w-md" style={{ color: 'var(--text-muted)' }}>
          {body}
        </p>
      )}
      {cta}
    </div>
  )
}

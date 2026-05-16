/**
 * Small "Last refreshed Xh ago" footer + 'Regenerate in Settings' link.
 * Visible whenever the precomputed Profile blob is older than the live
 * ratings count -- a manual rating happened since the last refresh.
 */
import { Link } from 'react-router-dom'

function relativeAge(iso: string | null | undefined): string {
  if (!iso) return 'never'
  const then = new Date(iso).getTime()
  if (!Number.isFinite(then)) return 'recently'
  const seconds = Math.max(1, Math.floor((Date.now() - then) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}

export function StaleNote({ computedAt }: { computedAt: string | null }) {
  return (
    <p
      className="text-xs"
      style={{ color: 'var(--text-muted)' }}
    >
      Analytics last refreshed {relativeAge(computedAt)}.{' '}
      <Link to="/settings" style={{ color: 'var(--accent-gold)', textDecoration: 'underline' }}>
        Regenerate in Settings
      </Link>
    </p>
  )
}

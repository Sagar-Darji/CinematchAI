/**
 * Watchlist tab content: poster grid with quick-rate + quick-remove.
 *
 * - Quick-rate writes to the ratings table via /users/feedback (which is
 *   what populates Profile analytics). It then auto-removes the title
 *   from the watchlist since rating implies "watched" — keeps the
 *   watchlist meaningfully a list of *unseen* films.
 * - Quick-remove just deletes the watchlist row.
 *
 * Pulls items from useWatchlistStore (the same store the rest of the
 * app uses) so changes here propagate everywhere.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Star, Trash2 } from 'lucide-react'
import { submitFeedback, removeFromWatchlistRemote } from '@/lib/api'
import { useUserStore } from '@/store/useUserStore'
import { useWatchlistStore, type WatchlistItem } from '@/store/useWatchlistStore'
import { EmptyState } from './EmptyState'

const HALF_STARS = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]

export function WatchlistGrid() {
  const userId = useUserStore((s) => s.userId)
  const items = useWatchlistStore((s) => s.items)
  const remove = useWatchlistStore((s) => s.remove)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [openRater, setOpenRater] = useState<string | null>(null)

  if (!items || items.length === 0) {
    return (
      <EmptyState
        title="Your watchlist is empty"
        body="Add films you want to see later — they'll show up here. The Letterboxd ZIP import brings your existing watchlist along."
        ctaLabel="Import"
        ctaHref="/settings"
      />
    )
  }

  const rateAndRemove = async (it: WatchlistItem, rating: number) => {
    const key = String(it.tmdbId)
    setBusyId(key)
    try {
      await submitFeedback(userId, it.tmdbId, rating)
      // Mirror the backend's auto-remove: the rating means "watched",
      // so the bookmark no longer applies.
      await removeFromWatchlistRemote(it.tmdbId, it.mediaType).catch(() => {})
      remove(it.tmdbId, it.mediaType)
    } finally {
      setBusyId(null)
      setOpenRater(null)
    }
  }

  const quickRemove = async (it: WatchlistItem) => {
    const key = String(it.tmdbId)
    setBusyId(key)
    try {
      await removeFromWatchlistRemote(it.tmdbId, it.mediaType).catch(() => {})
      remove(it.tmdbId, it.mediaType)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
      {items.map((it) => {
        const key = String(it.tmdbId)
        const isOpen = openRater === key
        const isBusy = busyId === key
        return (
          <div key={`${it.mediaType}-${key}`} className="relative group">
            <Link to={`/movie/${it.tmdbId}`}>
              <div
                className="relative"
                style={{ aspectRatio: '2/3', background: 'var(--bg-card)', borderRadius: '8px', overflow: 'hidden' }}
              >
                {it.posterPath ? (
                  <img
                    src={`https://image.tmdb.org/t/p/w342${it.posterPath}`}
                    alt={it.title}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-xs" style={{ color: 'var(--text-muted)' }}>
                    No poster
                  </div>
                )}
              </div>
              <p className="text-xs mt-1.5 truncate text-white" title={it.title}>{it.title}</p>
              {it.year && (
                <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{it.year}</p>
              )}
            </Link>
            <div
              className="absolute top-1 right-1 flex flex-col gap-1 transition-opacity opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
            >
              <button
                type="button"
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpenRater(isOpen ? null : key) }}
                aria-label="Rate"
                disabled={isBusy}
                style={{ background: 'rgba(0,0,0,0.78)', color: 'var(--accent-gold)', border: 'none', borderRadius: '6px', padding: '4px', cursor: 'pointer' }}
              >
                <Star size={14} />
              </button>
              <button
                type="button"
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); quickRemove(it) }}
                aria-label="Remove from watchlist"
                disabled={isBusy}
                style={{ background: 'rgba(0,0,0,0.78)', color: 'var(--accent-red)', border: 'none', borderRadius: '6px', padding: '4px', cursor: 'pointer' }}
              >
                <Trash2 size={14} />
              </button>
            </div>
            {isOpen && (
              <div
                className="absolute left-0 right-0 bottom-0 z-10 p-2 rounded-b-lg"
                style={{ background: 'rgba(10,10,15,0.95)' }}
                onClick={(e) => e.stopPropagation()}
              >
                <p className="text-[10px] mb-1 text-center" style={{ color: 'var(--text-muted)' }}>
                  Pick a rating
                </p>
                <div className="flex justify-center gap-1 flex-wrap">
                  {HALF_STARS.map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => rateAndRemove(it, r)}
                      disabled={isBusy}
                      className="text-[11px] px-1.5 py-0.5 rounded"
                      style={{ background: 'var(--bg-overlay)', color: 'white', border: '1px solid var(--border)', cursor: 'pointer' }}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

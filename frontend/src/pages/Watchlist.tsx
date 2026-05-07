import { Link } from 'react-router-dom'
import { Bookmark } from 'lucide-react'
import { useWatchlistStore } from '@/store/useWatchlistStore'
import { MovieCard, movieToRec } from '@/components/ui/MovieCard'
import type { Movie } from '@/lib/api'

export default function Watchlist() {
  const items = useWatchlistStore((s) => s.items)
  const clear = useWatchlistStore((s) => s.clear)

  if (items.length === 0) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-6 text-center pt-20">
        <Bookmark size={48} style={{ color: 'var(--text-muted)' }} className="mb-4" />
        <p className="text-base font-bold text-white mb-2">Your watchlist is empty</p>
        <p className="text-sm mb-6 max-w-sm" style={{ color: 'var(--text-muted)' }}>
          Save movies and series you want to watch later — they'll appear here.
        </p>
        <Link
          to="/browse"
          className="px-5 py-2.5 rounded-xl text-sm font-bold"
          style={{ background: 'var(--accent-gold)', color: '#0a0a0f', textDecoration: 'none' }}
        >
          Browse titles
        </Link>
      </div>
    )
  }

  return (
    <div className="min-h-screen px-4 md:px-6 pt-4 pb-10">
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="text-2xl md:text-3xl font-black text-white tracking-tight">Your Watchlist</h1>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            {items.length} {items.length === 1 ? 'title' : 'titles'} saved
          </p>
        </div>
        {items.length > 0 && (
          <button
            onClick={() => {
              if (confirm('Clear your entire watchlist?')) clear()
            }}
            className="text-xs font-semibold"
            style={{
              color: 'var(--text-muted)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            Clear all
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 md:gap-4">
        {items.map((it, i) => {
          const movie: Movie = {
            tmdb_id: it.tmdbId,
            title: it.title,
            year: it.year,
            poster_path: it.posterPath,
            media_type: it.mediaType,
          }
          return (
            <MovieCard
              key={`${it.tmdbId}-${it.mediaType}`}
              rec={movieToRec(movie, i + 1)}
              compact={false}
            />
          )
        })}
      </div>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Search, Trash2, ArrowUp, ArrowDown, Check, Loader2 } from 'lucide-react'
import { searchMovies, setFavorites, type FavoriteItem, type Movie } from '@/lib/api'
import { tmdbPoster } from '@/lib/utils'

interface Props {
  userId: string
  initial: FavoriteItem[]
  onClose: () => void
  onSaved: (items: FavoriteItem[]) => void
}

const MAX = 4

export function FavoritesEditor({ userId, initial, onClose, onSaved }: Props) {
  const [items, setItems] = useState<FavoriteItem[]>(initial)
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState<Movie[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string>('')
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
    }
  }, [onClose])

  // Debounced search across movies + TV in parallel.
  useEffect(() => {
    const q = query.trim()
    if (q.length < 2) {
      setResults([])
      setSearching(false)
      return
    }
    let cancelled = false
    setSearching(true)
    const t = setTimeout(async () => {
      try {
        const [movies, tv] = await Promise.all([
          searchMovies(q, 6, undefined, 1, 'movie'),
          searchMovies(q, 6, undefined, 1, 'tv'),
        ])
        if (cancelled) return
        // Interleave movies and tv results by popularity proxy (vote_average).
        const merged = [...movies, ...tv]
          .sort((a, b) => (b.vote_average ?? 0) - (a.vote_average ?? 0))
          .slice(0, 8)
        setResults(merged)
      } finally {
        if (!cancelled) setSearching(false)
      }
    }, 250)
    return () => { cancelled = true; clearTimeout(t) }
  }, [query])

  const addItem = (m: Movie) => {
    const fav: FavoriteItem = {
      tmdb_id: m.tmdb_id ?? m.id ?? 0,
      media_type: m.media_type ?? 'movie',
      title: m.title,
      poster_path: m.poster_path ?? null,
    }
    if (!fav.tmdb_id) return
    if (items.some((i) => i.tmdb_id === fav.tmdb_id && i.media_type === fav.media_type)) return
    if (items.length >= MAX) return
    setItems([...items, fav])
    setQuery('')
    setResults([])
  }

  const removeItem = (idx: number) => {
    setItems(items.filter((_, i) => i !== idx))
  }

  const move = (idx: number, dir: -1 | 1) => {
    const target = idx + dir
    if (target < 0 || target >= items.length) return
    const next = [...items]
    const [it] = next.splice(idx, 1)
    next.splice(target, 0, it)
    setItems(next)
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const saved = await setFavorites(userId, items)
      onSaved(saved)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const content = (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{
        background: 'rgba(0,0,0,0.85)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
      }}
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div
        className="relative w-full max-w-xl max-h-[90vh] flex flex-col rounded-2xl animate-fade-in shadow-2xl overflow-hidden"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border-hover)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 flex-shrink-0"
          style={{ borderBottom: '1px solid var(--border)' }}>
          <div>
            <h2 className="text-lg font-bold text-white">Pinned Favorites</h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              Pick up to {MAX}. They sit at the top of your profile.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-8 h-8 flex items-center justify-center rounded-full"
            style={{ background: 'rgba(255,255,255,0.08)', color: 'white', border: 'none', cursor: 'pointer' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 flex-1 overflow-y-auto space-y-4">
          {/* Current favorites */}
          <div>
            <p className="text-[11px] font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
              Your favorites ({items.length}/{MAX})
            </p>
            {items.length === 0 ? (
              <p className="text-sm py-3" style={{ color: 'var(--text-muted)' }}>
                No favorites yet. Search below to add up to {MAX}.
              </p>
            ) : (
              <div className="space-y-1.5">
                {items.map((it, idx) => {
                  const poster = tmdbPoster(it.poster_path ?? undefined, 'w185')
                  return (
                    <div key={`${it.tmdb_id}-${it.media_type}`} className="flex items-center gap-3 p-2 rounded-lg"
                      style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)' }}>
                      <span className="text-xs font-black w-5 text-center" style={{ color: 'var(--accent-gold)' }}>
                        {idx + 1}
                      </span>
                      <div className="w-9 flex-shrink-0 rounded overflow-hidden" style={{ aspectRatio: '2/3', background: 'var(--bg-card)' }}>
                        {poster ? (
                          <img src={poster} alt="" className="w-full h-full object-cover" />
                        ) : null}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-white truncate">{it.title}</p>
                        <p className="text-[10px] uppercase tracking-wide font-bold" style={{ color: 'var(--text-muted)' }}>
                          {it.media_type === 'tv' ? 'Series' : 'Movie'}
                        </p>
                      </div>
                      <div className="flex items-center gap-0.5 flex-shrink-0">
                        <button
                          onClick={() => move(idx, -1)}
                          disabled={idx === 0}
                          aria-label="Move up"
                          className="w-7 h-7 flex items-center justify-center rounded-md"
                          style={{ background: 'none', border: 'none', color: idx === 0 ? 'var(--text-muted)' : 'white', cursor: idx === 0 ? 'not-allowed' : 'pointer', opacity: idx === 0 ? 0.4 : 1 }}
                        >
                          <ArrowUp size={14} />
                        </button>
                        <button
                          onClick={() => move(idx, 1)}
                          disabled={idx === items.length - 1}
                          aria-label="Move down"
                          className="w-7 h-7 flex items-center justify-center rounded-md"
                          style={{ background: 'none', border: 'none', color: idx === items.length - 1 ? 'var(--text-muted)' : 'white', cursor: idx === items.length - 1 ? 'not-allowed' : 'pointer', opacity: idx === items.length - 1 ? 0.4 : 1 }}
                        >
                          <ArrowDown size={14} />
                        </button>
                        <button
                          onClick={() => removeItem(idx)}
                          aria-label="Remove"
                          className="w-7 h-7 flex items-center justify-center rounded-md"
                          style={{ background: 'none', border: 'none', color: 'var(--accent-red)', cursor: 'pointer' }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Search */}
          <div>
            <p className="text-[11px] font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
              Add a favorite
            </p>
            <div className="relative">
              <Search size={14} className="absolute top-1/2 left-3 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={items.length >= MAX ? 'Remove one to add another' : 'Search movies and TV…'}
                disabled={items.length >= MAX}
                className="w-full text-sm rounded-lg outline-none disabled:opacity-50"
                style={{
                  padding: '10px 12px 10px 36px',
                  background: 'var(--bg-overlay)',
                  border: '1px solid var(--border)',
                  color: 'white',
                }}
              />
            </div>
            {searching && (
              <div className="flex items-center gap-2 text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
                <Loader2 size={12} className="animate-spin" />
                Searching…
              </div>
            )}
            {results.length > 0 && (
              <div className="mt-2 space-y-1">
                {results.map((m) => {
                  const poster = tmdbPoster(m.poster_path, 'w185')
                  const id = m.tmdb_id ?? m.id ?? 0
                  const alreadyAdded = items.some((i) => i.tmdb_id === id && i.media_type === (m.media_type ?? 'movie'))
                  return (
                    <button
                      key={`${id}-${m.media_type}`}
                      onClick={() => addItem(m)}
                      disabled={alreadyAdded || items.length >= MAX}
                      className="w-full flex items-center gap-3 p-2 rounded-lg text-left disabled:opacity-50"
                      style={{
                        background: 'transparent',
                        border: '1px solid var(--border)',
                        cursor: alreadyAdded || items.length >= MAX ? 'not-allowed' : 'pointer',
                      }}
                    >
                      <div className="w-9 flex-shrink-0 rounded overflow-hidden" style={{ aspectRatio: '2/3', background: 'var(--bg-card)' }}>
                        {poster ? <img src={poster} alt="" className="w-full h-full object-cover" /> : null}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-white truncate">{m.title}</p>
                        <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                          {(m.media_type === 'tv' ? 'Series' : 'Movie')}
                          {m.year ? ` · ${m.year}` : ''}
                        </p>
                      </div>
                      {alreadyAdded ? (
                        <Check size={14} style={{ color: 'var(--accent-gold)' }} />
                      ) : null}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-4 flex items-center justify-between gap-3 flex-shrink-0"
          style={{ borderTop: '1px solid var(--border)' }}>
          {error ? (
            <p className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</p>
          ) : <span />}
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="text-sm font-semibold"
              style={{
                padding: '9px 16px',
                borderRadius: '10px',
                background: 'var(--bg-overlay)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border)',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="text-sm font-bold flex items-center gap-2"
              style={{
                padding: '9px 18px',
                borderRadius: '10px',
                background: 'var(--accent-gold)',
                color: '#0a0a0f',
                border: 'none',
                cursor: saving ? 'wait' : 'pointer',
                opacity: saving ? 0.7 : 1,
              }}
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : null}
              Save favorites
            </button>
          </div>
        </div>
      </div>
    </div>
  )

  return createPortal(content, document.body)
}

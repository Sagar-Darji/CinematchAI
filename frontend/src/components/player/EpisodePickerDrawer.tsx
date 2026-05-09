import { useEffect, useRef, useState } from 'react'
import { X, Play, Calendar, Clock } from 'lucide-react'
import { getSeasonEpisodes, type Episode, type Season } from '@/lib/api'
import { tmdbPoster, formatRuntime } from '@/lib/utils'
import { getPlayableSeasons } from './playerHelpers'

interface Props {
  tmdbId: number | string
  seasons: Season[] | undefined
  currentSeason: number
  currentEpisode: number
  autoAdvance: boolean
  onSelect: (season: number, episode: number) => void
  onClose: () => void
  onToggleAutoAdvance: (v: boolean) => void
}

/**
 * Bottom-sheet episode picker. The parent should conditionally mount/unmount
 * this component to control visibility — that lets activeSeason initialize
 * from currentSeason without a sync effect.
 */
export function EpisodePickerDrawer({
  tmdbId,
  seasons,
  currentSeason,
  currentEpisode,
  autoAdvance,
  onSelect,
  onClose,
  onToggleAutoAdvance,
}: Props) {
  const playableSeasons = getPlayableSeasons(seasons)
  const [activeSeason, setActiveSeason] = useState(currentSeason)
  // Cache episodes per (tmdbId, season) for the lifetime of the drawer.
  const cacheRef = useRef<Map<string, Episode[]>>(new Map())
  const [episodes, setEpisodes] = useState<Episode[] | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const cacheKey = `${tmdbId}:${activeSeason}`
    const cached = cacheRef.current.get(cacheKey)
    if (cached) {
      setEpisodes(cached)
      return
    }
    let cancelled = false
    setLoading(true)
    setEpisodes(null)
    getSeasonEpisodes(Number(tmdbId), activeSeason)
      .then((detail) => {
        if (cancelled) return
        const eps = detail?.episodes ?? []
        cacheRef.current.set(cacheKey, eps)
        setEpisodes(eps)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [tmdbId, activeSeason])

  // Capture Escape before the player's own Escape handler closes the whole
  // player — we want a layered close (drawer first, then player).
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    document.addEventListener('keydown', handler, true)
    return () => document.removeEventListener('keydown', handler, true)
  }, [onClose])

  const selectedSeasonMeta = playableSeasons.find((s) => s.season_number === activeSeason)
  const episodeCount = selectedSeasonMeta?.episode_count ?? 0

  return (
    <div
      className="absolute inset-0 z-20 flex flex-col justify-end"
      style={{ background: 'rgba(0,0,0,0.55)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="rounded-t-2xl flex flex-col overflow-hidden animate-slide-up"
        style={{
          background: 'rgba(12,12,16,0.98)',
          borderTop: '1px solid rgba(255,255,255,0.1)',
          maxHeight: '70vh',
          paddingBottom: 'max(env(safe-area-inset-bottom, 0px), 0.5rem)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer header */}
        <div className="flex items-center justify-between px-4 py-3 flex-shrink-0"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
          <div className="flex items-center gap-3">
            <h3 className="text-base font-bold text-white">Episodes</h3>
            <label className="flex items-center gap-1.5 text-[11px] cursor-pointer select-none"
              style={{ color: 'rgba(255,255,255,0.7)' }}>
              <input
                type="checkbox"
                checked={autoAdvance}
                onChange={(e) => onToggleAutoAdvance(e.target.checked)}
                className="cursor-pointer"
                style={{ accentColor: 'var(--accent-gold)' }}
              />
              Auto-play next
            </label>
          </div>
          <button
            onClick={onClose}
            aria-label="Close episodes"
            className="w-8 h-8 flex items-center justify-center rounded-full"
            style={{ background: 'rgba(255,255,255,0.1)', color: 'white', border: 'none', cursor: 'pointer' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Season tabs */}
        {playableSeasons.length > 1 && (
          <div className="flex gap-1.5 overflow-x-auto hide-scrollbar px-4 py-2.5 flex-shrink-0"
            style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            {playableSeasons.map((s) => {
              const isActive = s.season_number === activeSeason
              return (
                <button
                  key={s.season_number}
                  onClick={() => setActiveSeason(s.season_number)}
                  className="flex-shrink-0 text-xs font-bold px-3 py-1.5 rounded-full transition-colors"
                  style={{
                    background: isActive ? 'var(--accent-gold)' : 'rgba(255,255,255,0.06)',
                    color: isActive ? '#0a0a0f' : 'rgba(255,255,255,0.75)',
                    border: '1px solid ' + (isActive ? 'transparent' : 'rgba(255,255,255,0.1)'),
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {s.name && !/^Season \d+$/i.test(s.name) ? s.name : `Season ${s.season_number}`}
                </button>
              )
            })}
          </div>
        )}

        {/* Episode list */}
        <div className="flex-1 overflow-y-auto px-3 py-2">
          {loading && <EpisodeSkeletons count={Math.min(Math.max(episodeCount, 4), 8)} />}

          {!loading && (episodes?.length ?? 0) === 0 && (
            <p className="text-sm text-center py-8" style={{ color: 'var(--text-muted)' }}>
              No episodes found for this season.
            </p>
          )}

          {!loading && episodes && episodes.map((ep) => {
            const isPlaying = activeSeason === currentSeason && ep.episode_number === currentEpisode
            const still = tmdbPoster(ep.still_path ?? undefined, 'w300')
            return (
              <button
                key={ep.episode_number}
                onClick={() => onSelect(activeSeason, ep.episode_number)}
                className="w-full flex gap-3 p-2 rounded-xl text-left transition-colors mb-1"
                style={{
                  background: isPlaying ? 'rgba(245,197,24,0.08)' : 'transparent',
                  borderLeft: isPlaying ? '3px solid var(--accent-gold)' : '3px solid transparent',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                <div className="relative flex-shrink-0 rounded-md overflow-hidden"
                  style={{ width: '120px', aspectRatio: '16/9', background: 'rgba(255,255,255,0.05)' }}>
                  {still ? (
                    <img src={still} alt="" className="w-full h-full object-cover" loading="lazy" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-[10px] font-bold"
                      style={{ color: 'rgba(255,255,255,0.4)' }}>
                      EP {ep.episode_number}
                    </div>
                  )}
                  {isPlaying && (
                    <div className="absolute inset-0 flex items-center justify-center"
                      style={{ background: 'rgba(0,0,0,0.45)' }}>
                      <Play size={20} fill="white" color="white" />
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0 py-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-black flex-shrink-0"
                      style={{ color: isPlaying ? 'var(--accent-gold)' : 'rgba(255,255,255,0.5)' }}>
                      {ep.episode_number}
                    </span>
                    <p className="text-sm font-semibold text-white truncate">
                      {ep.name || `Episode ${ep.episode_number}`}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-[11px]"
                    style={{ color: 'rgba(255,255,255,0.55)' }}>
                    {ep.runtime ? (
                      <span className="flex items-center gap-1"><Clock size={10} />{formatRuntime(ep.runtime)}</span>
                    ) : null}
                    {ep.air_date ? (
                      <span className="flex items-center gap-1"><Calendar size={10} />{ep.air_date}</span>
                    ) : null}
                  </div>
                  {ep.overview ? (
                    <p className="text-[11px] mt-1 line-clamp-2"
                      style={{ color: 'rgba(255,255,255,0.5)' }}>
                      {ep.overview}
                    </p>
                  ) : null}
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function EpisodeSkeletons({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex gap-3 p-2 mb-1">
          <div className="skeleton flex-shrink-0 rounded-md"
            style={{ width: '120px', aspectRatio: '16/9' }} />
          <div className="flex-1 space-y-1.5 py-1">
            <div className="skeleton-text w-2/3" />
            <div className="skeleton-text w-1/3" style={{ opacity: 0.5 }} />
            <div className="skeleton-text w-full" style={{ opacity: 0.4 }} />
          </div>
        </div>
      ))}
    </>
  )
}

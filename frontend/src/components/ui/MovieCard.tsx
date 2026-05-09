import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { Star, Calendar, Clock, PlayCircle, X, ThumbsUp, ThumbsDown, ChevronUp } from 'lucide-react'
import { getMediaDetails, getSeasonEpisodes, submitFeedback, recordInteraction } from '@/lib/api'
import type { MediaType, Movie, Recommendation, Season, Episode } from '@/lib/api'
import { tmdbPoster, scoreColor, formatRuntime, cn } from '@/lib/utils'
import { useUserStore } from '@/store/useUserStore'
import { useHistoryStore } from '@/store/useHistoryStore'
import { EpisodePickerDrawer } from '@/components/player/EpisodePickerDrawer'
import {
  getPlayableSeasons,
  getDefaultSeasonNumber,
  getNextEpisode,
  getPrevEpisode,
} from '@/components/player/playerHelpers'

type EmbedSource = {
  name: string
  movieUrl: (id: string | number) => string
  tvUrl: (id: string | number, season?: number, episode?: number) => string
}

const EMBED_SOURCES = [
  {
    name: 'VidLink',
    movieUrl: (id) => `https://vidlink.pro/movie/${id}`,
    tvUrl: (id, season, episode) => season && episode
      ? `https://vidlink.pro/tv/${id}/${season}/${episode}`
      : `https://vidlink.pro/tv/${id}`,
  },
  {
    name: 'AutoEmbed',
    movieUrl: (id) => `https://player.autoembed.cc/embed/movie/${id}`,
    tvUrl: (id, season, episode) => season && episode
      ? `https://player.autoembed.cc/embed/tv/${id}/${season}/${episode}`
      : `https://player.autoembed.cc/embed/tv/${id}`,
  },
  {
    name: 'Embed.su',
    movieUrl: (id) => `https://embed.su/embed/movie/${id}`,
    tvUrl: (id, season, episode) => season && episode
      ? `https://embed.su/embed/tv/${id}/${season}/${episode}`
      : `https://embed.su/embed/tv/${id}`,
  },
  {
    name: 'VidSrc.to',
    movieUrl: (id) => `https://vidsrc.to/embed/movie/${id}`,
    tvUrl: (id, season, episode) => season && episode
      ? `https://vidsrc.to/embed/tv/${id}/${season}/${episode}`
      : `https://vidsrc.to/embed/tv/${id}`,
  },
  {
    name: 'VidSrc.xyz',
    movieUrl: (id) => `https://vidsrc.xyz/embed/movie/${id}`,
    tvUrl: (id, season, episode) => season && episode
      ? `https://vidsrc.xyz/embed/tv/${id}/${season}-${episode}`
      : `https://vidsrc.xyz/embed/tv/${id}`,
  },
  {
    name: 'VidSrc.in',
    movieUrl: (id) => `https://vidsrc.in/embed/movie/${id}`,
    tvUrl: (id, season, episode) => season && episode
      ? `https://vidsrc.in/embed/tv/${id}/${season}-${episode}`
      : `https://vidsrc.in/embed/tv/${id}`,
  },
] satisfies EmbedSource[]

function buildEmbedUrl(
  source: EmbedSource,
  mediaType: MediaType,
  tmdbId: string | number,
  season?: number,
  episode?: number,
) {
  return mediaType === 'tv'
    ? source.tvUrl(tmdbId, season, episode)
    : source.movieUrl(tmdbId)
}

// ── Full-screen video player overlay ─────────────────────────────────────────

export function FullScreenPlayer({
  tmdbId,
  title,
  mediaType,
  seasons,
  onClose,
}: {
  tmdbId: number | string
  title: string
  mediaType: MediaType
  seasons?: Season[]
  onClose: () => void
}) {
  const autoAdvance = useUserStore((s) => s.autoAdvance)
  const setAutoAdvance = useUserStore((s) => s.setAutoAdvance)

  const [adShield, setAdShield] = useState(true)
  const [srcIdx, setSrcIdx] = useState(0)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [currentSeasonEpisodes, setCurrentSeasonEpisodes] = useState<Episode[] | null>(null)
  // Seconds remaining in the auto-advance countdown, or null when not armed.
  const [pendingAdvance, setPendingAdvance] = useState<number | null>(null)

  // Resume the last season/episode the user navigated to last time, if any.
  const [selectedSeason, setSelectedSeason] = useState(() => {
    if (mediaType === 'tv') {
      const hist = useHistoryStore.getState().items.find(
        (i) => i.tmdbId === Number(tmdbId) && i.mediaType === 'tv',
      )
      if (hist?.lastSeason) return hist.lastSeason
    }
    return getDefaultSeasonNumber(seasons)
  })
  const [selectedEpisode, setSelectedEpisode] = useState(() => {
    if (mediaType === 'tv') {
      const hist = useHistoryStore.getState().items.find(
        (i) => i.tmdbId === Number(tmdbId) && i.mediaType === 'tv',
      )
      if (hist?.lastEpisode) return hist.lastEpisode
    }
    return 1
  })

  const playableSeasons = getPlayableSeasons(seasons)
  const fallbackEpisodeCount = playableSeasons.find((s) => s.season_number === selectedSeason)?.episode_count ?? 1
  // Prefer the exact count from the fetched episode list once it lands; fall
  // back to the season-level count in the meantime.
  const episodeCount = Math.max(currentSeasonEpisodes?.length ?? fallbackEpisodeCount, 1)
  const currentEpisodeData = currentSeasonEpisodes?.find((e) => e.episode_number === selectedEpisode)

  const nextRef = mediaType === 'tv'
    ? getNextEpisode(seasons, { season: selectedSeason, episode: selectedEpisode })
    : null
  const prevRef = mediaType === 'tv'
    ? getPrevEpisode(seasons, { season: selectedSeason, episode: selectedEpisode })
    : null

  const nextSource = () => setSrcIdx((i) => (i + 1) % EMBED_SOURCES.length)

  const goNext = () => {
    if (!nextRef) return
    setSelectedSeason(nextRef.season)
    setSelectedEpisode(nextRef.episode)
  }
  const goPrev = () => {
    if (!prevRef) return
    setSelectedSeason(prevRef.season)
    setSelectedEpisode(prevRef.episode)
  }

  useEffect(() => {
    setSrcIdx(0)
  }, [mediaType])

  // Fetch the current season's episode list — used to label the "now playing"
  // pill, validate the episode count, and show the episode title in the top
  // chrome. Server caches for 24h so re-opens are cheap.
  useEffect(() => {
    if (mediaType !== 'tv' || !tmdbId) {
      setCurrentSeasonEpisodes(null)
      return
    }
    let cancelled = false
    setCurrentSeasonEpisodes(null)
    getSeasonEpisodes(Number(tmdbId), selectedSeason).then((detail) => {
      if (cancelled) return
      setCurrentSeasonEpisodes(detail?.episodes ?? [])
    })
    return () => { cancelled = true }
  }, [tmdbId, mediaType, selectedSeason])

  // Persist TV progress as the user navigates seasons/episodes inside the player.
  useEffect(() => {
    if (mediaType !== 'tv' || !tmdbId) return
    useHistoryStore.getState().setProgress(
      Number(tmdbId),
      mediaType,
      selectedSeason,
      selectedEpisode,
    )
  }, [selectedSeason, selectedEpisode, mediaType, tmdbId])

  useEffect(() => {
    if (selectedEpisode > episodeCount) {
      setSelectedEpisode(1)
    }
  }, [selectedEpisode, episodeCount])

  // Cancel a pending auto-advance whenever the episode/source changes from
  // any source (manual nav, drawer pick, or the advance firing).
  useEffect(() => { setPendingAdvance(null) }, [selectedSeason, selectedEpisode, srcIdx])

  // Keyboard: Esc to close (unless drawer is up), n/p for next/prev episode.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (!drawerOpen) onClose()
        return
      }
      // Don't capture single-letter keys when typing in inputs.
      const target = e.target as HTMLElement | null
      const tag = target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || target?.isContentEditable) return
      if (mediaType === 'tv') {
        if (e.key === 'n' || e.key === 'N') goNext()
        if (e.key === 'p' || e.key === 'P') goPrev()
      }
    }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    // Block popups opened by the iframe
    const origOpen = window.open
    window.open = () => null
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
      window.open = origOpen
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onClose, mediaType, drawerOpen, nextRef?.season, nextRef?.episode, prevRef?.season, prevRef?.episode])

  // Auto-advance via embed postMessage. VidLink emits PLAYER_EVENT messages
  // with currentTime / duration; we arm the countdown on `ended` or > 97%.
  useEffect(() => {
    if (mediaType !== 'tv' || !autoAdvance || !nextRef) return
    let armed = false
    const handler = (event: MessageEvent) => {
      let payload: unknown = event.data
      if (typeof payload === 'string') {
        try { payload = JSON.parse(payload) } catch { return }
      }
      if (!payload || typeof payload !== 'object') return
      const obj = payload as Record<string, unknown>
      const evt = (obj.event ?? obj.type) as string | undefined
      const data = (obj.data ?? obj) as Record<string, unknown>
      const ct = Number(data.currentTime)
      const dur = Number(data.duration)
      const ended = evt === 'ended' || (Number.isFinite(ct) && Number.isFinite(dur) && dur > 0 && ct / dur > 0.97)
      if (ended && !armed) {
        armed = true
        setPendingAdvance(10)
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [mediaType, autoAdvance, nextRef, srcIdx])

  // Tick the countdown; fire goNext when it hits 0.
  useEffect(() => {
    if (pendingAdvance === null) return
    if (pendingAdvance <= 0) {
      goNext()
      return
    }
    const t = setTimeout(() => setPendingAdvance((p) => (p === null ? null : p - 1)), 1000)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingAdvance])

  const src = buildEmbedUrl(
    EMBED_SOURCES[srcIdx],
    mediaType,
    tmdbId,
    mediaType === 'tv' && playableSeasons.length > 0 ? selectedSeason : undefined,
    mediaType === 'tv' && playableSeasons.length > 0 ? selectedEpisode : undefined,
  )

  const episodeLabel = currentEpisodeData?.name
    ? `S${selectedSeason} · E${selectedEpisode} · ${currentEpisodeData.name}`
    : `S${selectedSeason} · E${selectedEpisode}`

  const titleBarText = mediaType === 'tv'
    ? (currentEpisodeData?.name
        ? `${title} · S${selectedSeason} · E${selectedEpisode} — ${currentEpisodeData.name}`
        : `${title} · S${selectedSeason} · E${selectedEpisode}`)
    : title

  return createPortal(
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100dvh',
        zIndex: 99999,
        background: '#000',
      }}
    >
      {/* Top bar: source switcher + title + close */}
      <div
        className="absolute top-0 inset-x-0 z-10 flex items-center justify-between gap-3"
        style={{
          background: 'linear-gradient(to bottom, rgba(0,0,0,0.85), transparent)',
          paddingTop: 'max(env(safe-area-inset-top, 0px), 0.75rem)',
          paddingBottom: '0.75rem',
          paddingLeft: 'max(env(safe-area-inset-left, 0px), 1rem)',
          paddingRight: 'max(env(safe-area-inset-right, 0px), 1rem)',
        }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <button
            onClick={nextSource}
            title="Try next streaming source"
            className="flex-shrink-0"
            style={{
              fontSize: '11px',
              padding: '6px 12px',
              borderRadius: '12px',
              border: '1px solid rgba(255,255,255,0.25)',
              background: 'rgba(255,255,255,0.1)',
              color: 'rgba(255,255,255,0.75)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            ⟳ {EMBED_SOURCES[srcIdx].name}
          </button>
        </div>
        <span className="text-white text-sm font-semibold truncate flex-1 text-center opacity-80 hidden md:inline">
          {titleBarText}
        </span>
        <button
          onClick={onClose}
          aria-label="Close player"
          className="w-10 h-10 flex items-center justify-center rounded-full flex-shrink-0"
          style={{
            background: 'rgba(255,255,255,0.18)',
            color: 'white',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          <X size={18} />
        </button>
      </div>

      {/* Episode toolbar (TV only): sits in a second row right under the
          top bar so it never covers the iframe's bottom controls
          (fullscreen, seekbar, settings). */}
      {mediaType === 'tv' && playableSeasons.length > 0 && (
        <div
          className="absolute z-10 flex items-center justify-between gap-3 flex-wrap"
          style={{
            // Outer container is click-through so the iframe behind always
            // gets the click; child buttons set pointer-events:auto.
            pointerEvents: 'none',
            left: 'max(env(safe-area-inset-left, 0px), 1rem)',
            right: 'max(env(safe-area-inset-right, 0px), 1rem)',
            // Sit just below the top bar (top bar ~3.25rem tall + safe-area).
            top: 'calc(max(env(safe-area-inset-top, 0px), 0.75rem) + 3.25rem)',
          }}
        >
          <button
            onClick={() => setDrawerOpen(true)}
            title="Browse episodes"
            className="flex items-center gap-2 max-w-[60%] truncate"
            style={{
              pointerEvents: 'auto',
              padding: '8px 14px',
              borderRadius: '14px',
              background: 'rgba(0,0,0,0.62)',
              backdropFilter: 'blur(10px)',
              border: '1px solid rgba(255,255,255,0.14)',
              color: '#fff',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            <span className="truncate">{episodeLabel}</span>
            <ChevronUp size={14} className="flex-shrink-0" />
          </button>

          <div className="flex items-center gap-2" style={{ pointerEvents: 'auto' }}>
            <button
              onClick={goPrev}
              disabled={!prevRef}
              aria-label="Previous episode"
              title="Previous episode (P)"
              style={{
                padding: '8px 14px',
                borderRadius: '14px',
                background: 'rgba(0,0,0,0.62)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(255,255,255,0.14)',
                color: prevRef ? '#fff' : 'rgba(255,255,255,0.35)',
                fontSize: '12px',
                fontWeight: 700,
                cursor: prevRef ? 'pointer' : 'not-allowed',
                whiteSpace: 'nowrap',
              }}
            >
              ‹ Prev
            </button>
            <button
              onClick={goNext}
              disabled={!nextRef}
              aria-label="Next episode"
              title="Next episode (N)"
              style={{
                padding: '8px 16px',
                borderRadius: '14px',
                background: nextRef ? 'var(--accent-gold)' : 'rgba(0,0,0,0.62)',
                backdropFilter: nextRef ? 'none' : 'blur(10px)',
                border: '1px solid ' + (nextRef ? 'transparent' : 'rgba(255,255,255,0.14)'),
                color: nextRef ? '#0a0a0f' : 'rgba(255,255,255,0.35)',
                fontSize: '12px',
                fontWeight: 800,
                cursor: nextRef ? 'pointer' : 'not-allowed',
                whiteSpace: 'nowrap',
              }}
            >
              Next ›
            </button>
          </div>
        </div>
      )}

      {/* Auto-advance countdown toast */}
      {pendingAdvance !== null && nextRef && (
        <div
          className="absolute z-20 flex items-center gap-3 animate-fade-in"
          style={{
            right: 'max(env(safe-area-inset-right, 0px), 1rem)',
            bottom: 'calc(max(env(safe-area-inset-bottom, 0px), 0.75rem) + 4rem)',
            padding: '10px 14px',
            borderRadius: '14px',
            background: 'rgba(12,12,16,0.94)',
            border: '1px solid rgba(255,255,255,0.14)',
            backdropFilter: 'blur(10px)',
            color: '#fff',
            fontSize: '12px',
            fontWeight: 600,
            maxWidth: '90vw',
          }}
        >
          <span>Playing S{nextRef.season} · E{nextRef.episode} in {pendingAdvance}s</span>
          <button
            onClick={() => setPendingAdvance(null)}
            style={{
              padding: '4px 10px',
              borderRadius: '8px',
              background: 'rgba(255,255,255,0.1)',
              border: '1px solid rgba(255,255,255,0.18)',
              color: '#fff',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={goNext}
            style={{
              padding: '4px 10px',
              borderRadius: '8px',
              background: 'var(--accent-gold)',
              border: 'none',
              color: '#0a0a0f',
              fontSize: '11px',
              fontWeight: 800,
              cursor: 'pointer',
            }}
          >
            Play now
          </button>
        </div>
      )}

      {/* Ad shield: absorbs the first click (VidSrc ad redirect) then disappears */}
      {adShield && (
        <div
          onClick={() => setAdShield(false)}
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 5,
            cursor: 'pointer',
            background: 'transparent',
          }}
        />
      )}

      <iframe
        key={`${mediaType}-${selectedSeason}-${selectedEpisode}-${srcIdx}`}
        // While the episode drawer is open, swap the iframe to about:blank
        // so playback hard-stops — embed sources are cross-origin so we
        // can't postMessage("pause") universally. When the drawer closes
        // (with or without a new pick), src flips back to the real URL.
        src={drawerOpen ? 'about:blank' : src}
        style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
        referrerPolicy="no-referrer"
        allow="autoplay; fullscreen; encrypted-media"
        allowFullScreen
        loading="lazy"
        title={`Watch ${title}`}
        onError={nextSource}
      />

      {mediaType === 'tv' && drawerOpen && (
        <EpisodePickerDrawer
          tmdbId={tmdbId}
          seasons={seasons}
          currentSeason={selectedSeason}
          currentEpisode={selectedEpisode}
          autoAdvance={autoAdvance}
          onSelect={(season, episode) => {
            setSelectedSeason(season)
            setSelectedEpisode(episode)
            setDrawerOpen(false)
          }}
          onClose={() => setDrawerOpen(false)}
          onToggleAutoAdvance={setAutoAdvance}
        />
      )}
    </div>,
    document.body
  )
}

interface MovieCardProps {
  rec: Recommendation
  rank?: number
  compact?: boolean
}

// ── Floating modal ────────────────────────────────────────────────────────────

interface ModalProps {
  rec: Recommendation
  onClose: () => void
}

function MovieModal({ rec, onClose }: ModalProps) {
  const { movie, score, explanation, is_exploration } = rec
  const [showPlayer, setShowPlayer] = useState(false)
  const [rated, setRated] = useState<'up' | 'down' | null>(null)
  const [detailMovie, setDetailMovie] = useState<Movie | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState(false)
  const userId = useUserStore((s) => s.userId)
  const overlayRef = useRef<HTMLDivElement>(null)

  const mediaType = movie.media_type ?? 'movie'
  const displayMovie = detailMovie ?? movie
  const poster = tmdbPoster(displayMovie.poster_path, 'w500')
  const pct = Math.round(score * 100)
  const barColor = scoreColor(score)
  const tmdbId = movie.tmdb_id || movie.id
  const isTv = mediaType === 'tv'

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
    }
  }, [onClose])

  useEffect(() => {
    let cancelled = false

    if (!tmdbId || mediaType !== 'tv') {
      setDetailMovie(null)
      setDetailLoading(false)
      setDetailError(false)
      return
    }

    setDetailLoading(true)
    setDetailError(false)

    getMediaDetails(Number(tmdbId), mediaType)
      .then((details) => {
        if (cancelled) return
        setDetailMovie(details)
        setDetailError(!details)
      })
      .catch(() => {
        if (cancelled) return
        setDetailError(true)
      })
      .finally(() => {
        if (cancelled) return
        setDetailLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [mediaType, tmdbId])

  const handleRate = async (v: 'up' | 'down') => {
    if (!userId || !tmdbId || isTv) return
    setRated(v)
    await submitFeedback(userId, tmdbId, v === 'up' ? 5.0 : 1.0)
    // Also record as dismissal signal for the feedback loop
    recordInteraction(userId, tmdbId, v === 'up' ? 'watched' : 'dismissed')
  }

  const modalContent = (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ 
        background: 'rgba(0,0,0,0.85)', 
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)'
      }}
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div
        className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl animate-fade-in shadow-2xl"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border-hover)' }}
      >
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-10 w-8 h-8 flex items-center justify-center rounded-full"
          style={{ background: 'rgba(0,0,0,0.7)', color: 'white', border: 'none', cursor: 'pointer' }}
        >
          <X size={15} />
        </button>

        {/* Poster backdrop header */}
        <div className="relative overflow-hidden rounded-t-2xl" style={{ height: '260px' }}>
          {poster ? (
            <>
              <div
                className="absolute inset-0"
                style={{
                  backgroundImage: `url(${poster})`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center 20%',
                  filter: 'blur(18px) brightness(0.35)',
                  transform: 'scale(1.15)',
                }}
              />
              <div className="relative h-full flex items-center justify-center">
                <img
                  src={poster}
                  alt={displayMovie.title}
                  style={{ height: '200px', borderRadius: '10px', boxShadow: '0 20px 60px rgba(0,0,0,0.8)', objectFit: 'cover' }}
                />
              </div>
            </>
          ) : (
            <div className="h-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#1a1a2e,#0f3460)' }}>
              <span className="text-xl font-bold" style={{ color: 'var(--accent-gold)' }}>{displayMovie.title}</span>
            </div>
          )}
          <div className="absolute bottom-0 inset-x-0 h-16" style={{ background: 'linear-gradient(to bottom, transparent, var(--bg-card))' }} />
        </div>

        {/* Body */}
        <div className="px-6 pb-6 -mt-2 space-y-4">
          {is_exploration && (
            <span className="inline-block text-white text-[10px] font-bold px-2 py-0.5 rounded-full"
              style={{ background: 'var(--accent-red)' }}>🔍 Discovery Pick</span>
          )}

          <div>
            <div className="flex items-start gap-2 flex-wrap">
              <h2 className="text-2xl font-black text-white leading-tight">{displayMovie.title}</h2>
              <span className="mt-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide"
                style={{ background: isTv ? 'rgba(91,192,190,0.12)' : 'rgba(245,197,24,0.12)', color: isTv ? '#8be0db' : 'var(--accent-gold)', border: `1px solid ${isTv ? 'rgba(91,192,190,0.3)' : 'rgba(245,197,24,0.22)'}` }}>
                {isTv ? 'Series' : 'Movie'}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-3 mt-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
              {displayMovie.year && <span className="flex items-center gap-1"><Calendar size={11} />{displayMovie.year}</span>}
              {displayMovie.vote_average && (
                <span className="flex items-center gap-1">
                  <Star size={11} style={{ color: 'var(--accent-gold)' }} />
                  {Number(displayMovie.vote_average).toFixed(1)}/10
                </span>
              )}
              {displayMovie.runtime && <span className="flex items-center gap-1"><Clock size={11} />{formatRuntime(displayMovie.runtime)}</span>}
              {displayMovie.director && <span>🎬 {displayMovie.director}</span>}
              {displayMovie.creator && <span>📺 {displayMovie.creator}</span>}
              {isTv && displayMovie.season_count && (
                <span>{displayMovie.season_count} {displayMovie.season_count === 1 ? 'season' : 'seasons'}</span>
              )}
              {isTv && displayMovie.episode_count && (
                <span>{displayMovie.episode_count} episodes</span>
              )}
            </div>
          </div>

          {(displayMovie.genres?.length ?? 0) > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {displayMovie.genres!.map((g) => <span key={g} className="genre-pill">{g}</span>)}
            </div>
          )}

          {isTv && detailLoading && (
            <div className="rounded-lg px-4 py-3 text-sm" style={{ background: 'var(--bg-overlay)', color: 'var(--text-muted)' }}>
              Loading seasons and episodes…
            </div>
          )}

          {isTv && detailError && (
            <div className="rounded-lg px-4 py-3 text-sm" style={{ background: 'rgba(229,9,20,0.08)', color: '#ff9b9b', border: '1px solid rgba(229,9,20,0.18)' }}>
              Season details could not be loaded. You can still try the player, but episode selection may be limited.
            </div>
          )}

          {/* Score bar */}
          <div className="flex items-center gap-3">
            <span className="text-xs" style={{ color: 'var(--text-muted)', minWidth: '70px' }}>Match score</span>
            <div className="score-bar-track flex-1">
              <div className="score-bar-fill" style={{ width: `${pct}%`, background: barColor }} />
            </div>
            <span className="text-sm font-black" style={{ color: barColor }}>{pct}%</span>
          </div>

          {displayMovie.overview && (
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>{displayMovie.overview}</p>
          )}

          {explanation && (
            <div className="rounded-lg px-4 py-3 text-sm" style={{ background: 'var(--bg-overlay)', borderLeft: `3px solid ${barColor}`, color: 'var(--text-muted)' }}>
              <span className="text-white font-semibold">Why this? </span>{explanation}
            </div>
          )}

          {/* Feedback */}
          {!isTv && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Rate this pick:</span>
              {([{ v: 'up', I: ThumbsUp, l: 'Love it', a: 'var(--accent-gold)', at: '#0a0a0f' },
                 { v: 'down', I: ThumbsDown, l: 'Not for me', a: 'var(--accent-red)', at: '#fff' }] as const)
                .map(({ v, I, l, a, at }) => (
                  <button key={v} onClick={() => handleRate(v)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium"
                    style={{ background: rated === v ? a : 'var(--bg-overlay)', color: rated === v ? at : 'var(--text-muted)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                    <I size={11} /> {l}
                  </button>
                ))}
            </div>
          )}

          {/* Watch Now */}
          {tmdbId && (
            <button onClick={() => {
              setShowPlayer(true)
              // Don't fire 'clicked' here — backend turns that into a 3.5
              // implicit rating, which is hostile UX. Pressing Play isn't
              // a rating signal.
            }}
              disabled={isTv && detailLoading}
              className="flex items-center gap-2 text-sm font-bold"
              style={{
                color: isTv && detailLoading ? 'var(--text-muted)' : 'var(--accent-gold)',
                background: 'none',
                border: 'none',
                cursor: isTv && detailLoading ? 'progress' : 'pointer',
                padding: 0,
              }}>
              <PlayCircle size={16} /> {isTv ? 'Watch Series' : 'Watch Now'}
            </button>
          )}
          {showPlayer && tmdbId && (
            <FullScreenPlayer
              tmdbId={tmdbId}
              title={displayMovie.title}
              mediaType={mediaType}
              seasons={displayMovie.seasons}
              onClose={() => setShowPlayer(false)}
            />
          )}
        </div>
      </div>
    </div>
  )

  // Render modal in a portal at document.body level
  return createPortal(modalContent, document.body)
}

// ── Compact row (Recommendations list) ───────────────────────────────────────

export function MovieCard({ rec, rank, compact = true }: MovieCardProps) {
  const navigate = useNavigate()
  const { movie, score, is_exploration } = rec
  const poster = tmdbPoster(movie.poster_path, 'w185')
  const pct = Math.round(score * 100)
  const barColor = scoreColor(score)

  const handleClick = () => {
    const id = movie.tmdb_id ?? movie.id
    if (!id) return
    const mt = movie.media_type ?? 'movie'
    navigate(`/title/${mt}/${id}`)
  }

  return (
    <>
      <button
        onClick={handleClick}
        className={cn(
          'w-full text-left transition-all animate-fade-in',
          compact
            ? 'flex items-center gap-3 rounded-xl px-3 py-2.5 hover:brightness-110'
            : 'poster-card group relative',
        )}
        style={compact
          ? { background: 'var(--bg-card)', border: '1px solid var(--border)', cursor: 'pointer', animationDelay: `${((rank ?? 1) - 1) * 0.045}s` }
          : { cursor: 'pointer', background: 'none', border: 'none', padding: 0 }
        }
      >
        {compact ? (
          <>
            {rank && (
              <span className="font-black text-base w-7 flex-shrink-0 text-center" style={{ color: 'var(--accent-gold)' }}>
                {rank}
              </span>
            )}
            <div className="w-9 h-13 flex-shrink-0 rounded overflow-hidden" style={{ height: '52px', width: '36px' }}>
              {poster
                ? <img src={poster} alt={movie.title} className="w-full h-full object-cover" loading="lazy" />
                : <div className="w-full h-full" style={{ background: '#1a1a2e' }} />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-sm text-white truncate">{movie.title}</p>
              <p className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
                {[movie.year, (movie.genres ?? []).slice(0, 2).join(' · ')].filter(Boolean).join(' · ')}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {is_exploration && (
                <span className="text-white text-[8px] font-black px-1.5 py-0.5 rounded-full uppercase" style={{ background: 'var(--accent-red)' }}>
                  disc
                </span>
              )}
              <div className="text-right">
                <div className="text-sm font-black" style={{ color: barColor }}>{pct}%</div>
              </div>
            </div>
          </>
        ) : (
          // Poster grid cell - Browse mode with enhanced hover
          <div className="rounded-xl overflow-hidden relative group/card" style={{ border: '1px solid var(--border)' }}>
            {poster
              ? <img src={poster} alt={movie.title} className="w-full aspect-[2/3] object-cover group-hover/card:scale-105 transition-transform duration-300" loading="lazy" />
              : <div className="w-full aspect-[2/3] flex items-center justify-center text-center p-2" style={{ background: 'linear-gradient(135deg,#1a1a2e,#0f3460)' }}>
                  <span className="text-[10px] font-bold text-white leading-tight">{movie.title}</span>
                </div>}
            
            {/* Hover overlay with info */}
            <div className="absolute inset-0 opacity-0 group-hover/card:opacity-100 transition-all duration-200 flex flex-col justify-end p-2.5"
              style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.95) 0%, rgba(0,0,0,0.7) 45%, transparent 80%)' }}>
              <div className="mb-1.5">
                <span className="text-[8px] px-1.5 py-0.5 rounded-full font-bold uppercase tracking-wide"
                  style={{
                    background: movie.media_type === 'tv' ? 'rgba(91,192,190,0.18)' : 'rgba(245,197,24,0.18)',
                    color: movie.media_type === 'tv' ? '#8be0db' : 'var(--accent-gold)',
                    border: `1px solid ${movie.media_type === 'tv' ? 'rgba(91,192,190,0.28)' : 'rgba(245,197,24,0.22)'}`,
                  }}>
                  {movie.media_type === 'tv' ? 'Series' : 'Movie'}
                </span>
              </div>
              <p className="text-white text-[11px] font-bold line-clamp-2 leading-tight mb-1">{movie.title}</p>
              
              <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                {movie.year && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(255,255,255,0.15)', color: '#fff' }}>
                    {movie.year}
                  </span>
                )}
                {movie.vote_average && (
                  <span className="flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(245,197,24,0.2)', color: 'var(--accent-gold)' }}>
                    <Star size={8} fill="currentColor" />
                    {Number(movie.vote_average).toFixed(1)}
                  </span>
                )}
              </div>
              
              {movie.genres && movie.genres.length > 0 && (
                <p className="text-[9px] line-clamp-1 leading-tight" style={{ color: 'rgba(255,255,255,0.7)' }}>
                  {movie.genres.slice(0, 2).join(' · ')}
                </p>
              )}
            </div>
            
            {rank && (
              <div className="absolute top-1.5 left-1.5 w-5 h-5 flex items-center justify-center rounded-full text-[9px] font-black shadow-lg"
                style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}>{rank}</div>
            )}
          </div>
        )}
      </button>

    </>
  )
}

// ── Helper ────────────────────────────────────────────────────────────────────

export function movieToRec(movie: Movie, rank = 1): Recommendation {
  return { movie, score: Math.min((movie.vote_average ?? 5) / 10, 1), rank }
}

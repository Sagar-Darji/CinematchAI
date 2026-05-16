/**
 * Hero strip at the top of the new Profile page.
 *
 * Cinematic backdrop pulled from the user's favorite #1 poster (banner_film_id
 * from the precomputed blob). Avatar + username + 4 taste-first stat chips
 * (Films / Decade lean / Top director / Top genre) underneath. Below the
 * chips: the rotating caption (on-this-day / recent / streak / random pick),
 * and a 'Refreshing…' badge when the analytics blob is stale.
 *
 * Everything renders from precomputed data — no derivation at view time.
 */
import { useEffect, useState } from 'react'
import { Camera, Loader2, RefreshCw } from 'lucide-react'
import type { ProfileCoreResponse } from '@/lib/api'
import { CaptionRotator } from './CaptionRotator'

interface Props {
  core: ProfileCoreResponse
  isRefreshing?: boolean
  onAvatarClick?: () => void
}

export function ProfileHeader({ core, isRefreshing, onAvatarClick }: Props) {
  const banner = useBanner(core.identity.banner_film_id)
  const chips = core.identity.stat_chips
  const avatarUrl = core.identity.avatar_url ?? null

  return (
    <header
      className="relative overflow-hidden rounded-2xl"
      style={{
        background: 'linear-gradient(180deg, rgba(245,197,24,0.12) 0%, var(--bg-card) 100%)',
        border: '1px solid var(--border)',
      }}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 -z-0"
        style={{
          backgroundImage: banner ? `url(${banner})` : 'none',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          filter: 'blur(48px) brightness(0.45)',
          opacity: banner ? 0.45 : 0,
        }}
      />
      <div className="relative z-10 p-6 md:p-8 flex flex-col gap-5">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onAvatarClick}
            aria-label="Change avatar"
            className="relative group rounded-full"
            style={{ width: 88, height: 88, background: 'var(--bg-card)', border: '2px solid var(--accent-gold)', cursor: 'pointer', padding: 0 }}
          >
            {avatarUrl ? (
              <img src={avatarUrl} alt="" style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }} />
            ) : (
              <span className="flex items-center justify-center w-full h-full text-3xl font-bold text-white" style={{ borderRadius: '50%' }}>
                {(core.identity.username || core.user_id || '?').charAt(0).toUpperCase()}
              </span>
            )}
            <span
              className="absolute inset-0 flex items-center justify-center transition-opacity opacity-0 group-hover:opacity-100"
              style={{ background: 'rgba(0,0,0,0.4)', borderRadius: '50%' }}
            >
              <Camera size={20} className="text-white" />
            </span>
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl md:text-3xl font-bold text-white truncate">
              {core.identity.username ?? core.user_id}
            </h1>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {core.live_total.toLocaleString()} {core.live_total === 1 ? 'film' : 'films'}
            </p>
          </div>
          {isRefreshing && (
            <span
              className="hidden sm:inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full"
              style={{ background: 'var(--bg-overlay)', color: 'var(--accent-gold)', border: '1px solid var(--border)' }}
            >
              <Loader2 size={12} className="animate-spin" />
              Refreshing…
            </span>
          )}
        </div>

        {/* 4 taste-first chips */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <StatChip label="Films" value={chips.films ?? 0} />
          <StatChip label="Decade lean" value={chips.decade_lean ?? '—'} />
          <StatChip
            label="Top director"
            value={chips.top_director?.name ?? '—'}
            sub={chips.top_director?.count != null ? `${chips.top_director.count} films` : undefined}
          />
          <StatChip
            label="Top genre"
            value={chips.top_genre?.name ?? '—'}
            sub={chips.top_genre?.count != null ? `${chips.top_genre.count} films` : undefined}
          />
        </div>

        {/* Rotating caption */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CaptionRotator captions={core.identity.captions} />
          {isRefreshing && (
            <span className="sm:hidden inline-flex items-center gap-1.5 text-xs" style={{ color: 'var(--accent-gold)' }}>
              <RefreshCw size={12} className="animate-spin" />
              Refreshing
            </span>
          )}
        </div>
      </div>
    </header>
  )
}

function StatChip({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div
      className="rounded-xl px-3 py-2.5"
      style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)' }}
    >
      <p className="text-[10px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
        {label}
      </p>
      <p className="text-base font-bold text-white truncate" title={String(value)}>
        {value}
      </p>
      {sub && (
        <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{sub}</p>
      )}
    </div>
  )
}

// ── Banner image resolver — fetch poster_path for the banner film id ──

function useBanner(bannerFilmId: number | null): string | null {
  const [bg, setBg] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    if (!bannerFilmId) { setBg(null); return }
    import('@/lib/api').then(({ getMediaDetails }) =>
      getMediaDetails(bannerFilmId, 'movie').then((m) => {
        if (cancelled) return
        const p = (m as { poster_path?: string | null } | null)?.poster_path
        setBg(p ? `https://image.tmdb.org/t/p/original${p}` : null)
      }).catch(() => { if (!cancelled) setBg(null) })
    )
    return () => { cancelled = true }
  }, [bannerFilmId])
  return bg
}

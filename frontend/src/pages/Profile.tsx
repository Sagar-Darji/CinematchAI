/**
 * Profile page — clean-slate rewrite.
 *
 * One page, one source of truth. Two API calls on mount:
 *   /profile/core/{user}      — fast first paint (header + favorites + computed_at)
 *   /profile/analytics/{user} — precomputed JSON blob (overview + diary)
 *
 * Tabs are navigation; each tab's content is a card grid. No client-side
 * recomputation, no fallback chains. SWR caches both blobs locally so a
 * hard refresh paints instantly while the network catches up.
 *
 * Letterboxd import lives at /settings/import and is reached from the
 * EmptyState CTA, not from the page itself.
 */
import { useEffect, useMemo, useState } from 'react'
import { useUserStore } from '@/store/useUserStore'
import {
  getProfileCore,
  getProfileAnalytics,
  type ProfileCoreResponse,
  type ProfileAnalyticsResponse,
  type FavoriteItem,
} from '@/lib/api'
import { readCache, writeCache } from '@/lib/cache'
import { Tabs } from '@/components/profile/Tabs'
import { ProfileHeader } from '@/components/profile/ProfileHeader'
import { OverviewCards } from '@/components/profile/OverviewCards'
import { DiaryCards } from '@/components/profile/DiaryCards'
import { LibraryGrid } from '@/components/profile/LibraryGrid'
import { WatchlistGrid } from '@/components/profile/WatchlistGrid'
import { EmptyState } from '@/components/profile/EmptyState'
import { StaleNote } from '@/components/profile/StaleNote'
import { AvatarUploader } from '@/components/profile/AvatarUploader'

type TabKey = 'overview' | 'diary' | 'films' | 'series' | 'watchlist'

export default function Profile() {
  const userId = useUserStore((s) => s.userId)
  const setRatingCount = useUserStore((s) => s.setRatingCount)

  const coreCacheKey = `profile-core-${userId}`
  const analyticsCacheKey = `profile-analytics-${userId}`

  const [core, setCore] = useState<ProfileCoreResponse | null>(
    () => (userId ? readCache<ProfileCoreResponse>(coreCacheKey) : null),
  )
  const [analytics, setAnalytics] = useState<ProfileAnalyticsResponse | null>(
    () => (userId ? readCache<ProfileAnalyticsResponse>(analyticsCacheKey) : null),
  )
  const [coreLoading, setCoreLoading] = useState(!core)
  const [analyticsLoading, setAnalyticsLoading] = useState(!analytics)
  const [tab, setTab] = useState<TabKey>('overview')
  const [editingAvatar, setEditingAvatar] = useState(false)

  // ── Fetch (SWR pattern: cache paints instantly, fetch overwrites) ─────
  useEffect(() => {
    if (!userId) return
    let cancelled = false
    setCoreLoading(!core)
    getProfileCore(userId)
      .then((c) => {
        if (cancelled) return
        setCore(c)
        writeCache(coreCacheKey, c)
        setRatingCount(c.live_total)
      })
      .catch(() => { /* SWR: keep showing cache on error */ })
      .finally(() => { if (!cancelled) setCoreLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  useEffect(() => {
    if (!userId) return
    let cancelled = false
    setAnalyticsLoading(!analytics)
    getProfileAnalytics(userId)
      .then((a) => {
        if (cancelled) return
        setAnalytics(a)
        writeCache(analyticsCacheKey, a)
      })
      .catch(() => { /* keep cache on error */ })
      .finally(() => { if (!cancelled) setAnalyticsLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  // ── Available filter values for Films/Series tabs ─────────────────────
  const availableGenres = useMemo<string[]>(
    () => (analytics?.payload?.overview.top_genres ?? []).map((g) => g.name),
    [analytics],
  )
  const availableDecades = useMemo<number[]>(
    () => (analytics?.payload?.overview.decades ?? []).map((d) => d.decade),
    [analytics],
  )

  if (!userId) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <EmptyState
          title="Sign in to see your profile"
          body="Your taste, your library, your watchlist."
          ctaLabel="Go to login"
          ctaHref="/login"
        />
      </div>
    )
  }

  // ── Cold-start: no analytics yet ──────────────────────────────────────
  const status = analytics?.status
  const isCold = !analyticsLoading && (status === 'missing' || (status === 'pending' && !analytics?.payload))

  // ── Refreshing badge ──────────────────────────────────────────────────
  // True when the server says the blob is stale (manual rating drift) OR
  // when a fetch is in flight after a 'pending' status was seen.
  const isRefreshing = Boolean(
    analytics?.is_stale ||
    core?.is_stale ||
    (status === 'pending'),
  )

  const computedAt = analytics?.computed_at ?? core?.computed_at ?? null

  return (
    <div className="min-h-screen px-4 sm:px-6 md:px-8 pb-16">
      <div className="max-w-5xl mx-auto pt-4 md:pt-6 space-y-6">
        {/* ── Header ───────────────────────────────────────────────────── */}
        {core ? (
          <ProfileHeader
            core={core}
            isRefreshing={isRefreshing}
            onAvatarClick={() => setEditingAvatar(true)}
          />
        ) : (
          <div className="h-48 rounded-2xl animate-pulse" style={{ background: 'var(--bg-card)' }} />
        )}

        {/* ── Tabs ─────────────────────────────────────────────────────── */}
        <Tabs<TabKey>
          active={tab}
          onChange={(v) => setTab(v)}
          options={[
            { value: 'overview',  label: 'Overview'  },
            { value: 'diary',     label: 'Diary'     },
            { value: 'films',     label: 'Films'     },
            { value: 'series',    label: 'Series'    },
            { value: 'watchlist', label: 'Watchlist' },
          ]}
        />

        {/* ── Cold-start CTA blocks everything below ───────────────────── */}
        {isCold && (
          <EmptyState
            title="Your Profile is waiting on some signal"
            body="Rate a few films or import your full Letterboxd ZIP and CinematchAI will read your taste back to you — top genres, decade lean, on-this-day callouts, a layered personality essay, the whole thing."
            ctaLabel="Import from Letterboxd"
            ctaHref="/settings"
          />
        )}

        {/* ── Tab content ──────────────────────────────────────────────── */}
        {!isCold && analytics?.payload && (
          <>
            {tab === 'overview' && (
              <OverviewCards
                userId={userId}
                overview={analytics.payload.overview}
                onFavoritesChange={(items: FavoriteItem[]) => {
                  // Optimistically reflect the change in the SWR cache so a
                  // hard refresh paints the new favorites immediately.
                  setCore((prev) => prev ? { ...prev, favorites: items } : prev)
                  setAnalytics((prev) => prev?.payload
                    ? {
                        ...prev,
                        payload: {
                          ...prev.payload,
                          overview: { ...prev.payload.overview, favorites: items },
                        },
                      }
                    : prev,
                  )
                  if (core)      writeCache(coreCacheKey, { ...core, favorites: items })
                  if (analytics?.payload) {
                    writeCache(analyticsCacheKey, {
                      ...analytics,
                      payload: {
                        ...analytics.payload,
                        overview: { ...analytics.payload.overview, favorites: items },
                      },
                    })
                  }
                }}
              />
            )}
            {tab === 'diary' && (
              <DiaryCards userId={userId} diary={analytics.payload.diary} />
            )}
            {tab === 'films' && (
              <LibraryGrid
                userId={userId}
                mediaType="movie"
                availableGenres={availableGenres}
                availableDecades={availableDecades}
              />
            )}
            {tab === 'series' && (
              <LibraryGrid
                userId={userId}
                mediaType="tv"
                availableGenres={availableGenres}
                availableDecades={availableDecades}
              />
            )}
            {tab === 'watchlist' && <WatchlistGrid />}
            {isRefreshing && computedAt && <StaleNote computedAt={computedAt} />}
          </>
        )}

        {/* Loading state when neither cache nor server has spoken yet */}
        {!isCold && !analytics?.payload && analyticsLoading && (
          <div className="rounded-2xl h-64 animate-pulse" style={{ background: 'var(--bg-card)' }} />
        )}
      </div>

      {editingAvatar && (
        <AvatarUploader
          userId={userId}
          currentUrl={core?.identity.avatar_url ?? null}
          onClose={() => setEditingAvatar(false)}
          onSaved={(url) => {
            if (core) {
              const next: ProfileCoreResponse = {
                ...core,
                identity: { ...core.identity, avatar_url: url },
              }
              setCore(next)
              writeCache(coreCacheKey, next)
            }
            setEditingAvatar(false)
          }}
        />
      )}
    </div>
  )
}

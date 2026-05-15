/**
 * Tiny stale-while-revalidate localStorage cache.
 *
 * The Profile page fires 5 independent fetches on mount (profile, admin,
 * favorites, heatmap, stats). On a hard refresh, every fetch starts cold —
 * which means skeleton flashes for everything except the few numbers we
 * already persist in the Zustand user store (e.g. ratingCount). That made
 * a refresh feel slower than the actual data layer is.
 *
 * Pattern: write fresh API responses here keyed by `slice-userId`. On
 * the next mount, the component lazy-inits its state from cache and
 * paints immediately; the fresh API call still runs in the background
 * and replaces the cached value when it returns. Mutations (save
 * favorites, upload avatar, recompute stats) write directly to cache
 * too so the next refresh shows the right state without waiting.
 *
 * No TTL: stale data is fine because the API call always runs anyway —
 * SWR semantics, not just-a-cache. Quota errors are swallowed.
 */

const PREFIX = "cinematch-swr:"

interface Envelope<T> {
  data: T
  fetchedAt: number
}

export function readCache<T>(key: string): T | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(PREFIX + key)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Envelope<T>
    return (parsed?.data ?? null) as T | null
  } catch {
    return null
  }
}

export function writeCache<T>(key: string, data: T): void {
  if (typeof window === "undefined") return
  try {
    const envelope: Envelope<T> = { data, fetchedAt: Date.now() }
    window.localStorage.setItem(PREFIX + key, JSON.stringify(envelope))
  } catch {
    // quota exceeded / localStorage disabled — silently skip; the API
    // refetch on next load is the fallback.
  }
}

export function deleteCache(key: string): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.removeItem(PREFIX + key)
  } catch {
    /* ignore */
  }
}

/** Clear every cinematch SWR entry — used by the logout cascade. */
export function clearAllCache(): void {
  if (typeof window === "undefined") return
  try {
    const toRemove: string[] = []
    for (let i = 0; i < window.localStorage.length; i++) {
      const k = window.localStorage.key(i)
      if (k && k.startsWith(PREFIX)) toRemove.push(k)
    }
    for (const k of toRemove) window.localStorage.removeItem(k)
  } catch {
    /* ignore */
  }
}

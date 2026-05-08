import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { MediaType } from '@/lib/api'
import {
  listWatchlist,
  addToWatchlistRemote,
  removeFromWatchlistRemote,
  clearWatchlistRemote,
} from '@/lib/api'

export interface WatchlistItem {
  tmdbId: number
  mediaType: MediaType
  title: string
  posterPath?: string
  year?: number
  addedAt: number
}

interface WatchlistState {
  items: WatchlistItem[]
  add: (item: Omit<WatchlistItem, 'addedAt'>) => void
  remove: (tmdbId: number, mediaType: MediaType) => void
  toggle: (item: Omit<WatchlistItem, 'addedAt'>) => void
  has: (tmdbId: number, mediaType: MediaType) => boolean
  clear: () => void
  /** Pull the canonical list from the backend and merge with local state.
   *  Server wins on conflict (added_at). Called once when a logged-in user's
   *  token becomes available. */
  syncFromServer: () => Promise<void>
}

/**
 * Watchlist store. Reads survive offline (localStorage cache), writes are
 * dual-written: optimistic local update + fire-and-forget backend call.
 * On boot we reconcile by pulling the server copy and merging.
 */
export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set, get) => ({
      items: [],

      add: (item) => {
        // Optimistic: skip if already present
        set((state) => {
          if (state.items.some((i) => i.tmdbId === item.tmdbId && i.mediaType === item.mediaType)) {
            return state
          }
          return { items: [{ ...item, addedAt: Date.now() }, ...state.items] }
        })
        // Backend
        addToWatchlistRemote({
          tmdbId: item.tmdbId,
          mediaType: item.mediaType,
          title: item.title,
          posterPath: item.posterPath,
          year: item.year,
        })
      },

      remove: (tmdbId, mediaType) => {
        set((state) => ({
          items: state.items.filter((i) => !(i.tmdbId === tmdbId && i.mediaType === mediaType)),
        }))
        removeFromWatchlistRemote(tmdbId, mediaType)
      },

      toggle: (item) => {
        const { has, add, remove } = get()
        if (has(item.tmdbId, item.mediaType)) remove(item.tmdbId, item.mediaType)
        else add(item)
      },

      has: (tmdbId, mediaType) =>
        get().items.some((i) => i.tmdbId === tmdbId && i.mediaType === mediaType),

      clear: () => {
        set({ items: [] })
        clearWatchlistRemote()
      },

      syncFromServer: async () => {
        const server = await listWatchlist()
        if (!server || server.length === 0) {
          // Server has nothing. If we have local items (from before the user
          // signed in, or first-time sync), push them up. Otherwise no-op.
          const local = get().items
          if (local.length > 0) {
            for (const it of local) {
              await addToWatchlistRemote({
                tmdbId: it.tmdbId,
                mediaType: it.mediaType,
                title: it.title,
                posterPath: it.posterPath,
                year: it.year,
              })
            }
          }
          return
        }
        // Server wins. Replace local state.
        set({
          items: server.map((s) => ({
            tmdbId: s.tmdb_id,
            mediaType: s.media_type,
            title: s.title,
            posterPath: s.poster_path ?? undefined,
            year: s.year ?? undefined,
            addedAt: new Date(s.added_at).getTime() || Date.now(),
          })),
        })
      },
    }),
    { name: 'cinematch-watchlist', version: 1 },
  ),
)

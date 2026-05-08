import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { MediaType } from '@/lib/api'

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
}

/**
 * Local watchlist for "save for later".
 *
 * Currently localStorage-only — cross-device sync is not promised.
 * TODO: sync to backend when /api/v1/watchlist endpoint lands.
 */
export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set, get) => ({
      items: [],
      add: (item) =>
        set((state) => {
          if (state.items.some((i) => i.tmdbId === item.tmdbId && i.mediaType === item.mediaType)) {
            return state
          }
          return { items: [{ ...item, addedAt: Date.now() }, ...state.items] }
        }),
      remove: (tmdbId, mediaType) =>
        set((state) => ({
          items: state.items.filter((i) => !(i.tmdbId === tmdbId && i.mediaType === mediaType)),
        })),
      toggle: (item) => {
        const { has, add, remove } = get()
        if (has(item.tmdbId, item.mediaType)) remove(item.tmdbId, item.mediaType)
        else add(item)
      },
      has: (tmdbId, mediaType) =>
        get().items.some((i) => i.tmdbId === tmdbId && i.mediaType === mediaType),
      clear: () => set({ items: [] }),
    }),
    { name: 'cinematch-watchlist', version: 1 },
  ),
)

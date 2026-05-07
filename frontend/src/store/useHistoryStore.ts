import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { MediaType } from '@/lib/api'

export interface HistoryItem {
  tmdbId: number
  mediaType: MediaType
  title: string
  posterPath?: string
  year?: number
  /** TV: last season the user navigated to inside the player (1-based). */
  lastSeason?: number
  /** TV: last episode the user navigated to inside the player (1-based). */
  lastEpisode?: number
  /** Epoch ms of the most recent player open or navigation. */
  watchedAt: number
}

interface HistoryState {
  items: HistoryItem[]
  /**
   * Add or refresh a title in the watch history. Records the moment the user
   * opened the player. Calling again for the same title bumps it to the top
   * and updates any newer metadata supplied (poster, year, etc.).
   */
  record: (item: Omit<HistoryItem, 'watchedAt'>) => void
  /**
   * Persist the latest season/episode for a TV title as the user navigates
   * inside the player. Safe to call repeatedly.
   */
  setProgress: (tmdbId: number, mediaType: MediaType, season: number, episode: number) => void
  remove: (tmdbId: number, mediaType: MediaType) => void
  clear: () => void
}

const MAX_ITEMS = 60

/**
 * Local "Continue Watching" history.
 *
 * We can't read playback time out of cross-origin embed iframes, so this is
 * a "last opened" signal — not a true resume position. For TV titles we also
 * track the most recent season/episode the user navigated to.
 *
 * TODO: sync to backend when /api/v1/history endpoint lands.
 */
export const useHistoryStore = create<HistoryState>()(
  persist(
    (set, get) => ({
      items: [],

      record: (item) =>
        set((state) => {
          const existing = state.items.find(
            (i) => i.tmdbId === item.tmdbId && i.mediaType === item.mediaType,
          )
          const merged: HistoryItem = {
            ...existing,
            ...item,
            watchedAt: Date.now(),
          }
          const without = state.items.filter(
            (i) => !(i.tmdbId === item.tmdbId && i.mediaType === item.mediaType),
          )
          return { items: [merged, ...without].slice(0, MAX_ITEMS) }
        }),

      setProgress: (tmdbId, mediaType, season, episode) =>
        set((state) => {
          const existing = state.items.find(
            (i) => i.tmdbId === tmdbId && i.mediaType === mediaType,
          )
          if (!existing) return state
          const updated: HistoryItem = {
            ...existing,
            lastSeason: season,
            lastEpisode: episode,
            watchedAt: Date.now(),
          }
          const without = state.items.filter(
            (i) => !(i.tmdbId === tmdbId && i.mediaType === mediaType),
          )
          return { items: [updated, ...without] }
        }),

      remove: (tmdbId, mediaType) =>
        set((state) => ({
          items: state.items.filter(
            (i) => !(i.tmdbId === tmdbId && i.mediaType === mediaType),
          ),
        })),

      clear: () => set({ items: [] }),
    }),
    { name: 'cinematch-history' },
  ),
)

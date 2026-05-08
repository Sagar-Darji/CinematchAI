import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { MediaType } from '@/lib/api'
import {
  listHistory,
  recordWatchHistoryRemote,
  clearHistoryRemote,
} from '@/lib/api'

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
  /** Pull the canonical list from the backend. Server wins on conflict
   *  (watched_at). Called once when a logged-in user's token is available. */
  syncFromServer: () => Promise<void>
}

const MAX_ITEMS = 60

/**
 * "Continue Watching" history. localStorage-cached, dual-written to the
 * backend so it survives cache wipes and crosses devices.
 *
 * We can't read playback time out of cross-origin embed iframes, so this is
 * a "last opened" signal — not a true resume position. For TV titles we also
 * track the most recent season/episode the user navigated to.
 */
export const useHistoryStore = create<HistoryState>()(
  persist(
    (set, get) => ({
      items: [],

      record: (item) => {
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
        })
        recordWatchHistoryRemote({
          tmdbId: item.tmdbId,
          mediaType: item.mediaType,
          title: item.title,
          posterPath: item.posterPath,
          year: item.year,
          lastSeason: item.lastSeason,
          lastEpisode: item.lastEpisode,
        })
      },

      setProgress: (tmdbId, mediaType, season, episode) => {
        const existing = get().items.find(
          (i) => i.tmdbId === tmdbId && i.mediaType === mediaType,
        )
        if (!existing) return
        set((state) => {
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
        })
        recordWatchHistoryRemote({
          tmdbId,
          mediaType,
          title: existing.title,
          posterPath: existing.posterPath,
          year: existing.year,
          lastSeason: season,
          lastEpisode: episode,
        })
      },

      remove: (tmdbId, mediaType) =>
        set((state) => ({
          items: state.items.filter(
            (i) => !(i.tmdbId === tmdbId && i.mediaType === mediaType),
          ),
        })),

      clear: () => {
        set({ items: [] })
        clearHistoryRemote()
      },

      syncFromServer: async () => {
        const server = await listHistory()
        if (!server || server.length === 0) {
          // Push existing local items up so they survive cache wipes.
          const local = get().items
          for (const it of local) {
            await recordWatchHistoryRemote({
              tmdbId: it.tmdbId,
              mediaType: it.mediaType,
              title: it.title,
              posterPath: it.posterPath,
              year: it.year,
              lastSeason: it.lastSeason,
              lastEpisode: it.lastEpisode,
            })
          }
          return
        }
        set({
          items: server.map((s) => ({
            tmdbId: s.tmdb_id,
            mediaType: s.media_type,
            title: s.title,
            posterPath: s.poster_path ?? undefined,
            year: s.year ?? undefined,
            lastSeason: s.last_season ?? undefined,
            lastEpisode: s.last_episode ?? undefined,
            watchedAt: new Date(s.watched_at).getTime() || Date.now(),
          })),
        })
      },
    }),
    { name: 'cinematch-history', version: 1 },
  ),
)

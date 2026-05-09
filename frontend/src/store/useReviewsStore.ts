import { create } from 'zustand'
import type { MediaType, Review } from '@/lib/api'
import { listUserReviews } from '@/lib/api'

const key = (tmdbId: number, mediaType: MediaType) => `${tmdbId}-${mediaType}`

interface State {
  byKey: Record<string, Review>
  /** True once we've fetched the user's full review list at least once
   * this session. Components should call `hydrate(userId)` before reading. */
  hydrated: boolean
  hydrate: (userId: string) => Promise<void>
  upsertLocal: (review: Review) => void
  removeLocal: (tmdbId: number, mediaType: MediaType) => void
  get: (tmdbId: number, mediaType: MediaType) => Review | undefined
  reset: () => void
}

/**
 * In-memory cache of the current user's reviews. Hydrated once per session
 * (not persisted) so the diary view, movie detail, and any other reader
 * shares state without re-fetching. Mutations are mirrored locally so the UI
 * updates immediately after upsert/delete.
 */
export const useReviewsStore = create<State>((set, getState) => ({
  byKey: {},
  hydrated: false,
  hydrate: async (userId: string) => {
    if (getState().hydrated) return
    const items = await listUserReviews(userId)
    const byKey: Record<string, Review> = {}
    for (const r of items) {
      byKey[key(r.tmdb_id, r.media_type)] = r
    }
    set({ byKey, hydrated: true })
  },
  upsertLocal: (review: Review) => {
    set((state) => ({
      byKey: { ...state.byKey, [key(review.tmdb_id, review.media_type)]: review },
    }))
  },
  removeLocal: (tmdbId: number, mediaType: MediaType) => {
    set((state) => {
      const next = { ...state.byKey }
      delete next[key(tmdbId, mediaType)]
      return { byKey: next }
    })
  },
  get: (tmdbId: number, mediaType: MediaType) =>
    getState().byKey[key(tmdbId, mediaType)],
  reset: () => set({ byKey: {}, hydrated: false }),
}))

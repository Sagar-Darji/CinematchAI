import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useWatchlistStore } from './useWatchlistStore'
import { useHistoryStore } from './useHistoryStore'
import { useReviewsStore } from './useReviewsStore'
import { clearAllCache } from '@/lib/cache'

interface UserState {
  userId: string
  email: string
  token: string
  isOnboarded: boolean
  ratingCount: number
  hasSeenTour: boolean
  /** Auto-play the next episode when the current one nears the end. Defaults to true. */
  autoAdvance: boolean
  /** True once Zustand has finished reading from localStorage. Use to gate route rendering. */
  hasHydrated: boolean
  setUserId: (id: string) => void
  setEmail: (email: string) => void
  setToken: (token: string) => void
  setOnboarded: (v: boolean) => void
  setRatingCount: (n: number) => void
  setHasSeenTour: (v: boolean) => void
  setAutoAdvance: (v: boolean) => void
  logout: () => void
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      userId: '',
      email: '',
      token: '',
      isOnboarded: false,
      ratingCount: 0,
      hasSeenTour: false,
      autoAdvance: true,
      hasHydrated: false,
      setUserId: (id) => set({ userId: id }),
      setEmail: (email) => set({ email }),
      setToken: (token) => set({ token }),
      setOnboarded: (v) => set({ isOnboarded: v }),
      setRatingCount: (n) => set({ ratingCount: n }),
      setHasSeenTour: (v) => set({ hasSeenTour: v }),
      setAutoAdvance: (v) => set({ autoAdvance: v }),
      logout: () => {
        // Cascade-clear other persisted stores + the SWR cache so private
        // data does not leak to the next user on a shared device.
        try { useWatchlistStore.getState().clear() } catch { /* ignore */ }
        try { useHistoryStore.getState().clear() } catch { /* ignore */ }
        try { useReviewsStore.getState().reset() } catch { /* ignore */ }
        try { clearAllCache() } catch { /* ignore */ }
        set({ userId: '', email: '', token: '', isOnboarded: false, ratingCount: 0, hasSeenTour: false, autoAdvance: true })
      },
    }),
    {
      name: 'cinematch-user',
      version: 1,
      // hasHydrated is runtime-only — do not persist it
      partialize: (state) => ({
        userId: state.userId,
        email: state.email,
        token: state.token,
        isOnboarded: state.isOnboarded,
        ratingCount: state.ratingCount,
        hasSeenTour: state.hasSeenTour,
        autoAdvance: state.autoAdvance,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) state.hasHydrated = true
      },
    },
  ),
)

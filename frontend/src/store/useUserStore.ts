import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useWatchlistStore } from './useWatchlistStore'
import { useHistoryStore } from './useHistoryStore'

interface UserState {
  userId: string
  email: string
  token: string
  isOnboarded: boolean
  ratingCount: number
  hasSeenTour: boolean
  setUserId: (id: string) => void
  setEmail: (email: string) => void
  setToken: (token: string) => void
  setOnboarded: (v: boolean) => void
  setRatingCount: (n: number) => void
  setHasSeenTour: (v: boolean) => void
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
      setUserId: (id) => set({ userId: id }),
      setEmail: (email) => set({ email }),
      setToken: (token) => set({ token }),
      setOnboarded: (v) => set({ isOnboarded: v }),
      setRatingCount: (n) => set({ ratingCount: n }),
      setHasSeenTour: (v) => set({ hasSeenTour: v }),
      logout: () => {
        // Cascade-clear other persisted stores so private data does not leak
        // to the next user on a shared device.
        try { useWatchlistStore.getState().clear() } catch { /* ignore */ }
        try { useHistoryStore.getState().clear() } catch { /* ignore */ }
        set({ userId: '', email: '', token: '', isOnboarded: false, ratingCount: 0, hasSeenTour: false })
      },
    }),
    { name: 'cinematch-user' },
  ),
)

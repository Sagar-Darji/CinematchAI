import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UserState {
  userId: string
  isOnboarded: boolean
  ratingCount: number
  setUserId: (id: string) => void
  setOnboarded: (v: boolean) => void
  setRatingCount: (n: number) => void
  logout: () => void
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      userId: '',
      isOnboarded: false,
      ratingCount: 0,
      setUserId: (id) => set({ userId: id }),
      setOnboarded: (v) => set({ isOnboarded: v }),
      setRatingCount: (n) => set({ ratingCount: n }),
      logout: () => set({ userId: '', isOnboarded: false, ratingCount: 0 }),
    }),
    { name: 'cinematch-user' },
  ),
)

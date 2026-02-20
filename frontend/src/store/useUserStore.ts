import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UserState {
  userId: string
  email: string
  token: string
  isOnboarded: boolean
  ratingCount: number
  setUserId: (id: string) => void
  setEmail: (email: string) => void
  setToken: (token: string) => void
  setOnboarded: (v: boolean) => void
  setRatingCount: (n: number) => void
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
      setUserId: (id) => set({ userId: id }),
      setEmail: (email) => set({ email }),
      setToken: (token) => set({ token }),
      setOnboarded: (v) => set({ isOnboarded: v }),
      setRatingCount: (n) => set({ ratingCount: n }),
      logout: () => set({ userId: '', email: '', token: '', isOnboarded: false, ratingCount: 0 }),
    }),
    { name: 'cinematch-user' },
  ),
)

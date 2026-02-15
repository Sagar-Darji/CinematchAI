import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function tmdbPoster(path: string | null | undefined, size: 'w185' | 'w300' | 'w500' | 'original' = 'w300') {
  if (!path || path === 'N/A') return null
  return `https://image.tmdb.org/t/p/${size}${path}`
}

export function scoreColor(score: number): string {
  if (score >= 0.7) return '#f5c518'
  if (score >= 0.4) return '#e5a019'
  return '#8a8a9a'
}

export function formatRuntime(minutes: number | null | undefined): string {
  if (!minutes) return ''
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

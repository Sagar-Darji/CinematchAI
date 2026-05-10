import type { AdminProfile } from '@/lib/api'

type Rating = AdminProfile['recent_ratings'][number]

/** Half-star buckets from 0.5 to 5.0 — matches Letterboxd's distribution chart. */
const HALF_STAR_BUCKETS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

/** Snap the stored rating (Letterboxd 0.5–5.0 half-star scale) to its
 * matching half-star bucket. Backend stores the value verbatim — do NOT
 * divide by 2. */
function toHalfStar(rating: number): number {
  if (rating <= 0) return 0.5
  const clamped = Math.max(0.5, Math.min(5, rating))
  return Math.round(clamped * 2) / 2
}

export interface HistogramBucket {
  rating: number
  count: number
}

export function ratingHistogram(ratings: Rating[] | undefined): HistogramBucket[] {
  const counts = new Map<number, number>(HALF_STAR_BUCKETS.map((b) => [b, 0]))
  for (const r of ratings ?? []) {
    if (typeof r.rating !== 'number') continue
    const bucket = toHalfStar(r.rating)
    counts.set(bucket, (counts.get(bucket) ?? 0) + 1)
  }
  return HALF_STAR_BUCKETS.map((b) => ({ rating: b, count: counts.get(b) ?? 0 }))
}

export interface DecadeBucket {
  decade: number
  label: string
  count: number
}

export function decadeBreakdown(ratings: Rating[] | undefined): DecadeBucket[] {
  const counts = new Map<number, number>()
  for (const r of ratings ?? []) {
    if (!r.year) continue
    const decade = Math.floor(r.year / 10) * 10
    counts.set(decade, (counts.get(decade) ?? 0) + 1)
  }
  return Array.from(counts.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([decade, count]) => ({
      decade,
      label: `${String(decade).slice(-2)}s`,
      count,
    }))
}

/** Films watched in the given calendar year. Counts ratings whose timestamp
 * (or fallback `year` field) lands in `year`. */
export function filmsThisYear(ratings: Rating[] | undefined, year: number): number {
  let n = 0
  for (const r of ratings ?? []) {
    if (r.timestamp) {
      const ts = new Date(r.timestamp)
      if (!isNaN(ts.valueOf()) && ts.getFullYear() === year) n += 1
    }
  }
  return n
}

export interface YearInReview {
  year: number
  filmCount: number
  topGenre?: string
  topRating?: { title: string; rating: number; year?: number }
  oldestFilm?: { title: string; year: number }
  newestFilm?: { title: string; year: number }
  totalHalfStars: number
}

export function yearInReview(
  ratings: Rating[] | undefined,
  genres: Record<string, number> | undefined,
  year: number,
): YearInReview {
  const inYear = (ratings ?? []).filter((r) => {
    if (!r.timestamp) return false
    const ts = new Date(r.timestamp)
    return !isNaN(ts.valueOf()) && ts.getFullYear() === year
  })

  let topRating: YearInReview['topRating']
  let oldest: YearInReview['oldestFilm']
  let newest: YearInReview['newestFilm']
  let totalHalfStars = 0
  for (const r of inYear) {
    const stars = toHalfStar(r.rating)
    totalHalfStars += stars
    if (r.title && (!topRating || r.rating > (topRating.rating ?? 0))) {
      topRating = { title: r.title, rating: r.rating, year: r.year }
    }
    if (r.title && r.year != null) {
      if (!oldest || r.year < oldest.year) oldest = { title: r.title, year: r.year }
      if (!newest || r.year > newest.year) newest = { title: r.title, year: r.year }
    }
  }

  // Top genre across all-time (we don't have per-rating genres, so fall back
  // to the overall genres map from the profile endpoint).
  const topGenre = Object.entries(genres ?? {}).sort((a, b) => b[1] - a[1])[0]?.[0]

  return {
    year,
    filmCount: inYear.length,
    topGenre,
    topRating,
    oldestFilm: oldest,
    newestFilm: newest,
    totalHalfStars,
  }
}

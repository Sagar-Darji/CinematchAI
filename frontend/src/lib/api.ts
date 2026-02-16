const BASE = '/api/v1'

export interface Movie {
  tmdb_id: number
  id?: number
  title: string
  year?: number
  genres?: string[]
  overview?: string
  poster_path?: string
  vote_average?: number
  director?: string
  runtime?: number
  original_language?: string
}

export interface Recommendation {
  movie: Movie
  score: number
  rank: number
  explanation?: string
  is_exploration?: boolean
}

export interface RecommendationResult {
  recommendations: Recommendation[]
  context_factors?: Record<string, string>
  processing_steps?: string[]
  trace_id?: string
}

export interface JobStatus {
  status: 'pending' | 'running' | 'complete' | 'failed'
  steps: Array<{ step: string; detail: string; timestamp: number }>
  result?: RecommendationResult
  error?: string
}

export interface UserProfile {
  user_id: string
  total_ratings: number
  genres?: Record<string, number>
  embedding_ready?: boolean
  is_cold_start?: boolean
}

export interface AdminProfile {
  user_id: string
  total_ratings: number
  recent_ratings: Array<{ movie_id: string; rating: number; title?: string; year?: number; timestamp?: string }>
  preferences?: Record<string, unknown>
  is_cold_start?: boolean
  avg_rating_given?: number
  profile_status?: string
}

export interface OnboardingMovie {
  tmdb_id: number
  title: string
  year?: number
  genres?: string[]
  overview?: string
  poster_path?: string
  vote_average?: number
}

// ── Recommendations ───────────────────────────────────────────────────────────

export async function submitRecommendationJob(
  userId: string,
  context: Record<string, unknown>,
  k: number,
  useHybrid = true,
): Promise<string> {
  const res = await fetch(`${BASE}/recommendations/async`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, context, k, use_hybrid: useHybrid }),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Submit failed: ${text}`)
  }
  const data = await res.json()
  return data.job_id as string
}

export async function pollJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${BASE}/recommendations/result/${jobId}`)
  if (!res.ok) throw new Error(`Poll failed: ${res.status}`)
  return res.json()
}

// ── Browse / Search ───────────────────────────────────────────────────────────

export async function getTrending(limit = 40, language?: string): Promise<Movie[]> {
  const params = new URLSearchParams({ time_window: 'week' })
  if (language) params.set('language', language)
  const res = await fetch(`${BASE}/movies/trending?${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return (data.movies ?? []).slice(0, limit)
}

export async function searchMovies(query: string, limit = 40, language?: string): Promise<Movie[]> {
  const params = new URLSearchParams({ query, limit: String(limit) })
  if (language) params.set('language', language)
  const res = await fetch(`${BASE}/movies/search?${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.movies ?? []
}

export async function discoverByGenre(genre: string, limit = 40, language?: string): Promise<Movie[]> {
  const params = new URLSearchParams({ genre, limit: String(limit) })
  if (language) params.set('language', language)
  const res = await fetch(`${BASE}/movies/discover?${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.movies ?? []
}

// ── Users ────────────────────────────────────────────────────────────────────

export async function getUserProfile(userId: string): Promise<UserProfile | null> {
  const res = await fetch(`${BASE}/users/${userId}`)
  if (!res.ok) return null
  return res.json()
}

export async function getAdminProfile(userId: string): Promise<AdminProfile | null> {
  const res = await fetch(`${BASE}/admin/users/${userId}/profile`)
  if (!res.ok) return null
  return res.json()
}

export async function getSystemStats(): Promise<{ chromadb_count: number; total_users: number; total_ratings: number } | null> {
  const res = await fetch(`${BASE}/admin/stats`)
  if (!res.ok) return null
  return res.json()
}

export async function getOnboardingMovies(k = 20): Promise<OnboardingMovie[]> {
  const res = await fetch(`${BASE}/users/onboarding-movies?k=${k}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.movies ?? []
}

export async function onboardUser(
  userId: string,
  ratings: Record<string, number>,
): Promise<void> {
  await fetch(`${BASE}/users/onboard`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, ratings }),
  })
}

export async function importLetterboxd(userId: string, csvContent: string): Promise<{ job_id: string; total_movies: number }> {
  const res = await fetch(`${BASE}/users/import/letterboxd`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, csv_content: csvContent }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function pollImportJob(jobId: string): Promise<{ status: string; progress: number; result?: unknown }> {
  const res = await fetch(`${BASE}/users/jobs/${jobId}`)
  if (!res.ok) throw new Error('Job not found')
  return res.json()
}

export async function submitFeedback(userId: string, movieId: number, rating: number): Promise<void> {
  await fetch(`${BASE}/users/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, movie_id: String(movieId), rating }),
  })
}

/** Record an implicit interaction signal (fire-and-forget). */
export function recordInteraction(
  userId: string,
  movieId: number,
  action: 'clicked' | 'watched' | 'dismissed',
): void {
  if (!userId || !movieId) return
  const params = new URLSearchParams({
    user_id: userId,
    movie_id: String(movieId),
    action,
  })
  // Use sendBeacon for dismissals so it survives tab close; fetch for others.
  if (action === 'dismissed' && navigator.sendBeacon) {
    navigator.sendBeacon(`${BASE}/users/interaction?${params}`)
  } else {
    fetch(`${BASE}/users/interaction?${params}`, { method: 'POST' }).catch(() => {})
  }
}

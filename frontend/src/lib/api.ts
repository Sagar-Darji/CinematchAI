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

export async function getRecommendations(
  userId: string,
  context: Record<string, unknown>,
  k: number,
): Promise<RecommendationResult> {
  const res = await fetch(`${BASE}/recommendations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, context, k }),
  })
  if (!res.ok) throw new Error(`Recommendations failed: ${res.status}`)
  return res.json()
}

// ── Browse / Search ───────────────────────────────────────────────────────────

export async function getTrending(limit = 20): Promise<Movie[]> {
  const res = await fetch(`${BASE}/movies/trending?limit=${limit}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.movies ?? data ?? []
}

export async function searchMovies(query: string, limit = 20): Promise<Movie[]> {
  const res = await fetch(`${BASE}/movies/search?q=${encodeURIComponent(query)}&limit=${limit}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.movies ?? data ?? []
}

export async function getMoviesByGenre(genre: string, limit = 20): Promise<Movie[]> {
  const res = await fetch(`${BASE}/movies/discover?genre=${encodeURIComponent(genre)}&limit=${limit}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.movies ?? data ?? []
}

// ── Users ────────────────────────────────────────────────────────────────────

export async function getUserProfile(userId: string): Promise<UserProfile | null> {
  const res = await fetch(`${BASE}/users/${userId}`)
  if (!res.ok) return null
  return res.json()
}

export async function submitFeedback(userId: string, movieId: number, rating: number): Promise<void> {
  await fetch(`${BASE}/users/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, movie_id: String(movieId), rating }),
  })
}

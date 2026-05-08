const API_URL = (import.meta.env.VITE_API_URL ?? '').trim().replace(/\/+$/, '')
const BASE = API_URL ? `${API_URL}/api/v1` : '/api/v1'
const AUTH_BASE = API_URL ? `${API_URL}/api/v1/auth` : '/api/v1/auth'
const AUTH_BASE_FALLBACK = '/api/v1/auth'

// ── Auth header helper ────────────────────────────────────────────────────────
// We can't import the Zustand store directly (circular dep), so we read the
// persisted JSON straight out of localStorage. The shape matches
// useUserStore's persist({ name: 'cinematch-user' }) state.

function readPersistedToken(): string {
  try {
    const raw = localStorage.getItem('cinematch-user')
    if (!raw) return ''
    const parsed = JSON.parse(raw) as { state?: { token?: string } }
    return parsed?.state?.token ?? ''
  } catch {
    return ''
  }
}

export function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = readPersistedToken()
  return {
    ...(extra ?? {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

/**
 * If a fetch returns 401, the token is invalid/expired. Clear persisted state
 * and redirect to /login. Returns the response untouched so callers can still
 * inspect non-401 statuses.
 */
function handle401IfNeeded(res: Response): Response {
  if (res.status !== 401) return res
  try {
    localStorage.removeItem('cinematch-user')
    localStorage.removeItem('cinematch-watchlist')
    localStorage.removeItem('cinematch-history')
  } catch { /* ignore */ }
  // Avoid loops: only redirect if we're not already on a public auth route.
  const path = window.location.pathname
  const isAuthRoute = ['/login', '/register', '/forgot-password', '/reset-password'].includes(path)
  if (!isAuthRoute) {
    const next = encodeURIComponent(path + window.location.search)
    window.location.href = `/login?next=${next}`
  }
  return res
}

function isNetworkError(err: unknown): boolean {
  if (!(err instanceof TypeError)) return false
  const message = err.message.toLowerCase()
  return (
    message.includes('failed to fetch') ||
    message.includes('load failed') ||
    message.includes('networkerror') ||
    message.includes('network request failed')
  )
}

function toNetworkError(action: string, err: unknown): never {
  if (isNetworkError(err)) {
    const target = API_URL || window.location.origin
    throw new Error(`Cannot reach the API server at ${target}. Check VITE_API_URL or the /api proxy.`)
  }
  throw err instanceof Error ? err : new Error(action)
}

async function authFetch(path: string, init: RequestInit): Promise<Response> {
  const primaryUrl = `${AUTH_BASE}${path}`
  try {
    return await fetch(primaryUrl, init)
  } catch (err: unknown) {
    // If VITE_API_URL is set but unreachable, retry via same-origin /api proxy.
    if (isNetworkError(err) && API_URL) {
      const res = await fetch(`${AUTH_BASE_FALLBACK}${path}`, init)
      // If the same-origin path has no real proxy (e.g. Amplify SPA hosting),
      // it responds with index.html. Reject that instead of feeding HTML to res.json().
      const ct = res.headers.get('content-type') ?? ''
      if (!ct.includes('application/json')) {
        throw new Error(`Cannot reach the API server at ${API_URL}. Check VITE_API_URL or the /api proxy.`)
      }
      return res
    }
    throw err
  }
}

export interface AuthResponse {
  token: string
  user_id: string
  email: string
  is_new_user: boolean
}

export type MediaType = 'movie' | 'tv'

export async function registerUser(username: string, email: string, password: string): Promise<AuthResponse> {
  try {
    const res = await authFetch('/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Registration failed' }))
      throw new Error(err.detail || 'Registration failed')
    }
    return res.json()
  } catch (err: unknown) {
    toNetworkError('Registration failed', err)
  }
}

export async function loginWithPassword(identifier: string, password: string): Promise<AuthResponse> {
  try {
    const res = await authFetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }))
      throw new Error(err.detail || 'Login failed')
    }
    return res.json()
  } catch (err: unknown) {
    toNetworkError('Login failed', err)
  }
}

export async function googleAuth(idToken: string, username?: string): Promise<AuthResponse> {
  try {
    const res = await authFetch('/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_token: idToken, username }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Google sign-in failed' }))
      throw new Error(err.detail || 'Google sign-in failed')
    }
    return res.json()
  } catch (err: unknown) {
    toNetworkError('Google sign-in failed', err)
  }
}

export async function renameUser(oldUserId: string, newUsername: string, token: string): Promise<AuthResponse> {
  try {
    const res = await authFetch('/rename-user', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_user_id: oldUserId, new_username: newUsername, token }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Rename failed' }))
      throw new Error(err.detail || 'Rename failed')
    }
    return res.json()
  } catch (err: unknown) {
    toNetworkError('Rename failed', err)
  }
}


export interface Season {
  season_number: number
  name?: string
  episode_count?: number
  air_date?: string
  poster_path?: string
}

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
  creator?: string
  runtime?: number
  original_language?: string
  media_type?: MediaType
  season_count?: number
  episode_count?: number
  seasons?: Season[]
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
  const res = handle401IfNeeded(await fetch(`${BASE}/recommendations/async`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ user_id: userId, context, k, use_hybrid: useHybrid }),
  }))
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Submit failed: ${text}`)
  }
  const data = await res.json()
  return data.job_id as string
}

export async function pollJobStatus(jobId: string): Promise<JobStatus> {
  const res = handle401IfNeeded(await fetch(`${BASE}/recommendations/result/${jobId}`, {
    headers: authHeaders(),
  }))
  if (!res.ok) throw new Error(`Poll failed: ${res.status}`)
  return res.json()
}

// ── Browse / Search ───────────────────────────────────────────────────────────

export async function getTrending(limit = 40, language?: string, page = 1, mediaType: MediaType = 'movie'): Promise<Movie[]> {
  const params = new URLSearchParams({ time_window: 'week' })
  params.set('media_type', mediaType)
  if (language) params.set('language', language)
  if (page > 1) params.set('page', String(page))
  const res = await fetch(`${BASE}/movies/trending?${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return (data.movies ?? []).slice(0, limit)
}

export async function searchMovies(query: string, limit = 40, language?: string, page = 1, mediaType: MediaType = 'movie'): Promise<Movie[]> {
  const params = new URLSearchParams({ query, limit: String(limit) })
  params.set('media_type', mediaType)
  if (language) params.set('language', language)
  if (page > 1) params.set('page', String(page))
  const res = await fetch(`${BASE}/movies/search?${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.movies ?? []
}

export async function discoverByGenre(genre: string, limit = 40, language?: string, page = 1, mediaType: MediaType = 'movie'): Promise<Movie[]> {
  const params = new URLSearchParams({ genre, limit: String(limit) })
  params.set('media_type', mediaType)
  if (language) params.set('language', language)
  if (page > 1) params.set('page', String(page))
  const res = await fetch(`${BASE}/movies/discover?${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.movies ?? []
}

export async function getMediaDetails(tmdbId: number, mediaType: MediaType = 'movie'): Promise<Movie | null> {
  const params = new URLSearchParams({ media_type: mediaType })
  const res = await fetch(`${BASE}/movies/${tmdbId}?${params}`)
  if (!res.ok) return null
  return res.json()
}

// ── Users ────────────────────────────────────────────────────────────────────

export async function getUserProfile(userId: string): Promise<UserProfile | null> {
  const res = handle401IfNeeded(await fetch(`${BASE}/users/${userId}`, { headers: authHeaders() }))
  if (!res.ok) return null
  return res.json()
}

export async function getAdminProfile(userId: string): Promise<AdminProfile | null> {
  const res = handle401IfNeeded(await fetch(`${BASE}/admin/users/${userId}/profile`, { headers: authHeaders() }))
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

export async function checkUserExists(userId: string): Promise<{ exists: boolean; total_ratings: number }> {
  const res = await fetch(`${BASE}/users/${encodeURIComponent(userId)}/exists`)
  if (!res.ok) return { exists: false, total_ratings: 0 }
  return res.json()
}

export async function onboardUser(
  userId: string,
  ratings: Record<string, number>,
): Promise<void> {
  handle401IfNeeded(await fetch(`${BASE}/users/onboard`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ user_id: userId, ratings }),
  }))
}

export async function importLetterboxd(userId: string, csvContent: string): Promise<{ job_id: string; total_movies: number }> {
  const res = handle401IfNeeded(await fetch(`${BASE}/users/import/letterboxd`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ user_id: userId, csv_content: csvContent }),
  }))
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function pollImportJob(jobId: string): Promise<{ status: string; progress: number; result?: unknown }> {
  const res = handle401IfNeeded(await fetch(`${BASE}/users/jobs/${jobId}`, { headers: authHeaders() }))
  if (!res.ok) throw new Error('Job not found')
  return res.json()
}

export async function submitFeedback(userId: string, movieId: number, rating: number): Promise<void> {
  handle401IfNeeded(await fetch(`${BASE}/users/feedback`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ user_id: userId, movie_id: String(movieId), rating }),
  }))
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
  // sendBeacon doesn't support custom headers, so we can't attach the bearer.
  // For dismissals we still fire it (server treats unauthenticated record as
  // a no-op now). For others, normal fetch with auth header.
  if (action === 'dismissed' && navigator.sendBeacon) {
    navigator.sendBeacon(`${BASE}/users/interaction?${params}`)
  } else {
    fetch(`${BASE}/users/interaction?${params}`, {
      method: 'POST',
      headers: authHeaders(),
    }).catch(() => {})
  }
}

// ── Watchlist (server-side) ──────────────────────────────────────────────────

export interface ServerWatchlistItem {
  user_id: string
  tmdb_id: number
  media_type: 'movie' | 'tv'
  title: string
  poster_path?: string | null
  year?: number | null
  added_at: string  // ISO timestamp from Postgres
}

export async function listWatchlist(): Promise<ServerWatchlistItem[]> {
  try {
    const res = handle401IfNeeded(await fetch(`${BASE}/watchlist`, { headers: authHeaders() }))
    if (!res.ok) return []
    const data = await res.json()
    return data.items ?? []
  } catch {
    return []
  }
}

export async function addToWatchlistRemote(item: {
  tmdbId: number
  mediaType: 'movie' | 'tv'
  title: string
  posterPath?: string
  year?: number
}): Promise<void> {
  try {
    handle401IfNeeded(await fetch(`${BASE}/watchlist`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        tmdb_id: item.tmdbId,
        media_type: item.mediaType,
        title: item.title,
        poster_path: item.posterPath ?? null,
        year: item.year ?? null,
      }),
    }))
  } catch { /* offline / unauth — local copy survives */ }
}

export async function removeFromWatchlistRemote(
  tmdbId: number,
  mediaType: 'movie' | 'tv',
): Promise<void> {
  try {
    handle401IfNeeded(await fetch(`${BASE}/watchlist/${mediaType}/${tmdbId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    }))
  } catch { /* swallow */ }
}

export async function clearWatchlistRemote(): Promise<void> {
  try {
    handle401IfNeeded(await fetch(`${BASE}/watchlist`, {
      method: 'DELETE',
      headers: authHeaders(),
    }))
  } catch { /* swallow */ }
}

// ── History (server-side) ────────────────────────────────────────────────────

export interface ServerHistoryItem {
  user_id: string
  tmdb_id: number
  media_type: 'movie' | 'tv'
  title: string
  poster_path?: string | null
  year?: number | null
  last_season?: number | null
  last_episode?: number | null
  watched_at: string
}

export async function listHistory(limit = 60): Promise<ServerHistoryItem[]> {
  try {
    const res = handle401IfNeeded(await fetch(`${BASE}/history?limit=${limit}`, { headers: authHeaders() }))
    if (!res.ok) return []
    const data = await res.json()
    return data.items ?? []
  } catch {
    return []
  }
}

export async function recordWatchHistoryRemote(item: {
  tmdbId: number
  mediaType: 'movie' | 'tv'
  title: string
  posterPath?: string
  year?: number
  lastSeason?: number
  lastEpisode?: number
}): Promise<void> {
  try {
    handle401IfNeeded(await fetch(`${BASE}/history`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        tmdb_id: item.tmdbId,
        media_type: item.mediaType,
        title: item.title,
        poster_path: item.posterPath ?? null,
        year: item.year ?? null,
        last_season: item.lastSeason ?? null,
        last_episode: item.lastEpisode ?? null,
      }),
    }))
  } catch { /* swallow */ }
}

export async function clearHistoryRemote(): Promise<void> {
  try {
    handle401IfNeeded(await fetch(`${BASE}/history`, {
      method: 'DELETE',
      headers: authHeaders(),
    }))
  } catch { /* swallow */ }
}

// ── /me ─────────────────────────────────────────────────────────────────────

export interface MeResponse {
  user_id: string
  email: string
  auth_provider: string
}

/**
 * Validate the persisted bearer token. Returns the user info on success.
 * On 401 the api wrapper has already cleared local state and redirected;
 * callers can treat null as "no valid session".
 */
export async function getCurrentUser(): Promise<MeResponse | null> {
  try {
    const res = handle401IfNeeded(await fetch(`${AUTH_BASE}/me`, { headers: authHeaders() }))
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

// ── Release Calendar ──────────────────────────────────────────────────────────

export async function getNowPlaying(region?: string, language?: string, page = 1): Promise<Movie[]> {
  const params = new URLSearchParams()
  if (region) params.set('region', region)
  if (language) params.set('language', language)
  if (page > 1) params.set('page', String(page))
  const res = await fetch(`${BASE}/movies/now-playing?${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.movies ?? []
}

export async function getUpcoming(region?: string, language?: string, page = 1): Promise<Movie[]> {
  const params = new URLSearchParams()
  if (region) params.set('region', region)
  if (language) params.set('language', language)
  if (page > 1) params.set('page', String(page))
  const res = await fetch(`${BASE}/movies/upcoming?${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.movies ?? []
}

export async function getOttReleases(providers?: string, region = 'US', language?: string, days = 30, page = 1): Promise<Movie[]> {
  const params = new URLSearchParams({ region, days: String(days) })
  if (providers) params.set('providers', providers)
  if (language) params.set('language', language)
  if (page > 1) params.set('page', String(page))
  const res = await fetch(`${BASE}/movies/ott-releases?${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.movies ?? []
}

// ── CineDigest ───────────────────────────────────────────────────────────────

export type DigestCategory = 'all' | 'bollywood' | 'hollywood' | 'trailer' | 'casting' | 'leak' | 'ott' | 'general'
export type DigestLang = 'all' | 'hindi' | 'english'

export interface DigestItem {
  id: string
  source_name: string
  source_url: string
  title: string
  description: string
  image_url: string | null
  published_at: string
  category: DigestCategory
  lang: DigestLang
  bullets: string[]
  headline: string
  fetched_at: string
}

export interface DigestResponse {
  items: DigestItem[]
  total: number
  last_refresh: string | null
}

export async function fetchDigest(
  category: DigestCategory = 'all',
  lang: DigestLang = 'all',
  limit = 40,
  offset = 0,
): Promise<DigestResponse> {
  const params = new URLSearchParams({ category, lang, limit: String(limit), offset: String(offset) })
  const res = await fetch(`${BASE}/news/digest?${params}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function triggerDigestRefresh(): Promise<void> {
  await fetch(`${BASE}/news/refresh`, { method: 'POST' })
}

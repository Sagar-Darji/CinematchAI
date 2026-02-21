import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Upload, Star, ArrowRight, Loader2, Check, Search, X } from 'lucide-react'
import { useUserStore } from '@/store/useUserStore'
import { getOnboardingMovies, onboardUser, importLetterboxd, pollImportJob, searchMovies, renameUser, type OnboardingMovie } from '@/lib/api'
import { tmdbPoster, cn } from '@/lib/utils'

type Step = 'username' | 'method' | 'rate' | 'letterboxd' | 'importing' | 'done'

const STARS = [1, 2, 3, 4, 5]

export default function Onboarding() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { userId: existingUserId, token: existingToken, setUserId, setToken, setOnboarded, setRatingCount } = useUserStore()

  // ?registered=1 → came from password Register (username already chosen, skip username step)
  // Google new users and anonymous users always see the username step
  const alreadyRegistered = searchParams.get('registered') === '1'
  const isGoogleUser = !!existingUserId && !alreadyRegistered
  const [step, setStep] = useState<Step>(alreadyRegistered ? 'method' : 'username')
  const [username, setUsername] = useState(existingUserId || '')
  const [movies, setMovies] = useState<OnboardingMovie[]>([])
  const [ratings, setRatings] = useState<Record<string, number>>({})
  const [loadingMovies, setLoadingMovies] = useState(false)
  const [csvContent, setCsvContent] = useState('')
  const [importJob, setImportJob] = useState<{ id: string; total: number } | null>(null)
  const [importProgress, setImportProgress] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<OnboardingMovie[]>([])
  const [searching, setSearching] = useState(false)

  // Load onboarding movies when entering rate step
  useEffect(() => {
    if (step === 'rate' && movies.length === 0) {
      setLoadingMovies(true)
      getOnboardingMovies(20).then((m) => {
        setMovies(m as OnboardingMovie[])
        setLoadingMovies(false)
      })
    }
  }, [step, movies.length])

  // Search movies with debounce
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([])
      return
    }
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const results = await searchMovies(searchQuery.trim(), 10)
        setSearchResults(results as OnboardingMovie[])
      } catch {
        setSearchResults([])
      } finally {
        setSearching(false)
      }
    }, 400)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Poll import job
  useEffect(() => {
    if (step !== 'importing' || !importJob) return
    const interval = setInterval(async () => {
      try {
        const data = await pollImportJob(importJob.id)
        setImportProgress(data.progress ?? 0)
        if (data.status === 'completed') {
          clearInterval(interval)
          setUserId(username)
          setOnboarded(true)
          setRatingCount(importJob.total)
          setStep('done')
          setTimeout(() => navigate('/recommendations'), 1500)
        } else if (data.status === 'failed') {
          clearInterval(interval)
          setError('Import failed. Please try again.')
          setStep('letterboxd')
        }
      } catch { /* keep polling */ }
    }, 2000)
    return () => clearInterval(interval)
  }, [step, importJob, username, navigate, setUserId, setOnboarded, setRatingCount])

  const handleUsername = async () => {
    if (!username.trim()) return
    // If this is a Google user who changed their auto-generated username, rename in DB
    if (existingUserId && username.trim() !== existingUserId && existingToken) {
      setSubmitting(true)
      setError('')
      try {
        const auth = await renameUser(existingUserId, username.trim(), existingToken)
        setUserId(auth.user_id)
        setToken(auth.token)
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Could not set username. Please try another.')
        setSubmitting(false)
        return
      } finally {
        setSubmitting(false)
      }
    } else if (!existingUserId) {
      setUserId(username.trim())
    }
    setStep('method')
  }

  const handleRate = async () => {
    const ratedCount = Object.keys(ratings).length
    if (ratedCount < 5) { setError('Please rate at least 5 movies.'); return }
    setSubmitting(true)
    try {
      await onboardUser(username, ratings)
      setUserId(username)
      setOnboarded(true)
      setRatingCount(ratedCount)
      setStep('done')
      setTimeout(() => navigate('/recommendations'), 1500)
    } catch (e) {
      setError(String(e))
    } finally { setSubmitting(false) }
  }

  const handleLetterboxdUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => setCsvContent(ev.target?.result as string)
    reader.readAsText(file)
  }

  const handleLetterboxdSubmit = async () => {
    if (!csvContent) { setError('Please select your Letterboxd CSV file.'); return }
    setSubmitting(true)
    setError('')
    try {
      const result = await importLetterboxd(username, csvContent)
      setImportJob({ id: result.job_id, total: result.total_movies })
      setStep('importing')
    } catch (e) {
      setError(String(e))
    } finally { setSubmitting(false) }
  }

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-4"
      style={{ background: 'var(--bg-primary)' }}
    >
      <div className="w-full max-w-2xl">
        {/* Brand */}
        <div className="text-center mb-10">
          <p className="text-xs font-bold tracking-[0.3em] uppercase mb-3" style={{ color: 'var(--accent-gold)' }}>
            CineMatch AI
          </p>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight text-white">
            {step === 'username' && 'Welcome'}
            {step === 'method' && 'How do you want to start?'}
            {step === 'rate' && 'Rate a few films'}
            {step === 'letterboxd' && 'Import from Letterboxd'}
            {step === 'importing' && 'Importing your taste…'}
            {step === 'done' && 'All set!'}
          </h1>
          {step === 'username' && (
            <p className="mt-3 text-sm" style={{ color: 'var(--text-muted)' }}>
              Your AI-powered cinema companion. Set up your taste profile to get started.
            </p>
          )}
        </div>

        {/* ── Step: Username ── */}
        {step === 'username' && (
          <div className="flex flex-col gap-3">
            <input
              type="text"
              autoFocus
              placeholder="Choose a username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleUsername()}
              className="w-full px-5 py-4 rounded-xl text-lg outline-none"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            />
            {isGoogleUser && username === existingUserId && (
              <p className="text-xs px-1" style={{ color: 'var(--text-muted)' }}>
                Auto-generated from your Google account. Feel free to change it.
              </p>
            )}
            {error && <p className="text-sm px-1" style={{ color: 'var(--accent-red)' }}>{error}</p>}
            <button
              onClick={handleUsername}
              disabled={submitting || !username.trim()}
              className="flex items-center justify-center gap-2 py-4 rounded-xl font-bold text-base disabled:opacity-40 transition-opacity"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
            >
              {submitting ? <Loader2 size={18} className="animate-spin" /> : <ArrowRight size={18} />}
              Continue
            </button>

            {/* Login link */}
            <p className="text-center text-sm mt-2" style={{ color: 'var(--text-muted)' }}>
              Already have an account?{' '}
              <a
                href="/login"
                className="font-medium hover:underline"
                style={{ color: 'var(--accent-gold)' }}
              >
                Sign in
              </a>
            </p>
          </div>
        )}

        {/* ── Step: Method ── */}
        {step === 'method' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              {
                key: 'rate',
                icon: <Star size={28} style={{ color: 'var(--accent-gold)' }} />,
                title: 'Rate Movies',
                desc: 'Search and rate movies you\'ve watched. We need at least 5 to start.',
              },
              {
                key: 'letterboxd',
                icon: <Upload size={28} style={{ color: 'var(--accent-gold)' }} />,
                title: 'Import Letterboxd',
                desc: 'Upload your Letterboxd ratings CSV. We\'ll import your entire taste profile.',
              },
            ].map(({ key, icon, title, desc }) => (
              <button
                key={key}
                onClick={() => setStep(key as Step)}
                className="text-left p-6 rounded-xl transition-all hover:scale-[1.01]"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', cursor: 'pointer' }}
              >
                <div className="mb-3">{icon}</div>
                <h3 className="font-bold text-white text-lg mb-1">{title}</h3>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{desc}</p>
              </button>
            ))}
          </div>
        )}

        {/* ── Step: Rate movies ── */}
        {step === 'rate' && (
          <div>
            {/* Search bar */}
            <div className="flex items-center gap-2 rounded-xl px-4 py-3 mb-4"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              <Search size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
              <input
                type="text"
                placeholder="Search movies you've watched..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 bg-transparent outline-none text-sm"
                style={{ color: 'var(--text-primary)' }}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                >
                  <X size={16} style={{ color: 'var(--text-muted)' }} />
                </button>
              )}
            </div>

            <p className="text-sm mb-4" style={{ color: 'var(--text-muted)' }}>
              Rated {Object.keys(ratings).length} movies · Need at least 5
            </p>
            {loadingMovies ? (
              /* Skeleton cards while movies load */
              <div className="space-y-3 max-h-[55vh] overflow-y-auto pr-1">
                {Array.from({ length: 10 }).map((_, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-4 rounded-xl p-3"
                    style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
                  >
                    <div className="skeleton w-10 h-14 rounded flex-shrink-0" />
                    <div className="flex-1 space-y-2 min-w-0">
                      <div className="skeleton-text" style={{ width: `${55 + (i % 5) * 8}%` }} />
                      <div className="skeleton-text w-24" style={{ opacity: 0.5 }} />
                    </div>
                    <div className="flex gap-1 flex-shrink-0">
                      {[0,1,2,3,4].map((s) => (
                        <div key={s} className="skeleton w-4 h-4 rounded" />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-3 max-h-[55vh] overflow-y-auto pr-1">
                {/* Show search results if searching */}
                {searchQuery.trim() && (
                  <>
                    {searching ? (
                      <div className="text-center py-6">
                        <Loader2 size={20} className="animate-spin mx-auto" style={{ color: 'var(--accent-gold)' }} />
                        <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>Searching...</p>
                      </div>
                    ) : searchResults.length === 0 ? (
                      <div className="text-center py-6">
                        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No results found for "{searchQuery}"</p>
                      </div>
                    ) : (
                      searchResults.map((movie) => {
                        const id = String(movie.tmdb_id)
                        const poster = tmdbPoster(movie.poster_path, 'w185')
                        const userRating = ratings[id]
                        return (
                          <div
                            key={id}
                            className="flex items-center gap-4 rounded-xl p-3"
                            style={{
                              background: userRating ? 'var(--bg-overlay)' : 'var(--bg-card)',
                              border: `1px solid ${userRating ? 'var(--accent-gold)' : 'var(--border)'}`,
                              transition: 'all 0.2s ease',
                            }}
                          >
                            {poster ? (
                              <img src={poster} alt={movie.title} className="w-10 h-14 object-cover rounded flex-shrink-0" />
                            ) : (
                              <div className="w-10 h-14 rounded flex-shrink-0 flex items-center justify-center text-[9px] text-center"
                                style={{ background: '#1a1a2e', color: 'var(--accent-gold)' }}>
                                {movie.title.slice(0, 10)}
                              </div>
                            )}
                            <div className="flex-1 min-w-0">
                              <p className="font-semibold text-sm text-white truncate">{movie.title}</p>
                              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                                {movie.year} · {(movie.genres ?? []).slice(0, 2).join(', ')}
                              </p>
                            </div>
                            <div className="flex gap-1 flex-shrink-0">
                              {STARS.map((s) => (
                                <button
                                  key={s}
                                  onClick={() => {
                                    setRatings((r) => {
                                      const newRatings = { ...r }
                                      if (newRatings[id] === s) {
                                        delete newRatings[id]
                                      } else {
                                        newRatings[id] = s
                                      }
                                      return newRatings
                                    })
                                  }}
                                  className="transition-transform hover:scale-125"
                                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px' }}
                                >
                                  <Star
                                    size={16}
                                    fill={userRating && userRating >= s ? 'var(--accent-gold)' : 'none'}
                                    style={{ color: userRating && userRating >= s ? 'var(--accent-gold)' : 'var(--border)' }}
                                  />
                                </button>
                              ))}
                            </div>
                          </div>
                        )
                      })
                    )}
                    <div className="border-t pt-3 mt-3" style={{ borderColor: 'var(--border)' }}>
                      <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>Or pick from popular movies:</p>
                    </div>
                  </>
                )}
                
                {/* Show curated movies */}
                {movies.map((movie) => {
                  const id = String(movie.tmdb_id)
                  const poster = tmdbPoster(movie.poster_path, 'w185')
                  const userRating = ratings[id]
                  return (
                    <div
                      key={id}
                      className="flex items-center gap-4 rounded-xl p-3"
                      style={{
                        background: userRating ? 'var(--bg-overlay)' : 'var(--bg-card)',
                        border: `1px solid ${userRating ? 'var(--accent-gold)' : 'var(--border)'}`,
                        transition: 'all 0.2s ease',
                      }}
                    >
                      {poster ? (
                        <img src={poster} alt={movie.title} className="w-10 h-14 object-cover rounded flex-shrink-0" />
                      ) : (
                        <div className="w-10 h-14 rounded flex-shrink-0 flex items-center justify-center text-[9px] text-center"
                          style={{ background: '#1a1a2e', color: 'var(--accent-gold)' }}>
                          {movie.title.slice(0, 10)}
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-sm text-white truncate">{movie.title}</p>
                        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                          {movie.year} · {(movie.genres ?? []).slice(0, 2).join(', ')}
                        </p>
                      </div>
                      <div className="flex gap-1 flex-shrink-0">
                        {STARS.map((s) => (
                          <button
                            key={s}
                            onClick={() => {
                              // Toggle: if clicking the same star, deselect (set to undefined)
                              setRatings((r) => {
                                const newRatings = { ...r }
                                if (newRatings[id] === s) {
                                  delete newRatings[id]
                                } else {
                                  newRatings[id] = s
                                }
                                return newRatings
                              })
                            }}
                            className="transition-transform hover:scale-125"
                            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px' }}
                          >
                            <Star
                              size={16}
                              fill={userRating && userRating >= s ? 'var(--accent-gold)' : 'none'}
                              style={{ color: userRating && userRating >= s ? 'var(--accent-gold)' : 'var(--border)' }}
                            />
                          </button>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
            {error && <p className="text-sm mt-3" style={{ color: 'var(--accent-red)' }}>{error}</p>}
            <button
              onClick={handleRate}
              disabled={submitting || Object.keys(ratings).length < 5}
              className="w-full mt-4 py-3 rounded-xl font-bold flex items-center justify-center gap-2 disabled:opacity-40"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
            >
              {submitting ? <Loader2 size={18} className="animate-spin" /> : <ArrowRight size={18} />}
              Build My Profile
            </button>
          </div>
        )}

        {/* ── Step: Letterboxd import ── */}
        {step === 'letterboxd' && (
          <div className="space-y-4">
            <div className="rounded-xl p-4 text-sm" style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)' }}>
              <p className="font-semibold text-white mb-2">How to export from Letterboxd:</p>
              <ol className="space-y-1" style={{ color: 'var(--text-muted)' }}>
                <li>1. Go to letterboxd.com → Settings → Import & Export</li>
                <li>2. Click <strong className="text-white">Export Your Data</strong></li>
                <li>3. Download the ZIP, extract <code className="text-yellow-400">ratings.csv</code></li>
                <li>4. Upload that file below</li>
              </ol>
            </div>

            <label
              className="flex flex-col items-center justify-center gap-3 rounded-xl p-8 cursor-pointer transition-colors"
              style={{
                border: `2px dashed ${csvContent ? 'var(--accent-gold)' : 'var(--border)'}`,
                background: 'var(--bg-card)',
              }}
            >
              <Upload size={32} style={{ color: csvContent ? 'var(--accent-gold)' : 'var(--text-muted)' }} />
              <span className="text-sm font-medium" style={{ color: csvContent ? 'var(--accent-gold)' : 'var(--text-muted)' }}>
                {csvContent ? 'CSV loaded ✓ — ready to import' : 'Click to select ratings.csv'}
              </span>
              <input type="file" accept=".csv" onChange={handleLetterboxdUpload} className="hidden" />
            </label>

            {error && <p className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</p>}

            <button
              onClick={handleLetterboxdSubmit}
              disabled={submitting || !csvContent}
              className="w-full py-3 rounded-xl font-bold flex items-center justify-center gap-2 disabled:opacity-40"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
            >
              {submitting ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
              Start Import
            </button>
          </div>
        )}

        {/* ── Step: Importing ── */}
        {step === 'importing' && (
          <div className="text-center space-y-6 py-8">
            <Loader2 size={48} className="animate-spin mx-auto" style={{ color: 'var(--accent-gold)' }} />
            <div>
              <p className="text-white font-bold text-lg">Importing your ratings…</p>
              <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
                {importJob?.total ? `${Math.round(importProgress / 100 * importJob.total)} / ${importJob.total} movies` : `${importProgress}% complete`}
              </p>
            </div>
            <div className="score-bar-track max-w-xs mx-auto">
              <div className="score-bar-fill" style={{ width: `${importProgress}%`, background: 'var(--accent-gold)' }} />
            </div>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Building your taste profile in the background…
            </p>
          </div>
        )}

        {/* ── Step: Done ── */}
        {step === 'done' && (
          <div className="text-center py-8">
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
              style={{ background: 'var(--accent-gold)' }}
            >
              <Check size={28} color="#0a0a0f" />
            </div>
            <p className="text-white font-bold text-xl mb-2">Profile created!</p>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Redirecting to your recommendations…</p>
          </div>
        )}

        {/* Back link */}
        {(step === 'method' || step === 'letterboxd') && (
          <button
            onClick={() => { setStep(step === 'letterboxd' ? 'method' : alreadyRegistered ? 'method' : 'username'); setError('') }}
            className="mt-4 text-sm w-full text-center"
            style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            ← Back
          </button>
        )}

        {/* Progress dots */}
        <div className={cn('flex justify-center gap-2 mt-8', step === 'done' && 'invisible')}>
          {(['username','method','rate','done'] as const).map((s, i) => {
            const active = ['username','method','rate','letterboxd'].indexOf(step) >= i
            return (
              <div
                key={s}
                className="w-1.5 h-1.5 rounded-full transition-all"
                style={{ background: active ? 'var(--accent-gold)' : 'var(--border)' }}
              />
            )
          })}
        </div>
      </div>
    </div>
  )
}

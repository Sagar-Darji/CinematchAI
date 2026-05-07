import { useState, useEffect, useRef } from 'react'
import { SlidersHorizontal, RefreshCw, X } from 'lucide-react'
import { submitRecommendationJob, pollJobStatus } from '@/lib/api'
import { useUserStore } from '@/store/useUserStore'
import { useRecommendationStore } from '@/store/useRecommendationStore'
import { FilmStack } from '@/components/recommendations/FilmStack'
import { TraceDisplay } from '@/components/recommendations/TraceDisplay'
import { PageLoader } from '@/components/ui/PageLoader'
import { cn } from '@/lib/utils'

const ALL_AGENTS = [
  'Profile Analyzer', 'Context-Aware', 'Retrieval',
  'Content Intelligence', 'Serendipity', 'Adversarial Critic', 'Explanation', 'Aggregation',
]

const LANGUAGE_MAP: Record<string, string> = {
  English: 'en', Hindi: 'hi', Tamil: 'ta', Telugu: 'te', Malayalam: 'ml',
  Kannada: 'kn', Bengali: 'bn', Gujarati: 'gu', Marathi: 'mr', Punjabi: 'pa',
  Korean: 'ko', Japanese: 'ja', French: 'fr', Spanish: 'es', German: 'de',
  Italian: 'it', Chinese: 'zh', Arabic: 'ar', Portuguese: 'pt', Russian: 'ru',
}

const MOODS = ['happy', 'sad', 'stressed', 'bored', 'thoughtful', 'energetic', 'nostalgic', 'adventurous']
const COMPANIONS = ['alone', 'partner', 'friends', 'family']

export default function Recommendations() {
  const userId = useUserStore((s) => s.userId)
  const {
    recommendations, jobStatus, steps, isPolling, reset,
    setRecommendations, setJobId, setJobStatus, setSteps, setIsPolling,
    setContextFactors,
  } = useRecommendationStore()

  const [mood, setMood] = useState<string[]>([])
  const [companion, setCompanion] = useState('')
  const [language, setLanguage] = useState('')
  const [naturalCtx, setNaturalCtx] = useState('')
  const [k, setK] = useState(10)
  const [yearMin, setYearMin] = useState('')
  const [yearMax, setYearMax] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [overlayOpen, setOverlayOpen] = useState(false)
  const overlayFadeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const isRunning = isPolling || jobStatus === 'running' || jobStatus === 'pending'
  const isDone = jobStatus === 'complete'

  const buildContext = () => {
    const ctx: Record<string, unknown> = {}
    if (mood.length > 0) ctx.mood = mood.join(', ')
    if (companion) ctx.companion = companion
    if (language) {
      ctx.language = LANGUAGE_MAP[language] ?? language.toLowerCase()
    }
    if (naturalCtx) ctx.natural_language_context = naturalCtx
    if (yearMin) ctx.year_min = parseInt(yearMin)
    if (yearMax) ctx.year_max = parseInt(yearMax)
    return ctx
  }

  const startJob = async () => {
    if (!userId) return
    reset()
    setOverlayOpen(true)
    if (overlayFadeTimer.current) clearTimeout(overlayFadeTimer.current)
    setIsPolling(true)
    setJobStatus('pending')

    try {
      const jobId = await submitRecommendationJob(userId, buildContext(), k)
      setJobId(jobId)

      const deadline = Date.now() + 120_000
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 700))
        const data = await pollJobStatus(jobId)
        setSteps(data.steps ?? [])
        setJobStatus(data.status)

        if (data.status === 'complete') {
          setRecommendations(data.result!.recommendations)
          setContextFactors(data.result!.context_factors ?? {})
          setIsPolling(false)
          // Auto-close overlay after a short celebration moment
          overlayFadeTimer.current = setTimeout(() => setOverlayOpen(false), 1800)
          return
        }
        if (data.status === 'failed') {
          setIsPolling(false)
          return
        }
      }
      setIsPolling(false)
    } catch (err) {
      console.error(err)
      setIsPolling(false)
      setJobStatus('failed')
    }
  }

  useEffect(() => {
    if (userId && recommendations.length === 0 && !isPolling && jobStatus === null) {
      startJob()
    }
  }, [userId]) // eslint-disable-line react-hooks/exhaustive-deps

  const currentRunningStep = ALL_AGENTS[steps.length] ?? null
  const pipelinePct = isDone
    ? 100
    : isRunning
    ? Math.max(5, Math.round((steps.length / 8) * 85))
    : 0

  const activeFilters = [...mood, language, companion, naturalCtx, yearMin, yearMax].filter(Boolean).length

  return (
    <div className="flex min-h-screen relative" style={{ background: 'var(--bg-primary)' }}>
      <PageLoader visible={isRunning} value={pipelinePct} />

      <div className="flex-1 min-w-0">
        {/* Sticky header */}
        <div
          className="sticky top-14 z-20 flex items-center justify-between px-5 md:px-8 py-4 border-b"
          style={{ background: 'rgba(10,10,15,0.92)', backdropFilter: 'blur(12px)', borderColor: 'var(--border)' }}
        >
          <div>
            <p className="text-[10px] font-bold tracking-[0.3em] uppercase" style={{ color: 'var(--accent-gold)' }}>AI-Curated</p>
            <h1 className="text-xl font-black tracking-tight text-white leading-none">
              For You
              {userId && <span className="text-sm font-normal ml-2" style={{ color: 'var(--text-muted)' }}>· {userId}</span>}
            </h1>
          </div>

          <div className="flex items-center gap-2">
            {/* Pipeline overlay toggle — only shown when done */}
            {isDone && steps.length > 0 && !isRunning && (
              <button
                onClick={() => setOverlayOpen(true)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold"
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                }}
              >
                🎬 Pipeline
              </button>
            )}

            <button
              onClick={() => setSidebarOpen((v) => !v)}
              className="relative p-2.5 rounded-xl"
              style={{
                background: sidebarOpen ? 'var(--bg-overlay)' : 'var(--bg-card)',
                border: `1px solid ${sidebarOpen ? 'var(--accent-gold)' : 'var(--border)'}`,
                color: sidebarOpen ? 'var(--accent-gold)' : 'var(--text-muted)',
                cursor: 'pointer',
              }}
            >
              <SlidersHorizontal size={16} />
              {activeFilters > 0 && (
                <span className="absolute -top-1.5 -right-1.5 w-4 h-4 flex items-center justify-center rounded-full text-[9px] font-black"
                  style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}>
                  {activeFilters}
                </span>
              )}
            </button>
            <button
              onClick={startJob}
              disabled={isRunning || !userId}
              className={cn('flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold disabled:opacity-40')}
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: isRunning ? 'not-allowed' : 'pointer' }}
            >
              <RefreshCw size={13} className={isRunning ? 'animate-spin' : ''} />
              {isRunning ? 'Running…' : 'Refresh'}
            </button>
          </div>
        </div>

        <div className="px-4 md:px-8 py-6 pb-16">
          {/* Error */}
          {jobStatus === 'failed' && (
            <div className="rounded-xl p-4 mb-6 text-sm max-w-lg mx-auto"
              style={{ background: 'rgba(229,9,20,0.08)', border: '1px solid rgba(229,9,20,0.25)', color: '#ff6b6b' }}>
              Pipeline failed. Check the API server is running on port 8000.
            </div>
          )}

          {/* Film stack — shown when done */}
          {recommendations.length > 0 && !isRunning && (
            <FilmStack recs={recommendations} />
          )}

          {!isRunning && recommendations.length === 0 && jobStatus !== 'failed' && (
            <div className="flex flex-col items-center justify-center py-32 text-center">
              <div className="text-6xl mb-5">{jobStatus === 'complete' ? '😕' : '🎬'}</div>
              <p className="text-lg font-bold text-white mb-1">
                {!userId
                  ? 'Not signed in'
                  : jobStatus === 'complete'
                  ? 'No recommendations yet'
                  : 'Starting the AI recommendation engine…'}
              </p>
              <p className="text-sm max-w-sm mx-auto" style={{ color: 'var(--text-muted)' }}>
                {!userId
                  ? 'Sign in on the Home page first.'
                  : jobStatus === 'complete'
                  ? 'You may need more ratings. Browse some films and rate them, then come back.'
                  : 'Hang tight — this takes a few seconds.'}
              </p>
              {jobStatus === 'complete' && userId && (
                <div className="flex items-center gap-3 mt-5">
                  <button
                    onClick={startJob}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold"
                    style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
                  >
                    <RefreshCw size={13} /> Try Again
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Filters sidebar */}
      {sidebarOpen && (
        <aside className="fixed lg:relative inset-x-0 bottom-0 lg:inset-auto lg:w-72 lg:flex-shrink-0 border-t lg:border-t-0 lg:border-l p-5 space-y-4 overflow-y-auto z-40 rounded-t-2xl lg:rounded-none"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', maxHeight: '80vh' }}>
          <div className="flex items-center justify-between">
            <h2 className="font-black text-xs uppercase tracking-widest" style={{ color: 'var(--accent-gold)' }}>Customize</h2>
            {activeFilters > 0 && (
              <button
                onClick={() => { setMood([]); setCompanion(''); setLanguage(''); setNaturalCtx(''); setYearMin(''); setYearMax('') }}
                className="text-[10px] font-semibold"
                style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                Clear all
              </button>
            )}
          </div>

          {/* Mood */}
          <div className="space-y-1.5">
            <label className="block text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
              Mood {mood.length > 0 && <span style={{ color: 'var(--accent-gold)' }}>({mood.length})</span>}
            </label>
            <div className="flex flex-wrap gap-1.5">
              {MOODS.map((m) => (
                <button 
                  key={m} 
                  onClick={() => setMood(prev => 
                    prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m]
                  )}
                  className="px-2.5 py-1 rounded-full text-[11px] font-semibold capitalize"
                  style={{ 
                    background: mood.includes(m) ? 'var(--accent-gold)' : 'var(--bg-overlay)', 
                    color: mood.includes(m) ? '#0a0a0f' : 'var(--text-muted)', 
                    border: '1px solid var(--border)', 
                    cursor: 'pointer' 
                  }}>
                  {m}
                </button>
              ))}
            </div>
          </div>

          {/* Companion */}
          <div className="space-y-1.5">
            <label className="block text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Watching with</label>
            <div className="flex flex-wrap gap-1.5">
              {COMPANIONS.map((c) => (
                <button key={c} onClick={() => setCompanion(companion === c ? '' : c)}
                  className="px-2.5 py-1 rounded-full text-[11px] font-semibold capitalize"
                  style={{ background: companion === c ? 'var(--accent-gold)' : 'var(--bg-overlay)', color: companion === c ? '#0a0a0f' : 'var(--text-muted)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                  {c}
                </button>
              ))}
            </div>
          </div>

          {/* Language */}
          <div className="space-y-1.5">
            <label className="block text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Language</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full rounded-lg px-3 py-2 text-xs font-semibold outline-none"
              style={{
                background: 'var(--bg-overlay)',
                color: language ? 'var(--accent-gold)' : 'var(--text-muted)',
                border: `1px solid ${language ? 'var(--accent-gold)' : 'var(--border)'}`,
                cursor: 'pointer',
              }}
            >
              <option value="">All Languages</option>
              {Object.keys(LANGUAGE_MAP).map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>

          {/* Year range */}
          <div className="space-y-1.5">
            <label className="block text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Year range</label>
            <div className="flex gap-2">
              <input type="number" placeholder="From" value={yearMin} onChange={(e) => setYearMin(e.target.value)}
                min={1900} max={2026} className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} />
              <input type="number" placeholder="To" value={yearMax} onChange={(e) => setYearMax(e.target.value)}
                min={1900} max={2026} className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} />
            </div>
          </div>

          {/* Freeform */}
          <div className="space-y-1.5">
            <label className="block text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Freeform context</label>
            <textarea rows={3} placeholder="e.g. 'something mind-bending like Inception'"
              value={naturalCtx} onChange={(e) => setNaturalCtx(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-xs outline-none resize-none"
              style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} />
          </div>

          {/* k slider */}
          <div className="space-y-1.5">
            <label className="block text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
              Results: <span style={{ color: 'var(--accent-gold)', fontWeight: 700 }}>{k}</span>
            </label>
            <input type="range" min={5} max={20} value={k} onChange={(e) => setK(+e.target.value)}
              className="w-full accent-yellow-400" />
            <div className="flex justify-between text-[10px]" style={{ color: 'var(--text-muted)' }}>
              <span>5</span><span>20</span>
            </div>
          </div>

          <button
            onClick={() => { setSidebarOpen(false); startJob() }}
            disabled={isRunning || !userId}
            className="w-full py-3 rounded-xl text-sm font-black disabled:opacity-40 transition-all hover:brightness-110"
            style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
          >
            Apply & Refresh
          </button>
        </aside>
      )}

      {/* ── Premium Pipeline Overlay ──────────────────────────────────────── */}
      {overlayOpen && (
        <div
          className="fixed inset-0 z-50 flex flex-col items-center justify-center"
          style={{
            backdropFilter: 'blur(22px)',
            WebkitBackdropFilter: 'blur(22px)',
            background: 'rgba(5,4,18,0.82)',
          }}
        >
          {/* Decorative ambient rings */}
          <div className="absolute inset-0 pointer-events-none overflow-hidden">
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full"
              style={{ background: 'radial-gradient(circle, rgba(245,197,24,0.04) 0%, transparent 70%)' }} />
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] rounded-full"
              style={{ background: 'radial-gradient(circle, rgba(245,197,24,0.06) 0%, transparent 60%)' }} />
          </div>

          {/* Header */}
          <div className="relative z-10 flex flex-col items-center mb-6">
            <p className="text-[10px] font-bold tracking-[0.35em] uppercase mb-1"
              style={{ color: 'rgba(245,197,24,0.55)' }}>
              {isRunning ? 'AI Pipeline · Live' : 'AI Pipeline · Complete'}
            </p>
            {isRunning && (
              <div className="flex items-center gap-2 mt-1">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                    style={{ background: 'var(--accent-gold)' }} />
                  <span className="relative inline-flex rounded-full h-2 w-2"
                    style={{ background: 'var(--accent-gold)' }} />
                </span>
                <span className="text-xs font-medium" style={{ color: 'rgba(255,255,255,0.5)' }}>
                  {currentRunningStep ? `Running ${currentRunningStep}…` : 'Initialising…'}
                </span>
              </div>
            )}
          </div>

          {/* Trace panel */}
          <div
            className="relative z-10 w-full max-w-2xl mx-auto px-4 overflow-y-auto"
            style={{ maxHeight: 'calc(100vh - 160px)' }}
          >
            <TraceDisplay
              steps={steps}
              runningStep={isRunning ? currentRunningStep : null}
              isComplete={isDone}
            />
          </div>

          {/* Close button — only when done */}
          {!isRunning && (
            <button
              onClick={() => setOverlayOpen(false)}
              className="relative z-10 mt-6 flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-bold transition-all hover:scale-105"
              style={{
                background: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.15)',
                color: 'rgba(255,255,255,0.7)',
                cursor: 'pointer',
              }}
            >
              <X size={14} /> Hide Pipeline
            </button>
          )}
        </div>
      )}
    </div>
  )
}

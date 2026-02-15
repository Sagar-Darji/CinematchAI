import { useState, useEffect } from 'react'
import { SlidersHorizontal, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import { submitRecommendationJob, pollJobStatus } from '@/lib/api'
import { useUserStore } from '@/store/useUserStore'
import { useRecommendationStore } from '@/store/useRecommendationStore'
import { MovieCard } from '@/components/ui/MovieCard'
import { TraceDisplay } from '@/components/recommendations/TraceDisplay'
import { PageLoader } from '@/components/ui/PageLoader'
import { cn } from '@/lib/utils'

const ALL_AGENTS = [
  'Profile Analyzer', 'Context-Aware', 'Retrieval',
  'Content Intelligence', 'Serendipity', 'Explanation', 'Aggregation',
]

const LANGUAGE_MAP: Record<string, string> = {
  English: 'en', Hindi: 'hi', Tamil: 'ta', Telugu: 'te', Malayalam: 'ml',
  Kannada: 'kn', Bengali: 'bn', Gujarati: 'gu', Marathi: 'mr', Punjabi: 'pa',
  Korean: 'ko', Japanese: 'ja', French: 'fr', Spanish: 'es', German: 'de',
  Italian: 'it', Chinese: 'zh', Arabic: 'ar', Portuguese: 'pt', Russian: 'ru',
}

export default function Recommendations() {
  const userId = useUserStore((s) => s.userId)
  const {
    recommendations, jobStatus, steps, isPolling, reset,
    setRecommendations, setJobId, setJobStatus, setSteps, setIsPolling,
    setContextFactors,
  } = useRecommendationStore()

  const [mood, setMood] = useState('')
  const [companion, setCompanion] = useState('')
  const [language, setLanguage] = useState('')
  const [naturalCtx, setNaturalCtx] = useState('')
  const [k, setK] = useState(10)
  const [yearMin, setYearMin] = useState('')
  const [yearMax, setYearMax] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [traceCollapsed, setTraceCollapsed] = useState(false)

  const isRunning = isPolling || jobStatus === 'running' || jobStatus === 'pending'
  const isDone = jobStatus === 'complete'

  const buildContext = () => {
    const ctx: Record<string, unknown> = {}
    if (mood) ctx.mood = mood
    if (companion) ctx.companion = companion
    if (language) ctx.language = LANGUAGE_MAP[language] ?? language.toLowerCase()
    if (naturalCtx) ctx.natural_language_context = naturalCtx
    if (yearMin) ctx.year_min = parseInt(yearMin)
    if (yearMax) ctx.year_max = parseInt(yearMax)
    return ctx
  }

  const startJob = async () => {
    if (!userId) return
    reset()
    setTraceCollapsed(false)
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
          // Auto-collapse trace so cards get focus
          setTimeout(() => setTraceCollapsed(true), 1800)
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

  // Pipeline progress for the top bar: 0-85 while running, 100 when done
  const pipelinePct = isDone
    ? 100
    : isRunning
    ? Math.max(5, Math.round((steps.length / 7) * 85))
    : 0

  return (
    <div className="flex min-h-screen relative" style={{ background: 'var(--bg-primary)' }}>
      <PageLoader visible={isRunning} value={pipelinePct} />

      {/* Main content */}
      <div className="flex-1 p-5 md:p-8 max-w-3xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <p className="text-xs font-bold tracking-[0.25em] uppercase mb-1" style={{ color: 'var(--accent-gold)' }}>
              AI-Curated
            </p>
            <h1 className="text-3xl font-black tracking-tight text-white">For You</h1>
            {userId && (
              <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
                Personalized for {userId}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              className="p-2 rounded-lg"
              style={{
                background: sidebarOpen ? 'var(--bg-overlay)' : 'var(--bg-card)',
                border: '1px solid var(--border)',
                color: 'var(--text-muted)',
                cursor: 'pointer',
              }}
              title="Filters"
            >
              <SlidersHorizontal size={17} />
            </button>
            <button
              onClick={startJob}
              disabled={isRunning || !userId}
              className={cn('flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold disabled:opacity-40')}
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: isRunning ? 'not-allowed' : 'pointer' }}
            >
              <RefreshCw size={14} className={isRunning ? 'animate-spin' : ''} />
              {isRunning ? 'Running…' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Trace panel — shows while running, collapsible when done */}
        {(isRunning || (isDone && steps.length > 0)) && (
          <div className="mb-6">
            {isDone && !isRunning && (
              <button
                onClick={() => setTraceCollapsed((v) => !v)}
                className="flex items-center gap-2 text-xs font-semibold mb-2"
                style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
              >
                {traceCollapsed ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
                {traceCollapsed ? 'Show pipeline trace' : 'Hide pipeline trace'}
              </button>
            )}
            {!traceCollapsed && (
              <TraceDisplay
                steps={steps}
                runningStep={isRunning ? currentRunningStep : null}
                isComplete={isDone}
              />
            )}
          </div>
        )}

        {/* Error */}
        {jobStatus === 'failed' && (
          <div
            className="rounded-xl p-4 mb-6 text-sm"
            style={{ background: 'rgba(229,9,20,0.08)', border: '1px solid rgba(229,9,20,0.25)', color: '#ff6b6b' }}
          >
            Pipeline failed. Check that the API server is running on port 8000.
          </div>
        )}

        {/* Recommendation cards — staggered fade in */}
        {recommendations.length > 0 && (
          <div className="space-y-2.5">
            <p className="text-xs font-bold tracking-[0.2em] uppercase mb-4" style={{ color: 'var(--text-muted)' }}>
              {recommendations.length} picks · AI-curated
            </p>
            {recommendations.map((rec, i) => (
              <MovieCard key={rec.movie.tmdb_id ?? i} rec={rec} rank={i + 1} compact />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!isRunning && recommendations.length === 0 && jobStatus !== 'failed' && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="text-5xl mb-4">🎬</div>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {userId ? 'Starting recommendation engine…' : 'Enter a username on Home first.'}
            </p>
          </div>
        )}
      </div>

      {/* Filters sidebar */}
      {sidebarOpen && (
        <aside
          className="w-72 border-l p-6 space-y-5 flex-shrink-0"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
        >
          <h2 className="font-bold text-xs uppercase tracking-widest" style={{ color: 'var(--accent-gold)' }}>
            Customize
          </h2>

          <FilterSelect label="Mood" value={mood} onChange={setMood}
            options={['happy','sad','stressed','bored','thoughtful','energetic','nostalgic','adventurous']} />

          <FilterSelect label="Watching with" value={companion} onChange={setCompanion}
            options={['alone','partner','friends','family']} />

          <FilterSelect label="Language" value={language} onChange={setLanguage}
            options={Object.keys(LANGUAGE_MAP)} />

          <div className="space-y-1">
            <label className="block text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Year range</label>
            <div className="flex gap-2">
              <input type="number" placeholder="From" value={yearMin}
                onChange={(e) => setYearMin(e.target.value)} min={1900} max={2026}
                className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} />
              <input type="number" placeholder="To" value={yearMax}
                onChange={(e) => setYearMax(e.target.value)} min={1900} max={2026}
                className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} />
            </div>
          </div>

          <div className="space-y-1">
            <label className="block text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
              Context (freeform)
            </label>
            <textarea
              rows={3}
              placeholder="e.g. 'Something mind-bending like Inception'"
              value={naturalCtx}
              onChange={(e) => setNaturalCtx(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-xs outline-none resize-none"
              style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            />
          </div>

          <div className="space-y-1">
            <label className="block text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
              Results: {k}
            </label>
            <input type="range" min={5} max={20} value={k} onChange={(e) => setK(+e.target.value)}
              className="w-full accent-yellow-400" />
          </div>

          <button
            onClick={() => { setSidebarOpen(false); startJob() }}
            disabled={isRunning || !userId}
            className="w-full py-2.5 rounded-xl text-sm font-bold disabled:opacity-40"
            style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
          >
            Apply & Refresh
          </button>
        </aside>
      )}
    </div>
  )
}

function FilterSelect({
  label, value, onChange, options,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: string[]
}) {
  return (
    <div className="space-y-1">
      <label className="block text-xs font-medium" style={{ color: 'var(--text-muted)' }}>{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 rounded-lg text-xs outline-none"
        style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
      >
        <option value="">Any</option>
        {options.map((o) => (
          <option key={o} value={o}>{o.charAt(0).toUpperCase() + o.slice(1)}</option>
        ))}
      </select>
    </div>
  )
}

/**
 * MovieWeb — CineWeb Galaxy Explorer
 *
 * Layout:  Full-screen canvas (no header bar eating space)
 * Search:  Floating glassmorphism card, top-centre
 * Detail:  Bottom sheet — slides up, has Watch Now + Explore
 * Color:   Genre-derived accent — every movie looks different
 */

import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import {
  Search, X, Star, ChevronRight, Play,
  Layers, Film, ZoomIn, Network,
} from 'lucide-react'
import MovieWebGraph, { type WebData, type WebNode, genreAccent } from '@/components/web/MovieWebGraph'
import { FullScreenPlayer } from '@/components/ui/MovieCard'

// ── API ───────────────────────────────────────────────────────────────────────

const API_URL = import.meta.env.VITE_API_URL || ''

async function fetchMovieWeb(name: string, maxNodes = 35): Promise<WebData> {
  const res = await fetch(`${API_URL}/api/v1/movie-web/${encodeURIComponent(name)}?max_nodes=${maxNodes}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Constants ─────────────────────────────────────────────────────────────────

const SUGGESTIONS = ['Inception', 'Parasite', 'The Dark Knight', 'Pulp Fiction', 'Interstellar', 'Get Out', 'Her']

const LOADING_LABELS = [
  'Scanning TMDB signals…',
  'Building candidate pool…',
  'Generating cinematic fingerprint…',
  'Running vibe scoring…',
  'Mapping the galaxy…',
]

const EDGE_LABELS: Record<string, string> = {
  director: 'Director', actor: 'Actor', keyword: 'Theme', similar: 'Similar', genre: 'Genre',
}
const EDGE_COLORS: Record<string, string> = {
  director: '#f5c518', actor: '#60A5FA', keyword: '#A78BFA', similar: '#94A3B8', genre: '#34D399',
}

// ── Orbital comet loader ──────────────────────────────────────────────────────

function RippleLoader({ label, accent }: { label: string; accent: string }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const raf = useRef(0)

  useEffect(() => {
    const c = ref.current; if (!c) return
    const ctx = c.getContext('2d')!
    const DPR = Math.min(window.devicePixelRatio || 1, 2)
    const S = 160
    c.width = S * DPR; c.height = S * DPR; ctx.scale(DPR, DPR)
    const cx = S / 2, cy = S / 2

    // Three orbital tracks — different radii, speeds, arc lengths
    const orbs = [
      { r: 60, speed:  0.007, arc: 2.2, phase: 0.0,  w: 1.4 },
      { r: 43, speed: -0.012, arc: 1.5, phase: 2.1,  w: 1.4 },
      { r: 26, speed:  0.022, arc: 0.9, phase: 4.6,  w: 1.4 },
    ]
    const STEPS = 52

    const loop = () => {
      ctx.clearRect(0, 0, S, S)
      const t = Date.now() / 1000

      // Faint orbit tracks
      orbs.forEach((o) => {
        ctx.beginPath(); ctx.arc(cx, cy, o.r, 0, Math.PI * 2)
        ctx.strokeStyle = `${accent}12`; ctx.lineWidth = 0.8; ctx.stroke()
      })

      // Comet arcs — quadratic fade from dim tail → bright head
      orbs.forEach((o) => {
        o.phase += o.speed
        for (let i = 0; i < STEPS; i++) {
          const pct = i / STEPS
          const a0  = o.phase + pct * o.arc
          const a1  = o.phase + ((i + 1) / STEPS) * o.arc
          ctx.beginPath(); ctx.arc(cx, cy, o.r, a0, a1)
          ctx.globalAlpha = pct * pct * 0.88
          ctx.strokeStyle = accent; ctx.lineWidth = o.w; ctx.stroke()
        }
        // Leading bright dot
        ctx.globalAlpha = 1
        const ha = o.phase + o.arc
        ctx.beginPath(); ctx.arc(cx + o.r * Math.cos(ha), cy + o.r * Math.sin(ha), o.w + 1, 0, Math.PI * 2)
        ctx.fillStyle = accent; ctx.fill()
      })
      ctx.globalAlpha = 1

      // Center glow + dot
      const pulse = 1 + 0.13 * Math.sin(t * 2.7)
      const glow  = ctx.createRadialGradient(cx, cy, 0, cx, cy, 16 * pulse)
      glow.addColorStop(0, `${accent}40`); glow.addColorStop(1, 'transparent')
      ctx.beginPath(); ctx.arc(cx, cy, 16 * pulse, 0, Math.PI * 2)
      ctx.fillStyle = glow; ctx.fill()
      ctx.beginPath(); ctx.arc(cx, cy, 3.5, 0, Math.PI * 2)
      ctx.fillStyle = accent; ctx.fill()

      raf.current = requestAnimationFrame(loop)
    }
    raf.current = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf.current)
  }, [accent])

  return (
    <div className="flex flex-col items-center gap-7 select-none">
      <canvas ref={ref} style={{ width: 160, height: 160 }} />
      <div className="flex flex-col items-center gap-1.5">
        <p className="text-[10px] font-semibold tracking-[0.2em] uppercase"
           style={{ color: `${accent}60` }}>
          Mapping your galaxy
        </p>
        <p className="text-sm" style={{ color: 'rgba(255,255,255,0.38)' }}>{label}</p>
      </div>
    </div>
  )
}

// ── Idle constellation ────────────────────────────────────────────────────────

function IdleRipple({ accent }: { accent: string }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const raf = useRef(0)

  useEffect(() => {
    const c = ref.current; if (!c) return
    const ctx = c.getContext('2d')!
    const DPR = Math.min(window.devicePixelRatio || 1, 2)
    const S = 160
    c.width = S * DPR; c.height = S * DPR; ctx.scale(DPR, DPR)
    const cx = S / 2, cy = S / 2

    // Fixed star positions (polar coords)
    const stars = [
      { r: 62, a: 0.4  }, { r: 55, a: 1.8  }, { r: 68, a: 3.2  },
      { r: 50, a: 4.5  }, { r: 70, a: 5.6  }, { r: 40, a: 2.5  },
      { r: 30, a: 0.9  }, { r: 72, a: 1.1  }, { r: 58, a: 4.0  },
    ]
    // Constellation edges (index pairs)
    const edges = [[0,1],[1,2],[2,3],[3,4],[4,0],[5,6],[6,7],[7,8]]

    const loop = () => {
      ctx.clearRect(0, 0, S, S)
      const t = Date.now() / 1000

      // Slow collective rotation
      const rot = t * 0.04

      const pts = stars.map((s) => ({
        x: cx + s.r * Math.cos(s.a + rot),
        y: cy + s.r * Math.sin(s.a + rot),
      }))

      // Constellation lines
      edges.forEach(([a, b]) => {
        ctx.beginPath()
        ctx.moveTo(pts[a].x, pts[a].y)
        ctx.lineTo(pts[b].x, pts[b].y)
        ctx.strokeStyle = `${accent}18`; ctx.lineWidth = 0.8; ctx.stroke()
      })

      // Stars — each twinkles independently
      stars.forEach((s, i) => {
        const twinkle = 0.55 + 0.45 * Math.sin(t * (1.1 + i * 0.37) + i)
        const radius  = (i % 3 === 0 ? 2.4 : 1.6) * twinkle
        // Soft halo
        const g = ctx.createRadialGradient(pts[i].x, pts[i].y, 0, pts[i].x, pts[i].y, radius * 3.5)
        g.addColorStop(0, `${accent}50`); g.addColorStop(1, 'transparent')
        ctx.beginPath(); ctx.arc(pts[i].x, pts[i].y, radius * 3.5, 0, Math.PI * 2)
        ctx.fillStyle = g; ctx.fill()
        // Core dot
        ctx.beginPath(); ctx.arc(pts[i].x, pts[i].y, radius, 0, Math.PI * 2)
        ctx.fillStyle = accent; ctx.globalAlpha = twinkle; ctx.fill()
        ctx.globalAlpha = 1
      })

      // Center anchor
      const pulse = 1 + 0.12 * Math.sin(t * 1.8)
      const glow  = ctx.createRadialGradient(cx, cy, 0, cx, cy, 14 * pulse)
      glow.addColorStop(0, `${accent}35`); glow.addColorStop(1, 'transparent')
      ctx.beginPath(); ctx.arc(cx, cy, 14 * pulse, 0, Math.PI * 2)
      ctx.fillStyle = glow; ctx.fill()
      ctx.beginPath(); ctx.arc(cx, cy, 3, 0, Math.PI * 2)
      ctx.fillStyle = accent; ctx.fill()

      raf.current = requestAnimationFrame(loop)
    }
    raf.current = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf.current)
  }, [accent])

  return <canvas ref={ref} style={{ width: 160, height: 160, opacity: 0.85 }} />
}

// ── Hover tooltip ─────────────────────────────────────────────────────────────

function Tooltip({ node, accent }: { node: WebNode; accent: string }) {
  const color = node.edge_type ? (EDGE_COLORS[node.edge_type] ?? accent) : accent
  return (
    <div
      className="absolute top-20 right-4 w-52 rounded-2xl p-3 space-y-1.5 pointer-events-none z-20"
      style={{
        background: 'rgba(5,4,18,0.92)',
        border: `1px solid ${color}44`,
        backdropFilter: 'blur(16px)',
        boxShadow: `0 0 24px ${color}18`,
      }}
    >
      <p className="font-bold text-white text-sm leading-snug">{node.title}</p>
      {node.year && (
        <p className="text-[11px]" style={{ color: 'rgba(255,255,255,0.4)' }}>
          {node.year}{node.genres?.length ? ' · ' + node.genres.slice(0, 2).join(', ') : ''}
        </p>
      )}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold"
          style={{ background: `${color}20`, color }}>
          {Math.round(node.score * 100)}% match
        </span>
        {node.vote_average && (
          <span className="flex items-center gap-0.5 text-[11px]" style={{ color: '#f5c518' }}>
            <Star size={9} fill="currentColor" />{node.vote_average.toFixed(1)}
          </span>
        )}
      </div>
      {node.reasons && node.reasons.length > 0 && (
        <ul className="space-y-0.5 pt-0.5">
          {node.reasons.slice(0, 3).map((r) => (
            <li key={r} className="flex items-start gap-1 text-[11px]"
              style={{ color: 'rgba(255,255,255,0.55)' }}>
              <ChevronRight size={8} className="mt-0.5 flex-shrink-0" style={{ color }} />
              {r}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Bottom Sheet ──────────────────────────────────────────────────────────────

function BottomSheet({ node, accent, onClose, onExplore }: {
  node: WebNode | null
  accent: string
  onClose: () => void
  onExplore: (title: string) => void
}) {
  const [open,       setOpen]       = useState(false)
  const [showPlayer, setShowPlayer] = useState(false)

  useEffect(() => {
    if (node) { const t = setTimeout(() => setOpen(true), 16); return () => clearTimeout(t) }
    else { setOpen(false); setShowPlayer(false) }
  }, [node])

  if (!node && !open) return null

  const isSeed = node?.score === 1.0
  const color  = isSeed ? accent : (node?.edge_type ? (EDGE_COLORS[node.edge_type] ?? accent) : accent)

  return (
    <div
      className="absolute inset-x-0 bottom-0 z-40 flex flex-col"
      style={{
        transform: open && node ? 'translateY(0)' : 'translateY(105%)',
        transition: 'transform 0.40s cubic-bezier(0.34,1.18,0.64,1)',
        background: 'rgba(4,3,14,0.97)',
        borderTop: `1px solid ${color}44`,
        backdropFilter: 'blur(28px)',
        boxShadow: `0 -6px 48px rgba(0,0,0,0.7), 0 -1px 0 ${color}22`,
        maxHeight: '80vh',
        overflowY: 'auto',
        borderRadius: '20px 20px 0 0',
      }}
    >
      {/* Drag handle */}
      <div className="flex justify-center pt-3 pb-1 flex-shrink-0">
        <div className="w-10 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.15)' }} />
      </div>

      <div className="flex gap-4 px-5 pb-2 pt-2">
        {/* Poster */}
        {node?.poster_url && (
          <div className="flex-shrink-0">
            <img
              src={node.poster_url}
              alt={node.title}
              className="rounded-xl object-cover"
              style={{
                width: 82, aspectRatio: '2/3',
                border: `1px solid ${color}33`,
                boxShadow: `0 4px 24px ${color}30`,
              }}
            />
          </div>
        )}

        {/* Info */}
        <div className="flex-1 min-w-0 flex flex-col gap-2">
          {/* Title + close */}
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-bold text-white text-base leading-snug">{node?.title}</p>
              <p className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.38)' }}>
                {[node?.year, node?.genres?.slice(0, 2).join(', ')].filter(Boolean).join(' · ')}
              </p>
            </div>
            <button
              onClick={() => { setOpen(false); setTimeout(onClose, 380) }}
              className="p-1.5 rounded-lg flex-shrink-0 hover:bg-white/10 transition-colors"
              style={{ color: 'rgba(255,255,255,0.4)' }}
            >
              <X size={15} />
            </button>
          </div>

          {/* Rating */}
          {node?.vote_average && (
            <div className="flex items-center gap-1.5">
              <Star size={12} fill="#f5c518" style={{ color: '#f5c518' }} />
              <span className="text-sm font-bold text-white">{node.vote_average.toFixed(1)}</span>
              <span className="text-xs" style={{ color: 'rgba(255,255,255,0.3)' }}>/10</span>
              {node.director && !isSeed && (
                <span className="text-xs ml-2" style={{ color: 'rgba(255,255,255,0.38)' }}>
                  · {node.director}
                </span>
              )}
            </div>
          )}

          {/* Seed: director */}
          {isSeed && node?.director && (
            <p className="text-xs" style={{ color: 'rgba(255,255,255,0.55)' }}>
              Directed by <span className="text-white font-medium">{node.director}</span>
            </p>
          )}

          {/* Similarity bar */}
          {!isSeed && node && (
            <div>
              <div className="flex items-center justify-between text-[11px] mb-1">
                <span style={{ color: 'rgba(255,255,255,0.38)' }}>Similarity</span>
                <span style={{ color }} className="font-bold">{Math.round(node.score * 100)}%</span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
                <div className="h-full rounded-full" style={{
                  width: `${node.score * 100}%`,
                  background: `linear-gradient(90deg, ${color}80, ${color})`,
                }} />
              </div>
            </div>
          )}

          {/* Why similar */}
          {!isSeed && node?.reasons && node.reasons.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {node.reasons.slice(0, 4).map((r) => (
                <span key={r} className="px-2 py-0.5 rounded-full text-[10px] font-medium"
                  style={{ background: `${color}18`, color }}>
                  {r}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Overview */}
      {node?.overview && (
        <p className="px-5 pb-2 text-xs leading-relaxed"
          style={{ color: 'rgba(255,255,255,0.45)' }}>
          {node.overview.length > 200 ? node.overview.slice(0, 198) + '…' : node.overview}
        </p>
      )}

      {/* Seed keywords */}
      {isSeed && node?.keywords && node.keywords.length > 0 && (
        <div className="px-5 pb-3 flex flex-wrap gap-1.5">
          {node.keywords.slice(0, 10).map((k) => (
            <span key={k} className="px-2 py-0.5 rounded-full text-[10px]"
              style={{ background: 'rgba(167,139,250,0.12)', color: '#A78BFA' }}>
              {k}
            </span>
          ))}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-3 px-5 pb-5 pt-1">
        {/* Watch Now — same FullScreenPlayer used on Browse/Recommendations */}
        <button
          onClick={() => setShowPlayer(true)}
          className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold transition-all hover:opacity-90 active:scale-[0.97]"
          style={{ background: color, color: '#04030e', border: 'none', cursor: 'pointer' }}
        >
          <Play size={14} fill="currentColor" />
          Watch Now
        </button>

        {/* Explore from here (non-seed only) */}
        {!isSeed && node && (
          <button
            onClick={() => { setOpen(false); setTimeout(() => onExplore(node.title), 380) }}
            className="flex-1 py-2.5 rounded-xl text-sm font-bold transition-all hover:opacity-90 active:scale-[0.97]"
            style={{ background: 'rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.85)', border: '1px solid rgba(255,255,255,0.12)', cursor: 'pointer' }}
          >
            Explore →
          </button>
        )}
      </div>

      {/* In-app player */}
      {showPlayer && node && (
        <FullScreenPlayer
          tmdbId={node.id}
          title={node.title}
          mediaType="movie"
          onClose={() => setShowPlayer(false)}
        />
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function MovieWeb() {
  const [query,        setQuery]        = useState('')
  const [webData,      setWebData]      = useState<WebData | null>(null)
  const [loading,      setLoading]      = useState(false)
  const [error,        setError]        = useState<string | null>(null)
  const [hoveredNode,  setHoveredNode]  = useState<WebNode | null>(null)
  const [selectedNode, setSelectedNode] = useState<WebNode | null>(null)
  const [loadingLabel, setLoadingLabel] = useState(LOADING_LABELS[0])
  const inputRef = useRef<HTMLInputElement>(null)

  const accentColor = useMemo(
    () => genreAccent(webData?.seed.genres),
    [webData?.seed.genres],
  )

  const explore = useCallback(async (title: string) => {
    if (!title.trim()) return
    setQuery(title); setWebData(null); setSelectedNode(null)
    setHoveredNode(null); setError(null); setLoading(true)

    let li = 0; setLoadingLabel(LOADING_LABELS[0])
    const iv = setInterval(() => {
      li = (li + 1) % LOADING_LABELS.length
      setLoadingLabel(LOADING_LABELS[li])
    }, 1800)

    try {
      setWebData(await fetchMovieWeb(title.trim(), 35))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      clearInterval(iv); setLoading(false)
    }
  }, [])

  // Focus input on mount
  useEffect(() => { inputRef.current?.focus() }, [])

  const activeAccent = loading ? '#f5c518' : accentColor

  return (
    <div
      className="relative"
      style={{ height: '100vh', background: '#010108', overflow: 'hidden', color: 'white' }}
    >
      {/* ── Full-screen canvas ────────────────────────────────────────────── */}
      {webData && !loading && (
        <div className="absolute inset-0 z-0">
          <MovieWebGraph
            data={webData}
            accentColor={accentColor}
            onNodeClick={setSelectedNode}
            onNodeHover={setHoveredNode}
          />
        </div>
      )}

      {/* ── Loading ───────────────────────────────────────────────────────── */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center z-10">
          <RippleLoader label={loadingLabel} accent={activeAccent} />
        </div>
      )}

      {/* ── Empty state ───────────────────────────────────────────────────── */}
      {!webData && !loading && !error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-6 z-10 pb-24">
          <IdleRipple accent="#f5c518" />
          <div className="text-center">
            <p className="text-2xl font-bold text-white mb-2">Your Movie Galaxy Awaits</p>
            <p className="text-sm max-w-xs mx-auto" style={{ color: 'rgba(255,255,255,0.38)' }}>
              Enter any movie — explore a living web of similar films connected by director, cast, theme & vibe.
            </p>
          </div>
        </div>
      )}

      {/* ── Error ─────────────────────────────────────────────────────────── */}
      {error && !loading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-5 z-10 pb-24 px-6">
          <div className="px-6 py-4 rounded-2xl text-center max-w-xs"
            style={{ background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.22)' }}>
            <p className="font-bold text-red-400 mb-1.5">Not found</p>
            <p className="text-sm" style={{ color: 'rgba(255,255,255,0.42)' }}>{error}</p>
          </div>
          <Chips onExplore={explore} />
        </div>
      )}

      {/* ── Floating search bar ───────────────────────────────────────────── */}
      <div
        className="absolute z-20 left-1/2"
        style={{
          top: 18,
          transform: 'translateX(-50%)',
          width: 'min(520px, calc(100% - 48px))',
        }}
      >
        <form
          onSubmit={(e) => { e.preventDefault(); explore(query) }}
          className="flex gap-2 rounded-2xl p-2"
          style={{
            background: 'rgba(6,5,20,0.82)',
            border: `1px solid ${webData ? activeAccent + '44' : 'rgba(255,255,255,0.1)'}`,
            backdropFilter: 'blur(24px)',
            boxShadow: webData ? `0 0 32px ${activeAccent}18` : '0 4px 32px rgba(0,0,0,0.5)',
            transition: 'border-color 0.4s, box-shadow 0.4s',
          }}
        >
          {/* Icon */}
          <div className="flex items-center pl-2 flex-shrink-0">
            <Network size={14} style={{ color: webData ? activeAccent : 'rgba(255,255,255,0.3)' }} />
          </div>

          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search any movie in the world…"
            className="flex-1 bg-transparent text-sm text-white outline-none placeholder:text-white/30 min-w-0"
          />

          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="flex-shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all active:scale-95 disabled:opacity-40"
            style={{ background: activeAccent, color: '#04030e' }}
          >
            <Search size={11} />
            {loading ? '…' : 'Explore'}
          </button>
        </form>

        {/* Chips below search — only when no data */}
        {!webData && !loading && (
          <div className="mt-3 flex flex-wrap justify-center gap-1.5">
            <Chips onExplore={explore} />
          </div>
        )}
      </div>

      {/* ── Seed title badge (when loaded) ───────────────────────────────── */}
      {webData && !loading && (
        <div
          className="absolute left-1/2 z-10 flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium hidden sm:flex"
          style={{
            top: 78,
            transform: 'translateX(-50%)',
            background: `${activeAccent}18`,
            border: `1px solid ${activeAccent}33`,
            color: activeAccent,
            backdropFilter: 'blur(8px)',
          }}
        >
          <Film size={10} />
          {webData.seed.title}
          {webData.seed.year && <span style={{ color: `${activeAccent}88` }}>· {webData.seed.year}</span>}
        </div>
      )}

      {/* ── Legend — hidden on mobile ─────────────────────────────────────── */}
      {webData && !loading && (
        <div
          className="absolute bottom-5 left-4 z-10 rounded-2xl px-3 py-2.5 space-y-1.5 hidden sm:block"
          style={{
            background: 'rgba(4,3,14,0.78)',
            border: '1px solid rgba(255,255,255,0.07)',
            backdropFilter: 'blur(12px)',
          }}
        >
          {Object.entries(EDGE_LABELS).map(([type, label]) => (
            <div key={type} className="flex items-center gap-2">
              <div className="w-4 h-px rounded-full flex-shrink-0" style={{ background: EDGE_COLORS[type], height: 1.5 }} />
              <span className="text-[10px]" style={{ color: 'rgba(255,255,255,0.42)' }}>{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* ── Stats + hints — hidden on mobile ─────────────────────────────── */}
      {webData && !loading && (
        <div
          className="absolute bottom-5 right-4 z-10 text-right space-y-1 hidden sm:block"
          style={{ color: 'rgba(255,255,255,0.25)' }}
        >
          <div className="flex items-center justify-end gap-1.5 text-[10px]">
            <Layers size={9} />
            <span>{webData.stats.candidates_evaluated} candidates · {webData.stats.nodes} nodes</span>
          </div>
          <div className="text-[9px] space-y-0.5">
            <div className="flex items-center justify-end gap-1">
              <ZoomIn size={8} /> Scroll to zoom
            </div>
            <p>Drag to pan · Dbl-click to reset</p>
          </div>
        </div>
      )}

      {/* ── Suggestion chips — hide when node selected (bottom sheet visible) */}
      {webData && !loading && !selectedNode && (
        <div className="absolute bottom-5 left-1/2 -translate-x-1/2 z-10 hidden sm:flex">
          <Chips onExplore={explore} compact accent={activeAccent} />
        </div>
      )}

      {/* ── Hover tooltip — desktop only (no hover on touch) ───────────────── */}
      {hoveredNode && !selectedNode && (
        <div className="hidden md:block">
          <Tooltip node={hoveredNode} accent={activeAccent} />
        </div>
      )}

      {/* ── Bottom sheet ─────────────────────────────────────────────────── */}
      <BottomSheet
        node={selectedNode}
        accent={activeAccent}
        onClose={() => setSelectedNode(null)}
        onExplore={(t) => { setSelectedNode(null); explore(t) }}
      />
    </div>
  )
}

// ── Suggestion chips ──────────────────────────────────────────────────────────

function Chips({ onExplore, compact = false, accent = '#f5c518' }: {
  onExplore: (t: string) => void
  compact?: boolean
  accent?: string
}) {
  const items = compact ? SUGGESTIONS.slice(0, 5) : SUGGESTIONS
  return (
    <div className="flex flex-wrap justify-center gap-1.5">
      {items.map((s) => (
        <button
          key={s}
          onClick={() => onExplore(s)}
          className="px-3 py-1 rounded-full text-xs font-medium transition-all hover:opacity-85 active:scale-95"
          style={{
            background: `${accent}0f`,
            border: `1px solid ${accent}28`,
            color: accent,
            backdropFilter: 'blur(8px)',
          }}
        >
          {s}
        </button>
      ))}
    </div>
  )
}

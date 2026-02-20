/**
 * MovieWebGraph — Galaxy-style force canvas.
 *
 * Design philosophy:
 *   • Every movie produces a UNIQUE look (genre-based nebula + accent colour)
 *   • Nodes float continuously in zero-gravity (never fully settle)
 *   • Closer = higher similarity = bigger node = nearer to seed
 *   • Gradient edges go from seed accent → relationship-type colour
 *   • Pan (drag empty space) · Zoom (scroll) · Drag nodes · Dbl-click reset
 *
 * Coordinate contract:
 *   ALL physics & draw coordinates are in LOGICAL (CSS) pixels.
 *   canvas.width = offsetWidth × dpr — only for backing-store resolution.
 *   ctx.setTransform(dpr,0,0,dpr,0,0) keeps draw units = CSS pixels.
 */

import { useRef, useEffect, useCallback } from 'react'

// ── Public types ───────────────────────────────────────────────────────────────

export interface WebNode {
  id: number
  title: string
  year?: string
  genres?: string[]
  poster_url?: string | null
  vote_average?: number
  overview?: string
  score: number
  edge_type?: string
  reasons?: string[]
  director?: string
  cast?: string[]
  keywords?: string[]
}

export interface WebEdge {
  source: number
  target: number
  weight: number
  type: string
  reasons?: string[]
}

export interface WebData {
  seed: WebNode
  nodes: WebNode[]
  edges: WebEdge[]
  stats: { candidates_evaluated: number; nodes: number; edges: number; keywords_used: number }
}

interface Props {
  data: WebData
  accentColor: string   // genre-derived, passed from parent
  onNodeClick: (node: WebNode) => void
  onNodeHover: (node: WebNode | null) => void
}

// ── Genre accent (exported so parent can use same colour) ──────────────────────

export function genreAccent(genres?: string[]): string {
  const list = (genres ?? []).map((g) => g.toLowerCase())
  if (list.some((g) => /sci.?fi|space|alien|futur/.test(g)))  return '#00D4FF'
  if (list.some((g) => /horror/.test(g)))                     return '#FF3B5C'
  if (list.some((g) => /action/.test(g)))                     return '#FF6B35'
  if (list.some((g) => /thriller|war/.test(g)))               return '#FF9840'
  if (list.some((g) => /romance/.test(g)))                    return '#FF69B4'
  if (list.some((g) => /animation|animated/.test(g)))         return '#FF6FD8'
  if (list.some((g) => /crime/.test(g)))                      return '#A855F7'
  if (list.some((g) => /mystery/.test(g)))                    return '#8B5CF6'
  if (list.some((g) => /documentary/.test(g)))                return '#34D399'
  if (list.some((g) => /comedy/.test(g)))                     return '#FBBF24'
  if (list.some((g) => /fantasy/.test(g)))                    return '#4ADE80'
  if (list.some((g) => /drama/.test(g)))                      return '#818CF8'
  if (list.some((g) => /history|biograph/.test(g)))           return '#D97706'
  if (list.some((g) => /music/.test(g)))                      return '#EC4899'
  return '#f5c518'
}

// ── Internal helpers ───────────────────────────────────────────────────────────

function h2r(hex: string, a: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${a})`
}

// ── Constants ─────────────────────────────────────────────────────────────────

const BG           = '#010108'
const SEED_RADIUS  = 56
const NODE_MIN     = 12
const NODE_MAX     = 32
const DAMPING      = 0.85
const MIN_ORBIT    = 0.30
const MAX_ORBIT    = 0.97
const FLOAT_Y_AMP  = 5      // vertical bob ±5 px
const FLOAT_X_AMP  = 3.5    // horizontal drift ±3.5 px
const FLOAT_Y_MS   = 5000   // Y cycle ~5 s
const FLOAT_X_MS   = 7000   // X cycle ~7 s (different → elliptical path)
const SETTLE_VEL   = 0.02

const EDGE_COLORS: Record<string, string> = {
  director: '#f5c518',
  actor:    '#60A5FA',
  keyword:  '#A78BFA',
  similar:  '#94A3B8',
  genre:    '#34D399',
}

const EDGE_LABELS: Record<string, string> = {
  director: 'Director', actor: 'Actor', keyword: 'Theme', similar: 'Similar', genre: 'Genre',
}

// Line dash per edge type — encodes relationship strength visually
const EDGE_DASH: Record<string, number[]> = {
  director: [],        // solid  — strongest creative DNA
  actor:    [6, 4],    // dashed — talent link
  keyword:  [3, 5],    // short  — thematic echo
  similar:  [2, 6],    // dotted — platform signal
  genre:    [1, 7],    // sparse — genre family
}

const HOVER_SCALE_TARGET = 1.65   // how large hovered node grows
const HOVER_SCALE_SPEED  = 0.09   // lerp factor (~0.5 s to reach target)

// ── Physics node ──────────────────────────────────────────────────────────────

interface PhysNode {
  id: number
  data: WebNode
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  targetR: number       // orbit radius (0 = seed, pinned at centre)
  driftPhase: number    // unique float phase offset
  hoverScale: number    // animated scale: 1.0 → HOVER_SCALE_TARGET on hover
  floatX: number        // draw-time horizontal drift
  floatY: number        // draw-time vertical bob
  img: HTMLImageElement | null
  imgLoaded: boolean
}

interface Camera { x: number; y: number; scale: number }

interface Star {
  x: number; y: number
  r: number; baseAlpha: number
  phase: number; twinkles: boolean
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function MovieWebGraph({ data, accentColor, onNodeClick, onNodeHover }: Props) {
  const canvasRef    = useRef<HTMLCanvasElement>(null)
  const nodesRef     = useRef<PhysNode[]>([])
  const rafRef       = useRef<number>(0)
  const hoveredRef   = useRef<number | null>(null)
  const dragRef      = useRef<PhysNode | null>(null)
  const isPanRef     = useRef(false)
  const panStartRef  = useRef({ sx: 0, sy: 0, cx: 0, cy: 0 })
  const hasPannedRef = useRef(false)
  const camRef       = useRef<Camera>({ x: 0, y: 0, scale: 1 })
  const starsRef     = useRef<Star[]>([])
  const imgCache     = useRef(new Map<number, HTMLImageElement>())
  const logW         = useRef(0)
  const logH         = useRef(0)

  // Reset camera when seed movie changes
  useEffect(() => {
    camRef.current = { x: 0, y: 0, scale: 1 }
  }, [data.seed.id])

  // ── Orbit radius from score ──────────────────────────────────────────────────
  const orbitR = useCallback((score: number): number => {
    const pad  = NODE_MAX + 22
    const maxR = Math.min(logW.current, logH.current) / 2 - pad
    const safe = Math.max(maxR, 90)
    // high score → small orbit (close); low score → large orbit (far)
    return safe * (MIN_ORBIT + (1 - Math.pow(score, 0.7)) * (MAX_ORBIT - MIN_ORBIT))
  }, [])

  // ── Generate star field ──────────────────────────────────────────────────────
  const buildStars = useCallback((W: number, H: number) => {
    starsRef.current = Array.from({ length: 260 }, () => ({
      x:         Math.random() * W,
      y:         Math.random() * H,
      r:         Math.random() < 0.05 ? 1.8 : Math.random() < 0.18 ? 1.0 : 0.5,
      baseAlpha: 0.10 + Math.random() * 0.65,
      phase:     Math.random() * Math.PI * 2,
      twinkles:  Math.random() < 0.38,
    }))
  }, [])

  // ── Build physics nodes ──────────────────────────────────────────────────────
  const buildNodes = useCallback((): PhysNode[] => {
    const W  = logW.current
    const H  = logH.current
    const cx = W / 2
    const cy = H / 2

    // Sort candidates by score so even-spacing distributes nicely
    const sorted = [...data.nodes].sort((a, b) => b.score - a.score)
    const all: WebNode[] = [data.seed, ...sorted]

    return all.map((n, i) => {
      const isSeed = i === 0
      const radius = isSeed
        ? SEED_RADIUS
        : NODE_MIN + (NODE_MAX - NODE_MIN) * Math.pow(n.score, 0.55)
      const targetR = isSeed ? 0 : orbitR(n.score)

      // Spread evenly around circle; slight random offset avoids symmetry
      const idx   = isSeed ? 0 : sorted.indexOf(n)
      const total = Math.max(sorted.length, 1)
      const angle = isSeed ? 0 : (idx / total) * Math.PI * 2 - Math.PI / 2 + (Math.random() - 0.5) * 0.5

      const startX = isSeed ? cx : cx + targetR * Math.cos(angle)
      const startY = isSeed ? cy : cy + targetR * Math.sin(angle)

      // Poster
      let img: HTMLImageElement | null = null
      if (n.poster_url) {
        if (imgCache.current.has(n.id)) {
          img = imgCache.current.get(n.id)!
        } else {
          img = new Image()
          img.crossOrigin = 'anonymous'
          img.src = n.poster_url
          imgCache.current.set(n.id, img)
        }
      }

      const pn: PhysNode = {
        id: n.id, data: n,
        x: startX,
        y: startY,
        vx: 0, vy: 0,
        radius, targetR,
        driftPhase: Math.random() * Math.PI * 2,
        hoverScale: 1.0,
        floatX: 0,
        floatY: 0,
        img, imgLoaded: img?.complete ?? false,
      }
      if (img && !img.complete) {
        img.onload  = () => { pn.imgLoaded = true }
        img.onerror = () => { pn.imgLoaded = false; pn.img = null }
      }
      return pn
    })
  }, [data, orbitR])

  // ── Pre-layout: resolve overlaps synchronously before first render ────────────
  // Runs 200 collision-separation iterations in JS (no RAF, no animation).
  // Result: nodes appear already spread out — no visible sliding on load.
  const preLayout = useCallback((nodes: PhysNode[]) => {
    const W  = logW.current
    const H  = logH.current
    const GAP = 18   // minimum gap between node edges

    for (let iter = 0; iter < 200; iter++) {
      let anyOverlap = false

      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i]
        if (a.targetR === 0) continue   // seed pinned

        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j]
          if (b.targetR === 0) continue

          const ox   = a.x - b.x
          const oy   = a.y - b.y
          const d2   = ox * ox + oy * oy
          const minD = a.radius + b.radius + GAP

          if (d2 < minD * minD) {
            anyOverlap = true
            const d   = Math.sqrt(d2) || 1
            const push = (minD - d) / d * 0.5   // each node moves half
            a.x += ox * push * 0.5
            a.y += oy * push * 0.5
            b.x -= ox * push * 0.5
            b.y -= oy * push * 0.5
          }
        }

        // Keep within canvas
        const pad = a.radius + 10
        a.x = Math.max(pad, Math.min(W - pad, a.x))
        a.y = Math.max(pad, Math.min(H - pad, a.y))
      }

      if (!anyOverlap) break   // early exit once fully resolved
    }
  }, [])

  // ── Physics tick ─────────────────────────────────────────────────────────────
  // Strategy: collision-only separation (no spring) with heavy damping.
  // Once all velocities are negligible the physics block is skipped entirely;
  // only the draw-time floatY bob continues — giving a subtle, calm float.
  const tick = useCallback((nodes: PhysNode[]) => {
    const t  = Date.now()
    const cx = logW.current / 2
    const cy = logH.current / 2
    const W  = logW.current
    const H  = logH.current

    // Pin seed, freeze dragged node
    nodes.forEach((n) => {
      if (n.targetR === 0) { n.x = cx; n.y = cy; n.vx = 0; n.vy = 0; n.floatX = 0; n.floatY = 0 }
      else if (n === dragRef.current) { n.vx = 0; n.vy = 0; n.floatX = 0; n.floatY = 0 }
    })

    // Check if already settled — skip heavy collision, only update float
    const moving = nodes.some(
      (n) => n.targetR !== 0 && n !== dragRef.current &&
             (Math.abs(n.vx) > SETTLE_VEL || Math.abs(n.vy) > SETTLE_VEL)
    )

    if (!moving) {
      nodes.forEach((n) => {
        if (n.targetR === 0 || n === dragRef.current) return
        n.floatX = Math.cos(t / FLOAT_X_MS + n.driftPhase * 1.3) * FLOAT_X_AMP
        n.floatY = Math.sin(t / FLOAT_Y_MS + n.driftPhase)       * FLOAT_Y_AMP
        // Smooth hover scale animation (runs even when physics is settled)
        const targetScale = n.id === hoveredRef.current ? HOVER_SCALE_TARGET : 1.0
        n.hoverScale += (targetScale - n.hoverScale) * HOVER_SCALE_SPEED
      })
      return
    }

    // Collision-only physics (runs until nodes stop overlapping)
    nodes.forEach((n) => {
      if (n.targetR === 0 || n === dragRef.current) return

      nodes.forEach((o) => {
        if (o.id === n.id) return
        const ox   = n.x - o.x
        const oy   = n.y - o.y
        const d2   = ox * ox + oy * oy || 1
        const minD = n.radius + o.radius + 18
        if (d2 < minD * minD) {
          const d = Math.sqrt(d2)
          const f = (minD - d) / d * 0.30   // stronger push — resolves overlaps fast
          n.vx += ox * f
          n.vy += oy * f
        }
      })

      n.vx *= DAMPING
      n.vy *= DAMPING
      n.x  += n.vx
      n.y  += n.vy

      const pad = n.radius + 10
      n.x = Math.max(pad, Math.min(W - pad, n.x))
      n.y = Math.max(pad, Math.min(H - pad, n.y))

      n.floatX = Math.cos(t / FLOAT_X_MS + n.driftPhase * 1.3) * FLOAT_X_AMP
      n.floatY = Math.sin(t / FLOAT_Y_MS + n.driftPhase)       * FLOAT_Y_AMP
      const targetScale = n.id === hoveredRef.current ? HOVER_SCALE_TARGET : 1.0
      n.hoverScale += (targetScale - n.hoverScale) * HOVER_SCALE_SPEED
    })
  }, [])

  // ── Draw ─────────────────────────────────────────────────────────────────────
  const draw = useCallback((
    ctx: CanvasRenderingContext2D,
    nodes: PhysNode[],
    hovId: number | null,
  ) => {
    const W   = logW.current
    const H   = logH.current
    const t   = Date.now()
    const cam = camRef.current
    const cx  = W / 2
    const cy  = H / 2

    ctx.clearRect(0, 0, W, H)

    // ── 1. Background ───────────────────────────────────────────────────────
    ctx.fillStyle = BG
    ctx.fillRect(0, 0, W, H)

    // ── 2. Stars (screen-space — don't move with camera) ───────────────────
    starsRef.current.forEach((s) => {
      const a = s.twinkles
        ? s.baseAlpha * (0.55 + 0.45 * Math.sin(t / 1000 + s.phase))
        : s.baseAlpha
      ctx.beginPath()
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(255,255,255,${a})`
      ctx.fill()
    })

    // ── 3. Camera transform (world space from here) ────────────────────────
    ctx.save()
    ctx.translate(cam.x, cam.y)
    ctx.scale(cam.scale, cam.scale)

    // ── 4. Nebula — unique per movie genre ─────────────────────────────────
    const seed = nodes[0]
    if (seed) {
      const sx = seed.x, sy = seed.y
      const nm = Math.max(W, H)
      // Wide glow
      const ng1 = ctx.createRadialGradient(sx, sy, 0, sx, sy, nm * 0.58)
      ng1.addColorStop(0, h2r(accentColor, 0.10))
      ng1.addColorStop(0.45, h2r(accentColor, 0.04))
      ng1.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = ng1; ctx.fillRect(0, 0, W, H)
      // Concentrated inner
      const ng2 = ctx.createRadialGradient(sx, sy, 0, sx, sy, nm * 0.22)
      ng2.addColorStop(0, h2r(accentColor, 0.18))
      ng2.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = ng2; ctx.fillRect(0, 0, W, H)
    }

    const byId = new Map(nodes.map((n) => [n.id, n]))

    // ── 5a. Ghost edges — always-visible whisper lines ──────────────────────
    // Near-invisible by default; serve as spatial orientation cues only.
    ctx.setLineDash([])
    data.edges.forEach((e) => {
      const src = byId.get(e.source); const tgt = byId.get(e.target)
      if (!src || !tgt) return
      const isHot = hovId !== null && (src.id === hovId || tgt.id === hovId)
      if (isHot) return   // hot edges drawn in pass 5b
      const sx = src.x + src.floatX, sy = src.y + src.floatY
      const tx = tgt.x + tgt.floatX, ty = tgt.y + tgt.floatY
      ctx.globalAlpha = hovId !== null ? 0.02 : 0.055
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth   = 0.45
      ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(tx, ty); ctx.stroke()
    })
    ctx.globalAlpha = 1

    // ── 5b. Active edges — hover reveals the ghost line's true colour ──────────
    // Same aesthetic as ghost lines (thin, ethereal) — just lit up with
    // the edge's colour. No thick glow, no dashes. Gossamer but visible.
    if (hovId !== null) {
      data.edges.forEach((e) => {
        const src = byId.get(e.source); const tgt = byId.get(e.target)
        if (!src || !tgt) return
        if (src.id !== hovId && tgt.id !== hovId) return

        const sx  = src.x + src.floatX, sy = src.y + src.floatY
        const tx  = tgt.x + tgt.floatX, ty = tgt.y + tgt.floatY
        const col = EDGE_COLORS[e.type] ?? '#94A3B8'

        // Bezier control point — same gentle curve as before
        const edgeLen = Math.hypot(tx - sx, ty - sy) || 1
        const curve   = Math.min(edgeLen * 0.22, 38)
        const cpx     = (sx + tx) / 2 - ((ty - sy) / edgeLen) * curve
        const cpy     = (sy + ty) / 2 + ((tx - sx) / edgeLen) * curve

        const tracePath = () => {
          ctx.beginPath()
          ctx.moveTo(sx, sy)
          ctx.quadraticCurveTo(cpx, cpy, tx, ty)
        }

        ctx.setLineDash([])
        ctx.lineCap = 'round'

        // Faint colour whisper underneath — barely there, just warms the line
        tracePath()
        ctx.strokeStyle = col; ctx.lineWidth = 5; ctx.globalAlpha = 0.07
        ctx.stroke()

        // The line itself — thin like the ghost but coloured and visible
        tracePath()
        ctx.strokeStyle = col; ctx.lineWidth = 0.75; ctx.globalAlpha = 0.78
        ctx.stroke()

        ctx.lineCap = 'butt'

        // Tiny dot at target end — same restraint, just a colour pip
        const dotX = src.id === hovId ? tx : sx
        const dotY = src.id === hovId ? ty : sy
        ctx.beginPath(); ctx.arc(dotX, dotY, 1.8, 0, Math.PI * 2)
        ctx.fillStyle = col; ctx.globalAlpha = 0.85; ctx.fill()

        ctx.globalAlpha = 1
      })
    }

    // ── 6. Glow halos — subtle ring behind each node ────────────────────────
    nodes.forEach((n) => {
      const isSeed = n.targetR === 0
      const isHov  = n.id === hovId
      const isDim  = hovId !== null && !isHov && !isSeed
      const nx = n.x + n.floatX, ny = n.y + n.floatY
      const nr = n.radius * n.hoverScale
      const nc = isSeed ? accentColor : (EDGE_COLORS[n.data.edge_type ?? ''] ?? '#94A3B8')

      // Restrained base glow on all non-dimmed nodes; bigger on hover
      if (!isDim) {
        const glowR = nr * (isHov ? 2.8 : 1.9)
        const gg = ctx.createRadialGradient(nx, ny, nr * 0.5, nx, ny, glowR)
        gg.addColorStop(0, h2r(nc, isHov ? 0.30 : 0.08))
        gg.addColorStop(1, 'rgba(0,0,0,0)')
        ctx.fillStyle = gg
        ctx.beginPath(); ctx.arc(nx, ny, glowR, 0, Math.PI * 2); ctx.fill()
      }
    })

    // ── 7. Seed rings + hover score arc ────────────────────────────────────
    nodes.forEach((n) => {
      const isSeed = n.targetR === 0
      const isHov  = n.id === hovId
      const nx = n.x + n.floatX, ny = n.y + n.floatY
      const nr = n.radius * n.hoverScale
      const nc = isSeed ? accentColor : (EDGE_COLORS[n.data.edge_type ?? ''] ?? '#94A3B8')

      if (isSeed) {
        // Single elegant breathing ring
        const pulse = 0.5 + 0.5 * Math.sin(t / 700)
        ctx.strokeStyle = accentColor; ctx.setLineDash([])
        ctx.beginPath(); ctx.arc(nx, ny, nr + 12, 0, Math.PI * 2)
        ctx.lineWidth = 1.2; ctx.globalAlpha = pulse * 0.55; ctx.stroke()
        ctx.globalAlpha = 1
      } else if (isHov) {
        // Score arc revealed only on hover — feels like discovery
        const end = -Math.PI / 2 + n.data.score * Math.PI * 2
        ctx.beginPath(); ctx.arc(nx, ny, nr + 4, -Math.PI / 2, end)
        ctx.strokeStyle = nc; ctx.lineWidth = 1.8; ctx.lineCap = 'round'
        ctx.globalAlpha = 0.85; ctx.stroke()
        ctx.lineCap = 'butt'; ctx.globalAlpha = 1
      }
    })

    // ── 8. Posters, borders, labels ────────────────────────────────────────
    nodes.forEach((n) => {
      const isSeed  = n.targetR === 0
      const isHov   = n.id === hovId
      const isDim   = hovId !== null && !isHov && !isSeed
      const nc      = isSeed ? accentColor : (EDGE_COLORS[n.data.edge_type ?? ''] ?? '#94A3B8')
      const nx      = n.x + n.floatX
      const ny      = n.y + n.floatY
      const nr      = n.radius * n.hoverScale   // scaled radius

      ctx.globalAlpha = isDim ? 0.20 : 1

      if (isHov || isSeed) { ctx.shadowBlur = isSeed ? 28 : 18; ctx.shadowColor = nc }

      // Poster / fallback (clipped circle)
      ctx.save()
      ctx.beginPath(); ctx.arc(nx, ny, nr, 0, Math.PI * 2); ctx.clip()
      if (n.img && n.imgLoaded) {
        try { ctx.drawImage(n.img, nx - nr, ny - nr, nr * 2, nr * 2) }
        catch { drawFallback(ctx, n, nx, ny, nr, nc) }
      } else {
        drawFallback(ctx, n, nx, ny, nr, nc)
      }
      ctx.restore()

      // Border
      ctx.shadowBlur = 0
      ctx.beginPath(); ctx.arc(nx, ny, nr, 0, Math.PI * 2)
      if (isSeed) {
        ctx.strokeStyle = accentColor; ctx.lineWidth = 2.0
      } else if (isHov) {
        ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.4
      } else {
        ctx.strokeStyle = `rgba(255,255,255,${isDim ? 0.04 : 0.10})`; ctx.lineWidth = 0.6
      }
      ctx.stroke(); ctx.globalAlpha = 1

      // Labels — only seed (always) and hovered node
      if (isSeed || isHov) {
        const nr2 = nr   // alias for clarity
        const fs  = isSeed
          ? Math.max(11, Math.min(14, nr2 * 0.26))
          : Math.max(10, Math.min(13, nr2 * 0.28))
        const label = n.data.title.length > 22 ? n.data.title.slice(0, 20) + '…' : n.data.title
        ctx.font      = `${isSeed ? 700 : 600} ${fs}px system-ui, sans-serif`
        ctx.textAlign = 'center'; ctx.fillStyle = isSeed ? accentColor : '#ffffff'
        ctx.shadowBlur = 8; ctx.shadowColor = '#000'
        ctx.fillText(label, nx, ny + nr2 + fs + 4)
        if (n.data.year) {
          ctx.font      = `400 ${fs - 2}px system-ui`
          ctx.fillStyle = 'rgba(255,255,255,0.38)'
          ctx.fillText(n.data.year, nx, ny + nr2 + fs + 4 + (fs - 1))
        }
        ctx.shadowBlur = 0
      }
    })

    ctx.restore()  // end camera
    ctx.textAlign = 'left'; ctx.globalAlpha = 1
  }, [data.edges, accentColor])

  // ── RAF loop ────────────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const applyResize = () => {
      const dpr = window.devicePixelRatio || 1
      logW.current = canvas.offsetWidth
      logH.current = canvas.offsetHeight
      canvas.width  = logW.current * dpr
      canvas.height = logH.current * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      buildStars(logW.current, logH.current)
      const nodes = buildNodes()
      preLayout(nodes)
      nodesRef.current = nodes
    }
    applyResize()

    const ro = new ResizeObserver(applyResize)
    ro.observe(canvas)

    const loop = () => {
      tick(nodesRef.current)
      draw(ctx, nodesRef.current, hoveredRef.current)
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)

    return () => { cancelAnimationFrame(rafRef.current); ro.disconnect() }
  }, [data, buildStars, buildNodes, preLayout, tick, draw])

  // ── Wheel zoom ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const rect = canvas.getBoundingClientRect()
      const cam  = camRef.current
      const f    = e.deltaY < 0 ? 1.13 : 0.89
      const ns   = Math.max(0.22, Math.min(5, cam.scale * f))
      const mx   = e.clientX - rect.left
      const my   = e.clientY - rect.top
      cam.x = mx - (mx - cam.x) * (ns / cam.scale)
      cam.y = my - (my - cam.y) * (ns / cam.scale)
      cam.scale = ns
    }
    canvas.addEventListener('wheel', onWheel, { passive: false })
    return () => canvas.removeEventListener('wheel', onWheel)
  }, [])

  // ── World coordinate helper ──────────────────────────────────────────────────
  const worldXY = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current!
    const rect   = canvas.getBoundingClientRect()
    const cam    = camRef.current
    return {
      x: (clientX - rect.left  - cam.x) / cam.scale,
      y: (clientY - rect.top   - cam.y) / cam.scale,
    }
  }

  const getNodeAt = (wx: number, wy: number) => {
    for (const n of [...nodesRef.current].reverse()) {
      const dx = wx - (n.x + n.floatX), dy = wy - (n.y + n.floatY)
      const nr = n.radius * n.hoverScale
      if (dx * dx + dy * dy <= (nr + 8) ** 2) return n
    }
    return null
  }

  // ── Mouse handlers ───────────────────────────────────────────────────────────
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const { x, y } = worldXY(e.clientX, e.clientY)
    const n = getNodeAt(x, y)
    hasPannedRef.current = false
    if (n) {
      dragRef.current = n; n.vx = 0; n.vy = 0
    } else {
      isPanRef.current  = true
      const canvas = canvasRef.current!
      const rect   = canvas.getBoundingClientRect()
      panStartRef.current = {
        sx: e.clientX - rect.left, sy: e.clientY - rect.top,
        cx: camRef.current.x,      cy: camRef.current.y,
      }
    }
  }, [])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (dragRef.current) {
      const { x, y } = worldXY(e.clientX, e.clientY)
      dragRef.current.x = x; dragRef.current.y = y
      dragRef.current.vx = 0; dragRef.current.vy = 0
      hasPannedRef.current = true
      return
    }
    if (isPanRef.current) {
      const canvas = canvasRef.current!
      const rect   = canvas.getBoundingClientRect()
      const sx = e.clientX - rect.left
      const sy = e.clientY - rect.top
      camRef.current.x = panStartRef.current.cx + sx - panStartRef.current.sx
      camRef.current.y = panStartRef.current.cy + sy - panStartRef.current.sy
      hasPannedRef.current = true
      if (canvas) canvas.style.cursor = 'grabbing'
      return
    }
    const { x, y } = worldXY(e.clientX, e.clientY)
    const n = getNodeAt(x, y)
    const newId = n?.id ?? null
    if (newId !== hoveredRef.current) {
      hoveredRef.current = newId
      onNodeHover(n?.data ?? null)
      if (canvasRef.current)
        canvasRef.current.style.cursor = newId !== null ? 'pointer' : 'default'
    }
  }, [onNodeHover])

  const handleMouseUp = useCallback(() => {
    dragRef.current = null
    if (isPanRef.current) {
      isPanRef.current = false
      if (canvasRef.current) canvasRef.current.style.cursor = 'default'
    }
  }, [])

  const handleClick = useCallback((e: React.MouseEvent) => {
    if (hasPannedRef.current) return
    const { x, y } = worldXY(e.clientX, e.clientY)
    const n = getNodeAt(x, y)
    if (n) onNodeClick(n.data)
  }, [onNodeClick])

  const handleDblClick = useCallback(() => {
    camRef.current = { x: 0, y: 0, scale: 1 }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{ display: 'block', width: '100%', height: '100%' }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => {
        hoveredRef.current = null; onNodeHover(null)
        dragRef.current = null; isPanRef.current = false
        if (canvasRef.current) canvasRef.current.style.cursor = 'default'
      }}
      onClick={handleClick}
      onDoubleClick={handleDblClick}
    />
  )
}

// ── Fallback tile ─────────────────────────────────────────────────────────────
function drawFallback(ctx: CanvasRenderingContext2D, n: PhysNode, nx: number, ny: number, nr: number, accent: string) {
  const g = ctx.createRadialGradient(nx, ny, 0, nx, ny, nr)
  g.addColorStop(0, '#1a1030')
  g.addColorStop(1, '#070510')
  ctx.fillStyle = g
  ctx.fillRect(nx - nr, ny - nr, nr * 2, nr * 2)
  ctx.font         = `bold ${Math.max(12, nr * 0.5)}px system-ui`
  ctx.textAlign    = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillStyle    = h2r(accent, 0.85)
  ctx.fillText(n.data.title[0]?.toUpperCase() ?? '?', nx, ny)
  ctx.textBaseline = 'alphabetic'
}

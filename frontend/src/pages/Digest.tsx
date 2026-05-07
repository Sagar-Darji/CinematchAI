import { useEffect, useState, useCallback, useRef } from 'react'
import { Rss, RefreshCw, ExternalLink, ChevronDown, ChevronUp, Loader2, Film, Clapperboard, Sparkles } from 'lucide-react'
import { fetchDigest, triggerDigestRefresh, type DigestItem, type DigestCategory, type DigestLang } from '@/lib/api'
import { cn } from '@/lib/utils'

// ── Constants ─────────────────────────────────────────────────────────────────

const PAGE_SIZE = 20

const CATEGORY_TABS: { key: DigestCategory; label: string; emoji: string }[] = [
  { key: 'all',       label: 'All',       emoji: '🎬' },
  { key: 'bollywood', label: 'Bollywood', emoji: '🎥' },
  { key: 'hollywood', label: 'Hollywood', emoji: '🌟' },
  { key: 'trailer',   label: 'Trailers',  emoji: '▶️' },
  { key: 'casting',   label: 'Casting',   emoji: '🎭' },
  { key: 'leak',      label: 'Leaks',     emoji: '🔥' },
  { key: 'ott',       label: 'OTT',       emoji: '📺' },
]

const LANG_TABS: { key: DigestLang; label: string }[] = [
  { key: 'all',     label: 'All' },
  { key: 'hindi',   label: '🇮🇳 Hindi' },
  { key: 'english', label: '🌐 English' },
]

// ── Category badge ────────────────────────────────────────────────────────────

const CAT_COLORS: Record<string, string> = {
  bollywood: 'rgba(255,165,0,0.18)',
  hollywood: 'rgba(99,179,237,0.18)',
  trailer:   'rgba(160,230,100,0.18)',
  casting:   'rgba(200,120,255,0.18)',
  leak:      'rgba(255,80,80,0.18)',
  ott:       'rgba(50,200,180,0.18)',
  general:   'rgba(150,150,150,0.12)',
}
const CAT_TEXT: Record<string, string> = {
  bollywood: '#FFA500',
  hollywood: '#63b3ed',
  trailer:   '#a0e664',
  casting:   '#c878ff',
  leak:      '#ff5050',
  ott:       '#32c8b4',
  general:   '#888',
}

const EMPTY_MESSAGES: Record<string, string> = {
  all:       'No stories yet — hit Fetch to pull the latest.',
  bollywood: 'No Bollywood stories found.',
  hollywood: 'No Hollywood stories found.',
  trailer:   'No trailers or teasers found.',
  casting:   'No casting news found.',
  leak:      'No leaks or rumours found.',
  ott:       'No OTT / streaming news found.',
  general:   'No stories found.',
}

function CategoryBadge({ category }: { category: string }) {
  return (
    <span
      className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full tracking-wider"
      style={{
        background: CAT_COLORS[category] ?? CAT_COLORS.general,
        color: CAT_TEXT[category] ?? CAT_TEXT.general,
      }}
    >
      {category}
    </span>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime()
    const m = Math.floor(diff / 60000)
    if (m < 2) return 'just now'
    if (m < 60) return `${m}m ago`
    const h = Math.floor(m / 60)
    if (h < 24) return `${h}h ago`
    return `${Math.floor(h / 24)}d ago`
  } catch { return '' }
}

function isNew(iso: string): boolean {
  try { return Date.now() - new Date(iso).getTime() < 7200000 } // 2h
  catch { return false }
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function DigestSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
      {[0,1,2,3,4,5].map(i => (
        <div
          key={i}
          className="rounded-xl p-4"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', animationDelay: `${i * 0.06}s` }}
        >
          <div className="flex gap-3">
            <div className="flex-1 space-y-2.5">
              <div className="flex gap-2 items-center">
                <div className="skeleton w-16 h-4 rounded-full" />
                <div className="skeleton w-20 h-3 rounded" style={{ opacity: 0.5 }} />
              </div>
              <div className="skeleton-text w-5/6" />
              <div className="skeleton-text w-3/4" style={{ opacity: 0.7 }} />
              <div className="space-y-1.5 pt-1">
                <div className="skeleton-text w-full" style={{ opacity: 0.5 }} />
                <div className="skeleton-text w-4/5" style={{ opacity: 0.4 }} />
              </div>
            </div>
            <div className="skeleton w-24 h-16 rounded-lg flex-shrink-0" />
          </div>
        </div>
      ))}
    </div>
  )
}

// ── News card ─────────────────────────────────────────────────────────────────

function DigestCard({ item, index }: { item: DigestItem; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const [imgFailed, setImgFailed] = useState(false)
  const hasBullets = item.bullets && item.bullets.length > 0
  const extraBullets = hasBullets ? item.bullets.length - 2 : 0
  const showImg = item.image_url && !imgFailed
  const timeStr = relativeTime(item.published_at || item.fetched_at)
  const fresh = isNew(item.fetched_at)

  return (
    <div
      className="rounded-xl overflow-hidden animate-fade-in group"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        animationDelay: `${Math.min(index, 8) * 0.05}s`,
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-hover)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
    >
      {/* ── Main content area ── */}
      <div className="p-4 flex gap-3">
        {/* Text */}
        <div className="flex-1 min-w-0 space-y-2">
          {/* Meta row */}
          <div className="flex items-center gap-2 flex-wrap">
            <CategoryBadge category={item.category} />
            {fresh && (
              <span
                className="text-[10px] font-bold px-1.5 py-0.5 rounded-full flex items-center gap-0.5"
                style={{ background: 'rgba(245,197,24,0.15)', color: 'var(--accent-gold)' }}
              >
                <Sparkles size={9} /> NEW
              </span>
            )}
            <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
              {item.source_name} · {timeStr}
            </span>
          </div>

          {/* Headline — primary action: opens source */}
          <a
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="block text-sm font-bold leading-snug text-white hover:underline decoration-1 underline-offset-2"
            style={{ textDecorationColor: 'var(--accent-gold)' }}
          >
            {item.headline || item.title}
          </a>

          {/* Bullets — first 2 always visible */}
          {hasBullets && (
            <ul className="space-y-1">
              {item.bullets.slice(0, expanded ? undefined : 2).map((b, i) => (
                <li key={i} className="flex gap-2 text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                  <span className="mt-0.5 flex-shrink-0" style={{ color: 'var(--accent-gold)' }}>•</span>
                  <span>{b.replace(/^[•\-]\s*/, '')}</span>
                </li>
              ))}
            </ul>
          )}

          {/* Show more bullets toggle (not description) */}
          {hasBullets && extraBullets > 0 && !expanded && (
            <button
              onClick={() => setExpanded(true)}
              className="flex items-center gap-1 text-[11px] font-semibold mt-0.5"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
            >
              <ChevronDown size={12} />
              {extraBullets} more point{extraBullets > 1 ? 's' : ''}
            </button>
          )}
          {expanded && extraBullets > 0 && (
            <button
              onClick={() => setExpanded(false)}
              className="flex items-center gap-1 text-[11px] font-semibold"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
            >
              <ChevronUp size={12} />
              Show less
            </button>
          )}
        </div>

        {/* Thumbnail — right side */}
        <div
          className="w-24 h-16 rounded-lg flex-shrink-0 flex items-center justify-center overflow-hidden"
          style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)' }}
        >
          {showImg ? (
            <img
              src={item.image_url!}
              alt=""
              className="w-full h-full object-cover"
              onError={() => setImgFailed(true)}
            />
          ) : (
            <Film size={20} style={{ color: 'var(--border-hover)', opacity: 0.6 }} />
          )}
        </div>
      </div>

      {/* ── Footer ── */}
      <div
        className="px-4 py-2.5 flex items-center justify-between border-t"
        style={{ borderColor: 'var(--border)' }}
      >
        {/* Expanded description */}
        {expanded && item.description ? (
          <p
            className="text-xs leading-relaxed flex-1 mr-4"
            style={{ color: 'var(--text-muted)' }}
          >
            {item.description.slice(0, 400)}{item.description.length > 400 ? '…' : ''}
          </p>
        ) : (
          <span />
        )}

        <a
          href={item.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg flex-shrink-0"
          style={{
            background: 'rgba(245,197,24,0.1)',
            color: 'var(--accent-gold)',
            border: '1px solid rgba(245,197,24,0.2)',
            transition: 'background 0.15s',
          }}
          onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'rgba(245,197,24,0.2)')}
          onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = 'rgba(245,197,24,0.1)')}
        >
          Read story <ExternalLink size={11} />
        </a>
      </div>
    </div>
  )
}

// ── Refresh banner ────────────────────────────────────────────────────────────

function RefreshBanner({ state }: { state: 'fetching' | 'done' | null }) {
  if (!state) return null
  return (
    <div
      className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold mb-4 animate-fade-in"
      style={{
        background: state === 'done' ? 'rgba(160,230,100,0.1)' : 'rgba(245,197,24,0.08)',
        border: `1px solid ${state === 'done' ? 'rgba(160,230,100,0.3)' : 'rgba(245,197,24,0.2)'}`,
        color: state === 'done' ? '#a0e664' : 'var(--accent-gold)',
      }}
    >
      {state === 'fetching'
        ? <><Loader2 size={14} className="animate-spin flex-shrink-0" /> Fetching fresh stories — this takes ~30 seconds…</>
        : <><span>✓</span> Feed refreshed! Scroll up for new stories.</>
      }
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Digest() {
  const [allItems, setAllItems]       = useState<DigestItem[]>([])
  const [visible, setVisible]         = useState(PAGE_SIZE)
  const [loading, setLoading]         = useState(true)
  const [stale, setStale]             = useState(false)   // dim while re-fetching
  const [refreshBanner, setRefreshBanner] = useState<'fetching' | 'done' | null>(null)
  const [error, setError]             = useState('')
  const [lastRefresh, setLastRefresh] = useState<string | null>(null)
  const [category, setCategory]       = useState<DigestCategory>('all')
  const [lang, setLang]               = useState<DigestLang>('all')
  const filterBarRef = useRef<HTMLDivElement>(null)
  const bannerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const load = useCallback(async (cat: DigestCategory, l: DigestLang, soft = false) => {
    if (soft) {
      setStale(true)   // keep items visible but dim
    } else {
      setLoading(true)
    }
    setError('')
    try {
      const data = await fetchDigest(cat, l, 100)
      setAllItems(data.items)
      setLastRefresh(data.last_refresh)
      setVisible(PAGE_SIZE)
    } catch {
      setError('Failed to load digest. Is the API running?')
    } finally {
      setLoading(false)
      setStale(false)
    }
  }, [])

  // Scroll to filter bar + reload on filter change
  const changeCategory = (cat: DigestCategory) => {
    setCategory(cat)
    filterBarRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  const changeLang = (l: DigestLang) => {
    setLang(l)
    filterBarRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  useEffect(() => {
    // Soft load (keep content) on filter changes after first load
    if (!loading) {
      load(category, lang, true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, lang])

  useEffect(() => { load(category, lang) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRefresh = async () => {
    setRefreshBanner('fetching')
    if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current)
    try {
      await triggerDigestRefresh()
      // Poll until done (max 60s)
      let waited = 0
      const poll = setInterval(async () => {
        waited += 4000
        if (waited >= 60000) { clearInterval(poll); return }
        const data = await fetchDigest(category, lang, 100)
        if (data.items.length > allItems.length || waited >= 35000) {
          clearInterval(poll)
          setAllItems(data.items)
          setLastRefresh(data.last_refresh)
          setVisible(PAGE_SIZE)
          setRefreshBanner('done')
          bannerTimerRef.current = setTimeout(() => setRefreshBanner(null), 4000)
        }
      }, 4000)
    } catch {
      setRefreshBanner(null)
    }
  }

  const visibleItems = allItems.slice(0, visible)
  const hasMore = visible < allItems.length

  const relRefresh = lastRefresh ? relativeTime(lastRefresh) : null

  return (
    <div className="min-h-screen w-full">
      {/* ── Page header (not sticky) ── */}
      <div className="px-5 md:px-8 pt-6 pb-4 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-white flex items-center gap-2.5">
            <Rss size={24} style={{ color: 'var(--accent-gold)' }} />
            CineDigest
          </h1>
          <p className="text-xs mt-1.5 flex items-center gap-2" style={{ color: 'var(--text-muted)' }}>
            <span>Bollywood · Hollywood · OTT · Casting · Leaks — one feed</span>
            {allItems.length > 0 && (
              <span
                className="px-1.5 py-0.5 rounded-md text-[10px] font-bold"
                style={{ background: 'var(--bg-overlay)', color: 'var(--accent-gold)' }}
              >
                {allItems.length} stories
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <button
            onClick={handleRefresh}
            disabled={refreshBanner === 'fetching'}
            title="Fetch fresh news"
            className="flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-lg disabled:opacity-40"
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              color: 'var(--accent-gold)',
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={13} className={cn(refreshBanner === 'fetching' && 'animate-spin')} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
          {relRefresh && (
            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>updated {relRefresh}</span>
          )}
        </div>
      </div>

      {/* ── Sticky filter bar ── */}
      <div
        ref={filterBarRef}
        className="sticky top-14 z-20 px-5 md:px-8 pb-3 pt-3 space-y-2"
        style={{
          background: 'rgba(10,10,15,0.85)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        {/* Lang + Category in one bar */}
        <div className="flex items-center gap-2 overflow-x-auto scrollbar-hide pb-0.5">
          {/* Language pills — compact */}
          <div className="flex gap-1 flex-shrink-0 mr-1">
            {LANG_TABS.map(t => (
              <button
                key={t.key}
                onClick={() => changeLang(t.key)}
                className="text-[11px] font-semibold px-2.5 py-1.5 rounded-full whitespace-nowrap"
                style={{
                  background: lang === t.key ? 'rgba(245,197,24,0.12)' : 'transparent',
                  color: lang === t.key ? 'var(--accent-gold)' : 'var(--text-muted)',
                  border: `1px solid ${lang === t.key ? 'rgba(245,197,24,0.4)' : 'var(--border)'}`,
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Divider */}
          <div className="w-px h-4 flex-shrink-0" style={{ background: 'var(--border)' }} />

          {/* Category chips */}
          {CATEGORY_TABS.map(t => (
            <button
              key={t.key}
              onClick={() => changeCategory(t.key)}
              className="flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1.5 rounded-full whitespace-nowrap flex-shrink-0"
              style={{
                background: category === t.key ? 'var(--accent-gold)' : 'transparent',
                color: category === t.key ? '#0a0a0f' : 'var(--text-muted)',
                border: `1px solid ${category === t.key ? 'var(--accent-gold)' : 'var(--border)'}`,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {t.emoji} {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Content area ── */}
      <div className="px-5 md:px-8 pt-4 pb-8">
        <RefreshBanner state={refreshBanner} />

        {loading ? (
          <DigestSkeleton />
        ) : error ? (
          <div className="text-center py-20 space-y-4">
            <Clapperboard size={40} className="mx-auto" style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{error}</p>
            <button
              onClick={() => load(category, lang)}
              className="text-xs font-semibold px-4 py-2 rounded-lg"
              style={{ background: 'var(--bg-card)', color: 'var(--accent-gold)', border: '1px solid var(--border)', cursor: 'pointer' }}
            >
              Try again
            </button>
          </div>
        ) : allItems.length === 0 ? (
          <div className="text-center py-20 space-y-4">
            <Film size={40} className="mx-auto" style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {EMPTY_MESSAGES[category] ?? EMPTY_MESSAGES.all}
            </p>
            <button
              onClick={handleRefresh}
              disabled={refreshBanner === 'fetching'}
              className="text-xs font-semibold px-4 py-2 rounded-lg disabled:opacity-40"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
            >
              {refreshBanner === 'fetching'
                ? <span className="flex items-center gap-1.5"><Loader2 size={13} className="animate-spin" /> Fetching…</span>
                : 'Fetch Now'
              }
            </button>
          </div>
        ) : (
          <>
            <div
              className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 transition-opacity duration-200"
              style={{ opacity: stale ? 0.45 : 1, pointerEvents: stale ? 'none' : 'auto' }}
            >
              {visibleItems.map((item, i) => (
                <DigestCard key={item.id} item={item} index={i} />
              ))}
            </div>

            {/* Load more */}
            {hasMore && (
              <div className="text-center mt-6">
                <button
                  onClick={() => setVisible(v => v + PAGE_SIZE)}
                  className="text-sm font-bold px-6 py-2.5 rounded-xl"
                  style={{
                    background: 'var(--bg-card)',
                    color: 'var(--accent-gold)',
                    border: '1px solid var(--border)',
                    cursor: 'pointer',
                  }}
                >
                  Load more · {allItems.length - visible} remaining
                </button>
              </div>
            )}

            {!hasMore && allItems.length > 0 && (
              <p className="text-center text-xs mt-6" style={{ color: 'var(--text-muted)' }}>
                You're all caught up — {allItems.length} stories loaded
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

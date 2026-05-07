import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, ChevronLeft } from 'lucide-react'
import { MovieCard, movieToRec } from '@/components/ui/MovieCard'
import type { Movie } from '@/lib/api'

interface RailProps {
  title: string
  items: Movie[]
  loading?: boolean
  seeAllHref?: string
  emptyMessage?: string
}

export function Rail({ title, items, loading, seeAllHref, emptyMessage }: RailProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  const scroll = (dir: 'left' | 'right') => {
    if (!scrollRef.current) return
    const w = scrollRef.current.clientWidth
    scrollRef.current.scrollBy({ left: dir === 'left' ? -w * 0.85 : w * 0.85, behavior: 'smooth' })
  }

  if (!loading && items.length === 0 && !emptyMessage) return null

  return (
    <section className="mb-7">
      <div className="flex items-baseline justify-between px-4 md:px-6 mb-2.5">
        <h2 className="text-base md:text-lg font-black text-white tracking-tight">{title}</h2>
        {seeAllHref && (
          <Link
            to={seeAllHref}
            className="text-xs font-semibold flex items-center gap-1"
            style={{ color: 'var(--accent-gold)', textDecoration: 'none' }}
          >
            See all <ChevronRight size={12} />
          </Link>
        )}
      </div>

      <div className="relative group/rail">
        {/* Scroll arrows — desktop only, only show with hover-capable pointer */}
        <button
          onClick={() => scroll('left')}
          aria-label="Scroll left"
          className="hidden lg:flex absolute left-2 top-1/2 -translate-y-1/2 z-10 w-9 h-9 items-center justify-center rounded-full opacity-0 group-hover/rail:opacity-100 transition-opacity"
          style={{
            background: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(6px)',
            color: '#fff',
            border: '1px solid rgba(255,255,255,0.2)',
            cursor: 'pointer',
          }}
        >
          <ChevronLeft size={18} />
        </button>
        <button
          onClick={() => scroll('right')}
          aria-label="Scroll right"
          className="hidden lg:flex absolute right-2 top-1/2 -translate-y-1/2 z-10 w-9 h-9 items-center justify-center rounded-full opacity-0 group-hover/rail:opacity-100 transition-opacity"
          style={{
            background: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(6px)',
            color: '#fff',
            border: '1px solid rgba(255,255,255,0.2)',
            cursor: 'pointer',
          }}
        >
          <ChevronRight size={18} />
        </button>

        <div
          ref={scrollRef}
          className="flex gap-3 md:gap-4 overflow-x-auto px-4 md:px-6 pb-2 hide-scrollbar"
          style={{ scrollSnapType: 'x mandatory' }}
        >
          {loading
            ? Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="skeleton rounded-xl flex-shrink-0"
                  style={{
                    width: 'clamp(120px, 30vw, 160px)',
                    aspectRatio: '2/3',
                    scrollSnapAlign: 'start',
                    animationDelay: `${i * 0.04}s`,
                  }}
                />
              ))
            : items.length === 0 && emptyMessage
              ? (
                <p className="text-sm py-8" style={{ color: 'var(--text-muted)' }}>
                  {emptyMessage}
                </p>
              )
              : items.map((m, i) => (
                  <div
                    key={`${m.tmdb_id ?? i}`}
                    className="flex-shrink-0"
                    style={{
                      width: 'clamp(120px, 30vw, 160px)',
                      scrollSnapAlign: 'start',
                    }}
                  >
                    <MovieCard rec={movieToRec(m)} compact={false} />
                  </div>
                ))}
        </div>
      </div>
    </section>
  )
}

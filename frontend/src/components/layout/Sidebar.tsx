import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Clapperboard, Sparkles, Search, User, Home } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getSystemStats } from '@/lib/api'

const NAV = [
  { to: '/', icon: Home, label: 'Home' },
  { to: '/recommendations', icon: Sparkles, label: 'For You' },
  { to: '/browse', icon: Search, label: 'Browse' },
  { to: '/profile', icon: User, label: 'Profile' },
]

export function Sidebar() {
  const [movieCount, setMovieCount] = useState<number | null>(null)

  useEffect(() => {
    getSystemStats().then((s) => {
      if (s?.chromadb_count) setMovieCount(s.chromadb_count)
    }).catch(() => {})
  }, [])

  const countLabel = movieCount
    ? movieCount >= 1000
      ? `${(movieCount / 1000).toFixed(0)}K+ movies`
      : `${movieCount} movies`
    : 'movies'

  return (
    <aside
      style={{ background: 'var(--bg-card)', borderRight: '1px solid var(--border)' }}
      className="fixed top-0 left-0 h-full w-16 md:w-56 flex flex-col z-30"
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b" style={{ borderColor: 'var(--border)' }}>
        <Clapperboard size={22} style={{ color: 'var(--accent-gold)' }} />
        <span className="hidden md:block font-bold text-sm tracking-wide" style={{ color: 'var(--accent-gold)' }}>
          CineMatch AI
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-1 px-2">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive ? 'text-white' : 'hover:text-white',
              )
            }
            style={({ isActive }) => ({
              background: isActive ? 'var(--bg-overlay)' : 'transparent',
              color: isActive ? 'var(--accent-gold)' : 'var(--text-muted)',
            })}
          >
            <Icon size={18} />
            <span className="hidden md:block">{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer with live movie count */}
      <div className="px-4 py-4 border-t text-xs hidden md:block" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
        v2.0.0 · {countLabel}
      </div>
    </aside>
  )
}

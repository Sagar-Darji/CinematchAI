import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Sparkles, Search, User, Home, Rss, CalendarDays, Network } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getSystemStats } from '@/lib/api'

const NAV = [
  { to: '/',                icon: Home,         label: 'Home'       },
  { to: '/recommendations', icon: Sparkles,     label: 'For You'    },
  { to: '/web',             icon: Network,      label: 'CineWeb'    },
  { to: '/browse',          icon: Search,       label: 'Discover'   },
  { to: '/digest',          icon: Rss,          label: 'CineDigest' },
  { to: '/calendar',        icon: CalendarDays, label: 'Releases'   },
  { to: '/profile',         icon: User,         label: 'Profile'    },
]

export function Sidebar() {
  const [movieCount, setMovieCount] = useState<number | null>(null)

  useEffect(() => {
    getSystemStats()
      .then((s) => { if (s?.chromadb_count) setMovieCount(s.chromadb_count) })
      .catch(() => {})
  }, [])

  const countLabel = movieCount
    ? movieCount >= 1000 ? `${(movieCount / 1000).toFixed(0)}K+ movies` : `${movieCount} movies`
    : 'movies'

  return (
    <aside
      style={{
        background: 'var(--bg-card)',
        borderRight: '1px solid var(--border)',
        paddingLeft: 'env(safe-area-inset-left, 0px)',
      }}
      className="hidden lg:flex fixed left-0 top-14 w-56 flex-col z-30 h-[calc(100vh-3.5rem)]"
    >
      <nav className="flex-1 py-3 space-y-0.5 px-2 overflow-y-auto">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            id={`tour-nav-${label.toLowerCase().replace(/\s+/g, '-')}`}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive ? 'text-white' : 'hover:text-white'
              )
            }
            style={({ isActive }) => ({
              background: isActive ? 'var(--bg-overlay)' : 'transparent',
              color: isActive ? 'var(--accent-gold)' : 'var(--text-muted)',
              textDecoration: 'none',
            })}
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          v2.0.0 · {countLabel}
        </p>
      </div>
    </aside>
  )
}

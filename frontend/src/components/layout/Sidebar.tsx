import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { Clapperboard, Sparkles, Search, User, Home, LogOut, Rss, CalendarDays, Network } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getSystemStats } from '@/lib/api'
import { useUserStore } from '@/store/useUserStore'
import { useRecommendationStore } from '@/store/useRecommendationStore'

const NAV = [
  { to: '/',               icon: Home,         label: 'Home'       },
  { to: '/recommendations',icon: Sparkles,     label: 'For You'    },
  { to: '/web',            icon: Network,      label: 'CineWeb'    },
  { to: '/browse',         icon: Search,       label: 'Discover'   },
  { to: '/digest',         icon: Rss,          label: 'CineDigest' },
  { to: '/calendar',       icon: CalendarDays, label: 'Releases'   },
  { to: '/profile',        icon: User,         label: 'Profile'    },
]

export function Sidebar() {
  const [movieCount, setMovieCount] = useState<number | null>(null)
  const { userId, isOnboarded, ratingCount, logout } = useUserStore()
  const resetRecs = useRecommendationStore((s) => s.reset)
  const navigate = useNavigate()

  useEffect(() => {
    getSystemStats().then((s) => {
      if (s?.chromadb_count) setMovieCount(s.chromadb_count)
    }).catch(() => {})
  }, [])

  const handleLogout = () => {
    if (confirm('Are you sure you want to log out?')) {
      resetRecs()
      logout()
      navigate('/login')
    }
  }

  const countLabel = movieCount
    ? movieCount >= 1000 ? `${(movieCount / 1000).toFixed(0)}K+ movies` : `${movieCount} movies`
    : 'movies'

  return (
    <aside
      style={{
        background: 'var(--bg-card)',
        borderRight: '1px solid var(--border)',
        paddingTop: 'env(safe-area-inset-top, 0px)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        paddingLeft: 'env(safe-area-inset-left, 0px)',
      }}
      className="fixed top-0 left-0 h-full w-16 md:w-56 flex flex-col z-30"
    >
      {/* Logo */}
      <NavLink to="/" id="tour-logo" className="flex items-center gap-3 px-4 py-5 border-b" style={{ borderColor: 'var(--border)' }}>
        <Clapperboard size={22} style={{ color: 'var(--accent-gold)' }} />
        <span className="hidden md:block font-bold text-sm tracking-wide" style={{ color: 'var(--accent-gold)' }}>
          CineMatch AI
        </span>
      </NavLink>

      {/* User card */}
      {isOnboarded && userId && (
        <div className="mx-2 my-2 px-3 py-2.5 rounded-xl hidden md:flex items-center gap-2.5"
          style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)' }}>
          <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-black flex-shrink-0"
            style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}>
            {userId[0]?.toUpperCase() ?? '?'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold text-white truncate">{userId}</p>
            {ratingCount > 0 && (
              <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{ratingCount} ratings</p>
            )}
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 py-2 space-y-0.5 px-2 overflow-y-auto">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} end={to === '/'}
            id={`tour-nav-${label.toLowerCase().replace(/\s+/g, '-')}`}
            className={({ isActive }) =>
              cn('flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive ? 'text-white' : 'hover:text-white')
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

      {/* Footer */}
      <div className="px-2 py-3 border-t space-y-1" style={{ borderColor: 'var(--border)' }}>
        {isOnboarded && userId && (
          <button onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium hover:text-white transition-colors"
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', textAlign: 'left' }}>
            <LogOut size={16} />
            <span className="hidden md:block">Log Out</span>
          </button>
        )}
        <div className="px-3 text-xs hidden md:block" style={{ color: 'var(--text-muted)' }}>
          v2.0.0 · {countLabel}
        </div>
      </div>
    </aside>
  )
}

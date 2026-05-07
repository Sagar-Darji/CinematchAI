import { NavLink } from 'react-router-dom'
import { Home, Sparkles, Search, Bookmark, User } from 'lucide-react'
import { cn } from '@/lib/utils'

const TABS = [
  { to: '/',                icon: Home,     label: 'Home'      },
  { to: '/recommendations', icon: Sparkles, label: 'For You'   },
  { to: '/browse',          icon: Search,   label: 'Discover'  },
  { to: '/watchlist',       icon: Bookmark, label: 'Watchlist' },
  { to: '/profile',         icon: User,     label: 'Profile'   },
]

export function BottomTabBar() {
  return (
    <nav
      className="lg:hidden fixed inset-x-0 bottom-0 z-40 grid grid-cols-5"
      style={{
        background: 'rgba(10,10,15,0.95)',
        backdropFilter: 'blur(14px)',
        WebkitBackdropFilter: 'blur(14px)',
        borderTop: '1px solid var(--border)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        paddingLeft: 'env(safe-area-inset-left, 0px)',
        paddingRight: 'env(safe-area-inset-right, 0px)',
        minHeight: '64px',
      }}
    >
      {TABS.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) =>
            cn(
              'flex flex-col items-center justify-center gap-0.5 py-2 transition-colors',
              isActive ? 'opacity-100' : 'opacity-70'
            )
          }
          style={({ isActive }) => ({
            color: isActive ? 'var(--accent-gold)' : 'var(--text-muted)',
            textDecoration: 'none',
          })}
        >
          <Icon size={20} />
          <span className="text-[10px] font-semibold tracking-wide">{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}

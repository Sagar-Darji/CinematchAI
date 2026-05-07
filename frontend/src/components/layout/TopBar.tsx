import { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Clapperboard, Search } from 'lucide-react'
import { AvatarMenu } from './AvatarMenu'

export function TopBar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (location.pathname === '/search') {
      const params = new URLSearchParams(location.search)
      setQuery(params.get('q') ?? '')
    } else if (query) {
      setQuery('')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.search])

  const submit = (q: string) => {
    const trimmed = q.trim()
    if (!trimmed) return
    navigate(`/search?q=${encodeURIComponent(trimmed)}`)
  }

  return (
    <header
      className="sticky top-0 z-40 flex items-center gap-3 px-3 sm:px-5 h-14"
      style={{
        background: 'rgba(10,10,15,0.92)',
        backdropFilter: 'blur(14px)',
        WebkitBackdropFilter: 'blur(14px)',
        borderBottom: '1px solid var(--border)',
        paddingTop: 'env(safe-area-inset-top, 0px)',
        paddingLeft: 'max(env(safe-area-inset-left, 0px), 0.75rem)',
        paddingRight: 'max(env(safe-area-inset-right, 0px), 0.75rem)',
      }}
    >
      <Link to="/" className="flex items-center gap-2 flex-shrink-0">
        <Clapperboard size={20} style={{ color: 'var(--accent-gold)' }} />
        <span className="hidden sm:block font-bold text-sm tracking-wide" style={{ color: 'var(--accent-gold)' }}>
          CineMatch AI
        </span>
      </Link>

      <form
        onSubmit={(e) => { e.preventDefault(); submit(query) }}
        className="hidden md:flex items-center gap-2 rounded-xl px-3 py-1.5 flex-1 max-w-2xl mx-auto"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
      >
        <Search size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
        <input
          type="text"
          placeholder="Search movies & series…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 bg-transparent outline-none text-sm min-w-0"
          style={{ color: 'var(--text-primary)' }}
        />
      </form>

      <div className="flex-1 md:hidden" />

      <button
        onClick={() => navigate('/search')}
        className="md:hidden p-2 rounded-lg flex-shrink-0"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-muted)', cursor: 'pointer' }}
        aria-label="Search"
      >
        <Search size={16} />
      </button>

      <AvatarMenu />
    </header>
  )
}

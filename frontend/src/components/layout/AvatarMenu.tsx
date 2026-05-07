import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, User } from 'lucide-react'
import { useUserStore } from '@/store/useUserStore'
import { useRecommendationStore } from '@/store/useRecommendationStore'

export function AvatarMenu() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const { userId, logout } = useUserStore()
  const resetRecs = useRecommendationStore((s) => s.reset)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', handler)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', handler)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  if (!userId) {
    return (
      <button
        onClick={() => navigate('/login')}
        className="text-xs sm:text-sm font-bold px-3 py-1.5 rounded-lg flex-shrink-0"
        style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
      >
        Sign in
      </button>
    )
  }

  const handleLogout = () => {
    if (confirm('Are you sure you want to log out?')) {
      resetRecs()
      logout()
      setOpen(false)
      navigate('/login')
    }
  }

  return (
    <div ref={ref} className="relative flex-shrink-0">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Account menu"
        aria-expanded={open}
        className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-black"
        style={{ background: 'var(--accent-gold)', color: '#0a0a0f', border: 'none', cursor: 'pointer' }}
      >
        {userId[0]?.toUpperCase() ?? '?'}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 min-w-[200px] rounded-xl py-1.5 z-50"
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            boxShadow: '0 12px 32px rgba(0,0,0,0.5)',
          }}
        >
          <div className="px-3 py-2 border-b mb-1" style={{ borderColor: 'var(--border)' }}>
            <p className="text-sm font-bold text-white truncate">{userId}</p>
            <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Signed in</p>
          </div>
          <button
            onClick={() => { setOpen(false); navigate('/profile') }}
            className="w-full text-left px-3 py-2 text-sm flex items-center gap-2.5"
            style={{ color: 'var(--text-primary)', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            <User size={14} /> Profile
          </button>
          <button
            onClick={handleLogout}
            className="w-full text-left px-3 py-2 text-sm flex items-center gap-2.5"
            style={{ color: 'var(--accent-red)', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            <LogOut size={14} /> Log out
          </button>
        </div>
      )}
    </div>
  )
}

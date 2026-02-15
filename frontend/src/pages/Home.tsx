import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Sparkles, Search, ArrowRight } from 'lucide-react'
import { useUserStore } from '@/store/useUserStore'

export default function Home() {
  const { userId, setUserId, isOnboarded, setOnboarded } = useUserStore()
  const [inputId, setInputId] = useState(userId)

  const handleStart = () => {
    if (inputId.trim()) {
      setUserId(inputId.trim())
      setOnboarded(true)
    }
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center px-6 py-20 text-center">
        {/* Tagline — unveil.fr style: large, bold, uppercase */}
        <p className="text-xs font-bold tracking-[0.3em] uppercase mb-6" style={{ color: 'var(--accent-gold)' }}>
          AI-Powered Cinema Discovery
        </p>

        <h1
          className="text-5xl md:text-7xl font-black leading-none mb-6 tracking-tight"
          style={{ color: 'var(--text-primary)' }}
        >
          Find Your
          <br />
          <span style={{ color: 'var(--accent-gold)' }}>Next Film</span>
        </h1>

        <p className="text-lg max-w-lg mb-12" style={{ color: 'var(--text-muted)', lineHeight: 1.7 }}>
          A multi-agent AI pipeline analyzes your taste, mood, and context to surface
          exactly the right movie from 9,600+ titles across 20+ languages.
        </p>

        {!isOnboarded ? (
          <div className="flex flex-col sm:flex-row gap-3 w-full max-w-sm">
            <input
              type="text"
              placeholder="Enter your username"
              value={inputId}
              onChange={(e) => setInputId(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleStart()}
              className="flex-1 px-4 py-3 rounded-xl text-sm outline-none"
              style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                color: 'var(--text-primary)',
              }}
            />
            <button
              onClick={handleStart}
              disabled={!inputId.trim()}
              className="px-6 py-3 rounded-xl text-sm font-bold flex items-center gap-2 transition-opacity disabled:opacity-40"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}
            >
              Let's go <ArrowRight size={15} />
            </button>
          </div>
        ) : (
          <div className="flex flex-wrap justify-center gap-4">
            <Link
              to="/recommendations"
              className="flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm transition-opacity hover:opacity-80"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}
            >
              <Sparkles size={16} /> Get Recommendations
            </Link>
            <Link
              to="/browse"
              className="flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm transition-opacity hover:opacity-80"
              style={{ background: 'var(--bg-card)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
            >
              <Search size={16} /> Browse Movies
            </Link>
          </div>
        )}
      </section>

      {/* Feature grid */}
      <section
        className="grid grid-cols-1 md:grid-cols-3 gap-px border-t"
        style={{ borderColor: 'var(--border)', background: 'var(--border)' }}
      >
        {[
          {
            icon: '🧠',
            title: 'Multi-Agent Pipeline',
            body: 'Profile analysis, context detection, retrieval, content intelligence, and serendipity — all in one pass.',
          },
          {
            icon: '🌍',
            title: '20+ Languages',
            body: 'Hindi, Tamil, Korean, Japanese, French and more. Regional cinema is a first-class citizen.',
          },
          {
            icon: '✨',
            title: 'Serendipity Engine',
            body: 'MMR diversity ensures you discover gems outside your comfort zone, not just more of the same.',
          },
        ].map(({ icon, title, body }) => (
          <div
            key={title}
            className="p-8"
            style={{ background: 'var(--bg-card)' }}
          >
            <div className="text-3xl mb-3">{icon}</div>
            <h3 className="font-bold text-base mb-2 text-white">{title}</h3>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>{body}</p>
          </div>
        ))}
      </section>
    </div>
  )
}

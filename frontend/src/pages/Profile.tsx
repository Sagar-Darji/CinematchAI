import { useEffect, useState } from 'react'
import { User, Film, TrendingUp } from 'lucide-react'
import { useUserStore } from '@/store/useUserStore'
import { getUserProfile, type UserProfile } from '@/lib/api'

export default function Profile() {
  const { userId, ratingCount, setRatingCount } = useUserStore()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!userId) return
    setLoading(true)
    getUserProfile(userId).then((p) => {
      setProfile(p)
      if (p?.total_ratings) setRatingCount(p.total_ratings)
    }).finally(() => setLoading(false))
  }, [userId, setRatingCount])

  const genres = profile?.genres ?? {}
  const topGenres = Object.entries(genres).sort((a, b) => b[1] - a[1]).slice(0, 8)
  const maxCount = topGenres[0]?.[1] ?? 1

  return (
    <div className="p-6 md:p-8 min-h-screen">
      <h1 className="text-3xl font-black tracking-tight text-white mb-8">Profile</h1>

      {!userId ? (
        <div className="flex flex-col items-center py-20 text-center">
          <User size={48} style={{ color: 'var(--text-muted)' }} className="mb-4" />
          <p style={{ color: 'var(--text-muted)' }}>Enter a username on the Home page to get started.</p>
        </div>
      ) : (
        <div className="space-y-6 max-w-2xl">
          {/* User card */}
          <div
            className="rounded-xl p-6 flex items-center gap-5"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            <div
              className="w-14 h-14 rounded-full flex items-center justify-center text-xl font-black"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}
            >
              {userId[0]?.toUpperCase() ?? '?'}
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">{userId}</h2>
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                {loading ? 'Loading…' : `${profile?.total_ratings ?? ratingCount} ratings`}
              </p>
            </div>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { icon: Film, label: 'Ratings', value: profile?.total_ratings ?? ratingCount },
              { icon: TrendingUp, label: 'Genres', value: Object.keys(genres).length },
              { icon: User, label: 'Profile ready', value: profile?.embedding_ready ? 'Yes' : 'No' },
            ].map(({ icon: Icon, label, value }) => (
              <div
                key={label}
                className="rounded-xl p-4 flex flex-col items-center gap-1"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
              >
                <Icon size={18} style={{ color: 'var(--accent-gold)' }} />
                <span className="text-xl font-black text-white">{value}</span>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
              </div>
            ))}
          </div>

          {/* Genre breakdown */}
          {topGenres.length > 0 && (
            <div
              className="rounded-xl p-6"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
            >
              <h3 className="text-sm font-bold uppercase tracking-widest mb-4" style={{ color: 'var(--text-muted)' }}>
                Top Genres
              </h3>
              <div className="space-y-3">
                {topGenres.map(([genre, count]) => (
                  <div key={genre} className="flex items-center gap-3">
                    <span className="text-sm text-white font-medium w-28 flex-shrink-0">{genre}</span>
                    <div className="score-bar-track flex-1">
                      <div
                        className="score-bar-fill"
                        style={{
                          width: `${(count / maxCount) * 100}%`,
                          background: 'var(--accent-gold)',
                        }}
                      />
                    </div>
                    <span className="text-xs font-bold w-6 text-right" style={{ color: 'var(--accent-gold)' }}>
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!loading && !profile && (
            <div className="text-sm text-center py-8" style={{ color: 'var(--text-muted)' }}>
              No profile data yet. Rate some movies to build your taste profile.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

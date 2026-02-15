import { useEffect, useState } from 'react'
import { User, Film, Star, TrendingUp } from 'lucide-react'
import { useUserStore } from '@/store/useUserStore'
import { getUserProfile, getAdminProfile, type UserProfile, type AdminProfile } from '@/lib/api'
import { PageLoader } from '@/components/ui/PageLoader'

// ── Skeleton components ────────────────────────────────────────────────────────

function SkeletonProfile() {
  return (
    <div className="space-y-5">
      {/* Identity card skeleton */}
      <div className="rounded-xl p-5 flex items-center gap-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <div className="skeleton w-14 h-14 rounded-full flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="skeleton-text w-32" />
          <div className="skeleton-text w-20" style={{ opacity: 0.6 }} />
        </div>
      </div>

      {/* Stats row skeleton */}
      <div className="grid grid-cols-3 gap-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="rounded-xl p-4 flex flex-col items-center gap-2" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <div className="skeleton w-4 h-4 rounded" />
            <div className="skeleton-text w-10" />
            <div className="skeleton-text w-14" style={{ opacity: 0.5 }} />
          </div>
        ))}
      </div>

      {/* Genre bars skeleton */}
      <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <div className="skeleton-text w-24 mb-5" />
        <div className="space-y-3.5">
          {[90, 70, 55, 45, 35, 25].map((w, i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="skeleton-text w-24 flex-shrink-0" />
              <div className="skeleton flex-1 h-1.5 rounded-full" style={{ opacity: w / 100 }} />
              <div className="skeleton-text w-4 flex-shrink-0" />
            </div>
          ))}
        </div>
      </div>

      {/* Recent ratings skeleton */}
      <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <div className="skeleton-text w-28 mb-5" />
        <div className="space-y-3">
          {[80, 65, 72, 55, 68].map((w, i) => (
            <div key={i} className="flex items-center gap-3 py-1.5">
              <div className="flex-1 space-y-1.5">
                <div className="skeleton-text" style={{ width: `${w}%` }} />
                <div className="skeleton-text w-10" style={{ opacity: 0.5 }} />
              </div>
              <div className="skeleton w-8 h-5 rounded flex-shrink-0" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function Profile() {
  const { userId, ratingCount, setRatingCount } = useUserStore()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [admin, setAdmin] = useState<AdminProfile | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!userId) return
    setLoading(true)
    Promise.all([
      getUserProfile(userId),
      getAdminProfile(userId),
    ]).then(([p, a]) => {
      setProfile(p)
      setAdmin(a)
      const total = p?.total_ratings ?? a?.total_ratings
      if (total) setRatingCount(total)
    }).finally(() => setLoading(false))
  }, [userId, setRatingCount])

  const genres = profile?.genres ?? {}
  const topGenres = Object.entries(genres).sort((a, b) => b[1] - a[1]).slice(0, 8)
  const maxCount = topGenres[0]?.[1] ?? 1
  const totalRatings = profile?.total_ratings ?? admin?.total_ratings ?? ratingCount
  const avgRating = admin?.avg_rating_given

  return (
    <div className="p-5 md:p-8 min-h-screen max-w-2xl">
      <PageLoader visible={loading} />

      <h1 className="text-3xl font-black tracking-tight text-white mb-8">Profile</h1>

      {!userId ? (
        <div className="flex flex-col items-center py-20 text-center gap-4">
          <User size={48} style={{ color: 'var(--text-muted)' }} />
          <p style={{ color: 'var(--text-muted)' }}>Enter a username on the Home page to get started.</p>
        </div>
      ) : loading ? (
        <SkeletonProfile />
      ) : (
        <div className="space-y-5">
          {/* User identity card */}
          <div
            className="rounded-xl p-5 flex items-center gap-5 animate-fade-in"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            <div
              className="w-14 h-14 rounded-full flex items-center justify-center text-xl font-black flex-shrink-0"
              style={{ background: 'var(--accent-gold)', color: '#0a0a0f' }}
            >
              {userId[0]?.toUpperCase() ?? '?'}
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-bold text-white">{userId}</h2>
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{totalRatings} ratings</p>
            </div>
            {admin?.profile_status && (
              <span
                className="text-[10px] font-bold px-2 py-1 rounded-full flex-shrink-0"
                style={{
                  background: admin.profile_status === 'active' ? 'rgba(245,197,24,0.15)' : 'var(--bg-overlay)',
                  color: admin.profile_status === 'active' ? 'var(--accent-gold)' : 'var(--text-muted)',
                  border: '1px solid var(--border)',
                }}
              >
                {admin.profile_status}
              </span>
            )}
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { icon: Film, label: 'Ratings', value: totalRatings || '—' },
              { icon: Star, label: 'Avg Rating', value: avgRating ? avgRating.toFixed(1) : '—' },
              { icon: TrendingUp, label: 'Genres', value: Object.keys(genres).length || '—' },
            ].map(({ icon: Icon, label, value }, i) => (
              <div
                key={label}
                className="rounded-xl p-4 flex flex-col items-center gap-1 text-center animate-fade-in"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', animationDelay: `${i * 0.06}s` }}
              >
                <Icon size={16} style={{ color: 'var(--accent-gold)' }} />
                <span className="text-xl font-black text-white">{value}</span>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
              </div>
            ))}
          </div>

          {/* Genre breakdown */}
          {topGenres.length > 0 && (
            <div
              className="rounded-xl p-5 animate-fade-in"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', animationDelay: '0.12s' }}
            >
              <h3 className="text-xs font-bold uppercase tracking-widest mb-4" style={{ color: 'var(--text-muted)' }}>
                Top Genres
              </h3>
              <div className="space-y-2.5">
                {topGenres.map(([genre, count], i) => (
                  <div key={genre} className="flex items-center gap-3">
                    <span className="text-sm text-white font-medium w-28 flex-shrink-0 truncate">{genre}</span>
                    <div className="score-bar-track flex-1">
                      <div
                        className="score-bar-fill"
                        style={{
                          width: `${(count / maxCount) * 100}%`,
                          background: 'var(--accent-gold)',
                          transitionDelay: `${i * 0.05}s`,
                        }}
                      />
                    </div>
                    <span className="text-xs font-bold w-5 text-right flex-shrink-0" style={{ color: 'var(--accent-gold)' }}>
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent ratings */}
          {admin && admin.recent_ratings && admin.recent_ratings.length > 0 && (
            <div
              className="rounded-xl p-5 animate-fade-in"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', animationDelay: '0.18s' }}
            >
              <h3 className="text-xs font-bold uppercase tracking-widest mb-4" style={{ color: 'var(--text-muted)' }}>
                Recent Ratings
              </h3>
              <div className="space-y-2">
                {admin.recent_ratings.slice(0, 15).map((r, i) => (
                  <div key={i} className="flex items-center gap-3 py-1.5 border-b last:border-0" style={{ borderColor: 'var(--border)' }}>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white truncate">{r.title ?? `Movie #${r.movie_id}`}</p>
                      {r.year && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{r.year}</p>}
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <Star size={11} style={{ color: 'var(--accent-gold)' }} />
                      <span className="text-sm font-bold" style={{ color: 'var(--accent-gold)' }}>{r.rating}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!profile && !admin && (
            <div className="text-sm text-center py-8" style={{ color: 'var(--text-muted)' }}>
              No profile data yet. Rate some movies to build your taste profile.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

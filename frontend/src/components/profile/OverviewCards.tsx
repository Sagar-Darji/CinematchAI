/**
 * Overview tab content. Mobile-first card grid: single column on phone,
 * 2-column on tablet, 3-column on desktop for cards that fit. Each card
 * is self-contained — no shared state.
 *
 * Cards rendered (in order):
 *   1. Favorites strip (full width)
 *   2. Personality card (full width)
 *   3. Insight cards (auto-wrap)
 *   4. Top genres / Decades / People / Histogram (auto-grid)
 *
 * Pure render: all data comes from the precomputed `overview` payload.
 */
import { useState } from 'react'
import { Pencil, Sparkles, BarChart3, Film, Users2, Star } from 'lucide-react'
import type { FavoriteItem, ProfileOverview } from '@/lib/api'
import { PersonalityCard } from './PersonalityCard'
import { FavoritesEditor } from './FavoritesEditor'

interface Props {
  userId: string
  overview: ProfileOverview
  onFavoritesChange?: (items: FavoriteItem[]) => void
}

export function OverviewCards({ userId, overview, onFavoritesChange }: Props) {
  return (
    <div className="space-y-5">
      <FavoritesStripCard
        userId={userId}
        favorites={overview.favorites}
        onChange={onFavoritesChange}
      />
      <PersonalityCard personality={overview.personality} />
      {overview.insights.length > 0 && <InsightStrip insights={overview.insights} />}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {overview.top_genres.length > 0 && (
          <TopGenresCard genres={overview.top_genres.slice(0, 8)} />
        )}
        {overview.decades.length > 0 && (
          <DecadesCard decades={overview.decades} totalFilms={overview.totals.films} />
        )}
        {(overview.people.directors.length > 0 || overview.people.actors.length > 0) && (
          <PeopleCard directors={overview.people.directors.slice(0, 6)} actors={overview.people.actors.slice(0, 6)} />
        )}
        {overview.histogram.some((h) => h.count > 0) && (
          <HistogramCard histogram={overview.histogram} />
        )}
      </div>
    </div>
  )
}

// ── Favorites ────────────────────────────────────────────────────────

function FavoritesStripCard({
  userId,
  favorites,
  onChange,
}: {
  userId: string
  favorites: FavoriteItem[]
  onChange?: (items: FavoriteItem[]) => void
}) {
  const [editing, setEditing] = useState(false)
  const slots: (FavoriteItem | null)[] = [favorites[0] ?? null, favorites[1] ?? null, favorites[2] ?? null, favorites[3] ?? null]
  return (
    <section
      className="rounded-2xl p-5"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Star size={14} style={{ color: 'var(--accent-gold)' }} />
          <h2 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
            Favorites
          </h2>
        </div>
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="text-xs font-semibold inline-flex items-center gap-1"
          style={{ background: 'none', border: 'none', color: 'var(--accent-gold)', cursor: 'pointer' }}
        >
          <Pencil size={12} /> Edit
        </button>
      </div>
      <div className="grid grid-cols-4 gap-3">
        {slots.map((f, i) => (
          <div key={i} style={{ aspectRatio: '2/3', background: 'var(--bg-overlay)', borderRadius: '8px', overflow: 'hidden' }}>
            {f?.poster_path ? (
              <img
                src={`https://image.tmdb.org/t/p/w342${f.poster_path}`}
                alt={f.title}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-xs" style={{ color: 'var(--text-muted)' }}>
                Empty
              </div>
            )}
          </div>
        ))}
      </div>
      {editing && (
        <FavoritesEditor
          userId={userId}
          initial={favorites}
          onClose={() => setEditing(false)}
          onSaved={(items) => { onChange?.(items); setEditing(false) }}
        />
      )}
    </section>
  )
}

// ── Insight strip ────────────────────────────────────────────────────

function InsightStrip({ insights }: { insights: ProfileOverview['insights'] }) {
  return (
    <section
      className="rounded-2xl p-5"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={14} style={{ color: 'var(--accent-gold)' }} />
        <h2 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
          Cinephile insights
        </h2>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {insights.map((it, i) => (
          <div
            key={i}
            className="rounded-xl p-3"
            style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border)' }}
          >
            <p className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
              {it.title}
            </p>
            <p className="text-sm font-bold text-white mt-1 truncate" title={it.value}>{it.value}</p>
            {it.context && (
              <p className="text-[11px] mt-1" style={{ color: 'var(--text-muted)' }}>{it.context}</p>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

// ── Top genres ───────────────────────────────────────────────────────

function TopGenresCard({ genres }: { genres: Array<{ name: string; count: number }> }) {
  const total = genres.reduce((sum, g) => sum + g.count, 0) || 1
  const max = Math.max(...genres.map((g) => g.count))
  return (
    <CardShell title="Top genres" icon={<Film size={14} style={{ color: 'var(--accent-gold)' }} />}>
      <ul className="space-y-2">
        {genres.map((g) => {
          const pct = Math.round((g.count / total) * 100)
          const barPct = Math.round((g.count / max) * 100)
          return (
            <li key={g.name} className="flex items-center gap-3">
              <span className="text-sm text-white flex-1 truncate">{g.name}</span>
              <div style={{ flex: 2, height: 6, background: 'var(--bg-overlay)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ width: `${barPct}%`, height: '100%', background: 'var(--accent-gold)' }} />
              </div>
              <span className="text-xs tabular-nums w-12 text-right" style={{ color: 'var(--text-muted)' }}>
                {g.count} · {pct}%
              </span>
            </li>
          )
        })}
      </ul>
    </CardShell>
  )
}

// ── Decades ──────────────────────────────────────────────────────────

function DecadesCard({ decades, totalFilms }: { decades: ProfileOverview['decades']; totalFilms: number }) {
  const sumDecades = decades.reduce((s, d) => s + d.count, 0)
  const missing = Math.max(0, totalFilms - sumDecades)
  const max = Math.max(...decades.map((d) => d.count))
  const sorted = [...decades].sort((a, b) => a.decade - b.decade)
  return (
    <CardShell title="Decades" icon={<BarChart3 size={14} style={{ color: 'var(--accent-gold)' }} />}>
      <ul className="space-y-1.5">
        {sorted.map((d) => {
          const barPct = max > 0 ? Math.round((d.count / max) * 100) : 0
          return (
            <li key={d.decade} className="flex items-center gap-3">
              <span className="text-xs text-white w-12 tabular-nums">{d.label}</span>
              <div style={{ flex: 1, height: 6, background: 'var(--bg-overlay)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ width: `${barPct}%`, height: '100%', background: 'var(--accent-gold)' }} />
              </div>
              <span className="text-xs tabular-nums w-10 text-right" style={{ color: 'var(--text-muted)' }}>
                {d.count}
              </span>
            </li>
          )
        })}
      </ul>
      {missing > 0 && (
        <p className="text-[11px] mt-3 pt-3" style={{ color: 'var(--text-muted)', borderTop: '1px solid var(--border)' }}>
          {missing} {missing === 1 ? 'rating has' : 'ratings have'} no release year on TMDB.
        </p>
      )}
    </CardShell>
  )
}

// ── People ───────────────────────────────────────────────────────────

function PeopleCard({
  directors,
  actors,
}: {
  directors: ProfileOverview['people']['directors']
  actors:    ProfileOverview['people']['actors']
}) {
  return (
    <CardShell title="People" icon={<Users2 size={14} style={{ color: 'var(--accent-gold)' }} />}>
      {directors.length > 0 && (
        <>
          <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: 'var(--text-muted)' }}>Directors</p>
          <ul className="space-y-1 mb-3">
            {directors.map((d) => (
              <li key={d.name} className="flex justify-between text-sm">
                <span className="text-white truncate">{d.name}</span>
                <span style={{ color: 'var(--text-muted)' }}>
                  {d.count} {d.count === 1 ? 'film' : 'films'}
                  {d.avg_rating != null && (
                    <> · <span style={{ color: 'var(--accent-gold)' }}>{d.avg_rating}★</span></>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      {actors.length > 0 && (
        <>
          <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: 'var(--text-muted)' }}>Actors</p>
          <ul className="space-y-1">
            {actors.map((a) => (
              <li key={a.name} className="flex justify-between text-sm">
                <span className="text-white truncate">{a.name}</span>
                <span style={{ color: 'var(--text-muted)' }}>{a.count}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </CardShell>
  )
}

// ── Histogram ────────────────────────────────────────────────────────

function HistogramCard({ histogram }: { histogram: ProfileOverview['histogram'] }) {
  const max = Math.max(1, ...histogram.map((b) => b.count))
  return (
    <CardShell title="Rating distribution" icon={<Star size={14} style={{ color: 'var(--accent-gold)' }} />}>
      <div className="flex items-end gap-1" style={{ height: 100 }}>
        {histogram.map((b) => {
          const pct = Math.round((b.count / max) * 100)
          return (
            <div key={b.rating} className="flex-1 flex flex-col items-center justify-end" title={`${b.rating}★ — ${b.count}`}>
              <div
                style={{
                  width: '100%',
                  height: `${Math.max(4, pct)}%`,
                  background: 'var(--accent-gold)',
                  opacity: pct === 0 ? 0.18 : 1,
                  borderRadius: '3px 3px 0 0',
                }}
              />
              <span className="text-[9px] mt-1" style={{ color: 'var(--text-muted)' }}>{b.rating}</span>
            </div>
          )
        })}
      </div>
    </CardShell>
  )
}

// ── Shared shell ─────────────────────────────────────────────────────

function CardShell({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section
      className="rounded-2xl p-5"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h2 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
          {title}
        </h2>
      </div>
      {children}
    </section>
  )
}

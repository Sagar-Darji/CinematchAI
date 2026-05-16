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
import { Pencil, Sparkles, BarChart3, Film, User as UserIcon, Star } from 'lucide-react'
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
        {overview.histogram.some((h) => h.count > 0) && (
          <HistogramCard histogram={overview.histogram} />
        )}
      </div>
      {(overview.people.directors.length > 0 || overview.people.actors.length > 0) && (
        <PeoplePanels people={overview.people} />
      )}
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
// Side-by-side Top Directors + Top Actors panels with a shared language
// toggle. When the backend ships `directors_by_language` / `actors_by_language`
// we surface a small "All / Hindi / English …" chip strip; otherwise the
// strip is hidden and we render the global aggregate.

type PeopleData = ProfileOverview['people']

// ISO-639-1 → display name. Keep the common ones a Letterboxd user is
// likely to have in their library; anything missing falls back to the raw
// code uppercased (still readable).
const LANG_LABELS: Record<string, string> = {
  en: 'English',
  hi: 'Hindi',
  ta: 'Tamil',
  te: 'Telugu',
  ml: 'Malayalam',
  kn: 'Kannada',
  bn: 'Bengali',
  ko: 'Korean',
  ja: 'Japanese',
  zh: 'Chinese',
  fr: 'French',
  es: 'Spanish',
  de: 'German',
  it: 'Italian',
  ru: 'Russian',
}

function langLabel(code: string): string {
  return LANG_LABELS[code] ?? code.toUpperCase()
}

function PeoplePanels({ people }: { people: PeopleData }) {
  // Only surface the toggle when there's actually >1 language to switch
  // between AND the backend shipped the per-language buckets.
  const langs = (people.languages ?? []).filter(
    (l) =>
      (people.directors_by_language?.[l]?.length ?? 0) > 0 ||
      (people.actors_by_language?.[l]?.length ?? 0) > 0,
  )
  const showToggle = langs.length >= 2
  const [lang, setLang] = useState<string>('all')

  const directors = lang === 'all'
    ? people.directors.slice(0, 8)
    : (people.directors_by_language?.[lang] ?? []).slice(0, 8)
  const actors = lang === 'all'
    ? people.actors.slice(0, 8)
    : (people.actors_by_language?.[lang] ?? []).slice(0, 8)

  return (
    <div className="space-y-3">
      {showToggle && (
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="text-[10px] uppercase tracking-widest mr-1"
            style={{ color: 'var(--text-muted)' }}
          >
            People
          </span>
          <LangChip label="All" active={lang === 'all'} onClick={() => setLang('all')} />
          {langs.map((l) => (
            <LangChip
              key={l}
              label={langLabel(l)}
              active={lang === l}
              onClick={() => setLang(l)}
            />
          ))}
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {directors.length > 0 && (
          <PeoplePanel
            icon={Film}
            title="Top directors"
            rows={directors.map((d, i) => ({
              rank:  i + 1,
              name:  d.name,
              count: d.count,
              sub:   d.avg_rating != null ? `${d.avg_rating}★` : undefined,
            }))}
          />
        )}
        {actors.length > 0 && (
          <PeoplePanel
            icon={UserIcon}
            title="Top actors"
            rows={actors.map((a, i) => ({
              rank:  i + 1,
              name:  a.name,
              count: a.count,
            }))}
          />
        )}
      </div>
    </div>
  )
}

function LangChip({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-xs font-semibold rounded-full px-3 py-1 transition-colors"
      style={{
        background: active ? 'var(--accent-gold)' : 'var(--bg-overlay)',
        color:      active ? 'var(--bg-page)'    : 'var(--text-muted)',
        border:     '1px solid var(--border)',
        cursor:     'pointer',
      }}
    >
      {label}
    </button>
  )
}

function PeoplePanel({
  icon: Icon,
  title,
  rows,
}: {
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>
  title: string
  rows: Array<{ rank: number; name: string; count: number; sub?: string }>
}) {
  const max = Math.max(1, ...rows.map((r) => r.count))
  return (
    <CardShell title={title} icon={<Icon size={14} style={{ color: 'var(--accent-gold)' }} />}>
      <div className="space-y-2.5">
        {rows.map((r) => (
          <div key={r.name} className="flex items-center gap-3 min-w-0">
            <span
              className="text-[10px] font-black w-4 text-right flex-shrink-0"
              style={{ color: 'var(--text-muted)' }}
            >
              {r.rank}
            </span>
            <span className="text-sm text-white font-semibold truncate flex-1 min-w-0">
              {r.name}
            </span>
            <div className="flex items-center gap-2 flex-shrink-0">
              <div
                className="rounded-full"
                style={{
                  width:  `${Math.max(8, (r.count / max) * 64)}px`,
                  height: '4px',
                  background: 'var(--accent-gold)',
                  opacity: 0.7,
                }}
              />
              <span
                className="text-xs font-bold w-5 text-right tabular-nums"
                style={{ color: 'var(--accent-gold)' }}
              >
                {r.count}
              </span>
              {r.sub && (
                <span
                  className="text-[10px] font-semibold w-10 text-right"
                  style={{ color: 'var(--text-muted)' }}
                >
                  {r.sub}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
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

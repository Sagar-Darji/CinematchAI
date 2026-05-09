import type { Season } from '@/lib/api'

export interface EpisodeRef {
  season: number
  episode: number
}

/** Seasons the player can actually navigate — drops "Specials" (season 0)
 * and any season with a 0/missing episode_count. */
export function getPlayableSeasons(seasons?: Season[]): Season[] {
  return (seasons ?? []).filter((s) => (s.episode_count ?? 0) > 0)
}

/** First playable season number, preferring season 1+ over Specials. */
export function getDefaultSeasonNumber(seasons?: Season[]): number {
  const playable = getPlayableSeasons(seasons)
  const preferred = playable.find((s) => s.season_number > 0) ?? playable[0]
  return preferred?.season_number ?? 1
}

/** Find the next episode after the current one, rolling over to the next
 * season when needed. Returns null at the end of the show. */
export function getNextEpisode(
  seasons: Season[] | undefined,
  current: EpisodeRef,
): EpisodeRef | null {
  const playable = getPlayableSeasons(seasons)
  if (playable.length === 0) return null

  const idx = playable.findIndex((s) => s.season_number === current.season)
  if (idx < 0) return null

  const season = playable[idx]
  const epCount = Math.max(season.episode_count ?? 1, 1)

  if (current.episode < epCount) {
    return { season: current.season, episode: current.episode + 1 }
  }

  const next = playable[idx + 1]
  if (!next) return null
  return { season: next.season_number, episode: 1 }
}

/** Find the previous episode, rolling back to the prior season's last episode
 * when at episode 1. Returns null at the very start. */
export function getPrevEpisode(
  seasons: Season[] | undefined,
  current: EpisodeRef,
): EpisodeRef | null {
  const playable = getPlayableSeasons(seasons)
  if (playable.length === 0) return null

  const idx = playable.findIndex((s) => s.season_number === current.season)
  if (idx < 0) return null

  if (current.episode > 1) {
    return { season: current.season, episode: current.episode - 1 }
  }

  const prev = playable[idx - 1]
  if (!prev) return null
  const prevCount = Math.max(prev.episode_count ?? 1, 1)
  return { season: prev.season_number, episode: prevCount }
}

/**
 * Rotates through the 4 caption types from ProfileIdentity.captions every
 * ~12 seconds. Data is precomputed in the backend; this component only
 * does the rendering + timer.
 *
 * Skips the rotation when there's 0 or 1 caption (nothing to rotate).
 * Pauses while hidden (visibilitychange) so we don't burn timers in
 * background tabs.
 */
import { useEffect, useState } from 'react'
import type { ProfileCaption } from '@/lib/api'

const ROTATE_MS = 12_000

export function CaptionRotator({ captions }: { captions: ProfileCaption[] }) {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (captions.length <= 1) return
    let timer: ReturnType<typeof setTimeout> | null = null
    let paused = false

    const tick = () => {
      if (paused) return
      setIndex((i) => (i + 1) % captions.length)
      timer = setTimeout(tick, ROTATE_MS)
    }
    timer = setTimeout(tick, ROTATE_MS)

    const onVisibility = () => {
      paused = document.hidden
      if (!paused && !timer) timer = setTimeout(tick, ROTATE_MS)
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      if (timer) clearTimeout(timer)
    }
  }, [captions.length])

  if (!captions.length) return null
  const caption = captions[index]
  return (
    <p
      key={caption.text}
      className="text-sm animate-fade-in"
      style={{ color: 'var(--text-muted)' }}
    >
      {caption.text}
    </p>
  )
}

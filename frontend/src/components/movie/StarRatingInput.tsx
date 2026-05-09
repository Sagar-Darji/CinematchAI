import { useState } from 'react'
import { Star } from 'lucide-react'

interface Props {
  value: number | null
  onChange: (value: number | null) => void
  size?: number
  ariaLabel?: string
}

/**
 * Half-star rating input. 5 stars rendered, each split into two click zones
 * (left = N.5, right = N+1.0). Hovering previews the rating; mouseleave
 * snaps back to the committed value. Click toggles off if the user clicks
 * the value they already had selected.
 */
export function StarRatingInput({ value, onChange, size = 24, ariaLabel = 'Rate' }: Props) {
  const [hover, setHover] = useState<number | null>(null)
  const display = hover ?? value ?? 0

  const setRating = (next: number) => {
    if (value === next) {
      // Click the current value to clear.
      onChange(null)
    } else {
      onChange(next)
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      onChange(Math.max(0.5, (value ?? 3) - 0.5))
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      onChange(Math.min(5, (value ?? 0) + 0.5))
    } else if (e.key === 'Backspace' || e.key === 'Delete') {
      e.preventDefault()
      onChange(null)
    }
  }

  return (
    <div
      className="inline-flex items-center gap-0.5"
      role="slider"
      aria-label={ariaLabel}
      aria-valuemin={0}
      aria-valuemax={5}
      aria-valuenow={value ?? 0}
      tabIndex={0}
      onKeyDown={handleKey}
      onMouseLeave={() => setHover(null)}
      style={{ outline: 'none' }}
    >
      {[1, 2, 3, 4, 5].map((slot) => {
        const fillPct = Math.max(0, Math.min(1, display - (slot - 1))) * 100
        return (
          <span
            key={slot}
            className="relative inline-block"
            style={{ width: size, height: size, lineHeight: 0 }}
          >
            {/* Empty/outline star — sits behind the fill */}
            <Star
              size={size}
              style={{ color: 'rgba(255,255,255,0.18)', position: 'absolute', inset: 0 }}
            />
            {/* Filled star clipped to the fillPct */}
            <span
              style={{
                position: 'absolute',
                inset: 0,
                width: `${fillPct}%`,
                overflow: 'hidden',
                pointerEvents: 'none',
              }}
            >
              <Star
                size={size}
                fill="currentColor"
                style={{ color: 'var(--accent-gold)' }}
              />
            </span>
            {/* Two click zones: left half = .5, right half = 1.0 */}
            <button
              type="button"
              aria-label={`${slot - 0.5} stars`}
              onMouseEnter={() => setHover(slot - 0.5)}
              onClick={() => setRating(slot - 0.5)}
              style={{
                position: 'absolute',
                left: 0,
                top: 0,
                width: '50%',
                height: '100%',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
              }}
            />
            <button
              type="button"
              aria-label={`${slot} stars`}
              onMouseEnter={() => setHover(slot)}
              onClick={() => setRating(slot)}
              style={{
                position: 'absolute',
                left: '50%',
                top: 0,
                width: '50%',
                height: '100%',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
              }}
            />
          </span>
        )
      })}
    </div>
  )
}

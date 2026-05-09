import { useEffect, useRef, useState } from 'react'
import { Loader2, Check, Trash2, AlertCircle } from 'lucide-react'
import { deleteReview, getMyReview, upsertReview, type MediaType } from '@/lib/api'
import { useReviewsStore } from '@/store/useReviewsStore'
import { StarRatingInput } from './StarRatingInput'

type Status = 'idle' | 'saving' | 'saved' | 'error'

interface Props {
  tmdbId: number
  mediaType: MediaType
}

/**
 * In-place review editor: half-star input + textarea + auto-save on blur.
 * Status indicator shows saving / saved / error. Delete button removes the
 * row entirely. Hydrates from useReviewsStore first, falls back to a single
 * GET if the store hasn't been hydrated yet.
 */
export function ReviewEditor({ tmdbId, mediaType }: Props) {
  const cached = useReviewsStore((s) => s.byKey[`${tmdbId}-${mediaType}`])
  const upsertLocal = useReviewsStore((s) => s.upsertLocal)
  const removeLocal = useReviewsStore((s) => s.removeLocal)

  const [rating, setRating] = useState<number | null>(cached?.rating ?? null)
  const [text, setText] = useState<string>(cached?.review_text ?? '')
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string>('')
  const [loaded, setLoaded] = useState<boolean>(!!cached)
  const lastSaved = useRef<{ rating: number | null; text: string }>({
    rating: cached?.rating ?? null,
    text: cached?.review_text ?? '',
  })

  // Initial fetch when the store didn't have it.
  useEffect(() => {
    if (cached) return
    let cancelled = false
    getMyReview(tmdbId, mediaType)
      .then((r) => {
        if (cancelled) return
        if (r) {
          setRating(r.rating ?? null)
          setText(r.review_text ?? '')
          lastSaved.current = { rating: r.rating ?? null, text: r.review_text ?? '' }
          upsertLocal(r)
        }
      })
      .finally(() => {
        if (!cancelled) setLoaded(true)
      })
    return () => { cancelled = true }
  }, [tmdbId, mediaType, cached, upsertLocal])

  const dirty = rating !== lastSaved.current.rating || text !== lastSaved.current.text
  const hasContent = rating !== null || text.trim().length > 0
  const hasSaved = lastSaved.current.rating !== null || lastSaved.current.text.trim().length > 0

  const save = async () => {
    if (!dirty) return
    if (!hasContent) {
      // Both fields empty — treat as a delete if there was a previous review.
      if (hasSaved) {
        await handleDelete()
      }
      return
    }
    setStatus('saving')
    setError('')
    try {
      const saved = await upsertReview({
        tmdbId,
        mediaType,
        rating,
        reviewText: text.trim() || null,
      })
      lastSaved.current = { rating: saved.rating ?? null, text: saved.review_text ?? '' }
      upsertLocal(saved)
      setStatus('saved')
      // Drop the saved indicator after a moment
      setTimeout(() => setStatus((s) => (s === 'saved' ? 'idle' : s)), 1800)
    } catch (e) {
      setStatus('error')
      setError(e instanceof Error ? e.message : 'Save failed')
    }
  }

  const handleDelete = async () => {
    if (!hasSaved) return
    setStatus('saving')
    setError('')
    try {
      await deleteReview(tmdbId, mediaType)
      removeLocal(tmdbId, mediaType)
      setRating(null)
      setText('')
      lastSaved.current = { rating: null, text: '' }
      setStatus('idle')
    } catch (e) {
      setStatus('error')
      setError(e instanceof Error ? e.message : 'Delete failed')
    }
  }

  // When the rating changes (one click — easy to lose), persist eagerly so a
  // refresh doesn't lose work. The textarea uses onBlur to avoid spamming.
  useEffect(() => {
    if (!loaded) return
    if (rating === lastSaved.current.rating) return
    save()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rating])

  return (
    <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[10px] md:text-xs font-bold uppercase tracking-[0.2em]"
          style={{ color: 'var(--accent-gold)' }}>
          Your review
        </h3>
        <StatusBadge status={status} dirty={dirty} hasSaved={hasSaved} />
      </div>

      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <StarRatingInput value={rating} onChange={setRating} size={26} ariaLabel="Your rating" />
        {rating !== null && (
          <span className="text-sm font-bold" style={{ color: 'var(--accent-gold)' }}>
            {rating.toFixed(1)} / 5
          </span>
        )}
        {rating === null && (
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Tap stars to rate
          </span>
        )}
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={save}
        placeholder="What did you think? (optional)"
        rows={3}
        maxLength={5000}
        className="w-full text-sm rounded-lg outline-none resize-y"
        style={{
          padding: '10px 12px',
          background: 'var(--bg-overlay)',
          border: '1px solid var(--border)',
          color: 'white',
          minHeight: '72px',
        }}
      />

      <div className="flex items-center justify-between mt-2">
        <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
          {text.length > 0 ? `${text.length}/5000` : ''}
        </span>
        {hasSaved && (
          <button
            onClick={handleDelete}
            className="flex items-center gap-1 text-[11px] font-semibold"
            style={{ color: 'var(--accent-red)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            <Trash2 size={11} /> Delete
          </button>
        )}
      </div>

      {error && (
        <p className="text-xs mt-2 flex items-center gap-1" style={{ color: 'var(--accent-red)' }}>
          <AlertCircle size={11} /> {error}
        </p>
      )}
    </div>
  )
}

function StatusBadge({ status, dirty, hasSaved }: { status: Status; dirty: boolean; hasSaved: boolean }) {
  if (status === 'saving') {
    return (
      <span className="flex items-center gap-1 text-[11px]" style={{ color: 'var(--text-muted)' }}>
        <Loader2 size={11} className="animate-spin" /> Saving…
      </span>
    )
  }
  if (status === 'saved') {
    return (
      <span className="flex items-center gap-1 text-[11px]" style={{ color: 'var(--accent-gold)' }}>
        <Check size={11} /> Saved
      </span>
    )
  }
  if (dirty) {
    return (
      <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
        Unsaved
      </span>
    )
  }
  if (hasSaved) {
    return (
      <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
        Saved
      </span>
    )
  }
  return null
}

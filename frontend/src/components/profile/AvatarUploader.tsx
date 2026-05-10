import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Upload, Loader2, Trash2, Check } from 'lucide-react'
import { uploadAvatar, deleteAvatar } from '@/lib/api'

interface Props {
  userId: string
  currentUrl?: string | null
  onClose: () => void
  onSaved: (url: string | null) => void
}

const MAX_BYTES = 5 * 1024 * 1024
const TARGET_PREVIEW = 256

/**
 * Modal: pick an image from disk, preview a center-cropped square at the
 * target size, upload (server resizes + persists in S3), refresh the
 * profile's avatar URL. Also supports deleting the existing avatar.
 */
export function AvatarUploader({ userId, currentUrl, onClose, onSaved }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
    }
  }, [onClose])

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null
    setError('')
    if (!f) return
    if (!f.type.startsWith('image/')) {
      setError('Please pick an image file.')
      return
    }
    if (f.size > MAX_BYTES) {
      setError('File is bigger than 5 MB.')
      return
    }
    setFile(f)
    if (preview) URL.revokeObjectURL(preview)
    setPreview(URL.createObjectURL(f))
  }

  const handleUpload = async () => {
    if (!file) return
    setSubmitting(true)
    setError('')
    try {
      const url = await uploadAvatar(userId, file)
      onSaved(url)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    setSubmitting(true)
    setError('')
    try {
      await deleteAvatar(userId)
      onSaved(null)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setSubmitting(false)
    }
  }

  const content = (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{
        background: 'rgba(0,0,0,0.85)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
      }}
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div
        className="relative w-full max-w-sm rounded-2xl animate-fade-in shadow-2xl overflow-hidden"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border-hover)' }}
      >
        <div className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: '1px solid var(--border)' }}>
          <h2 className="text-base font-bold text-white">Profile picture</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-8 h-8 flex items-center justify-center rounded-full"
            style={{ background: 'rgba(255,255,255,0.08)', color: 'white', border: 'none', cursor: 'pointer' }}
          >
            <X size={16} />
          </button>
        </div>

        <div className="px-5 py-5 flex flex-col items-center gap-4">
          {/* Preview */}
          <div
            className="rounded-full overflow-hidden flex items-center justify-center"
            style={{
              width: TARGET_PREVIEW,
              height: TARGET_PREVIEW,
              background: 'var(--bg-overlay)',
              border: '2px solid var(--border)',
              maxWidth: '100%',
              maxHeight: '40vh',
              aspectRatio: '1 / 1',
            }}
          >
            {preview ? (
              <img src={preview} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            ) : currentUrl ? (
              <img src={currentUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            ) : (
              <span className="text-sm" style={{ color: 'var(--text-muted)' }}>No picture yet</span>
            )}
          </div>

          {/* File picker */}
          <label
            className="w-full flex items-center justify-center gap-2 rounded-xl py-3 cursor-pointer text-sm font-bold"
            style={{
              background: 'var(--bg-overlay)',
              border: '1px dashed var(--border)',
              color: 'var(--text-primary)',
            }}
          >
            <Upload size={14} />
            {file ? file.name.slice(0, 28) : 'Choose image…'}
            <input
              type="file"
              accept="image/*"
              onChange={handleFile}
              className="hidden"
            />
          </label>

          {error && (
            <p className="text-xs" style={{ color: 'var(--accent-red)' }}>{error}</p>
          )}

          <p className="text-[11px] text-center" style={{ color: 'var(--text-muted)' }}>
            We center-crop and resize to 256×256 — keep the subject centered.
          </p>
        </div>

        <div className="px-5 py-4 flex items-center justify-between gap-3"
          style={{ borderTop: '1px solid var(--border)' }}>
          {currentUrl ? (
            <button
              onClick={handleDelete}
              disabled={submitting}
              className="flex items-center gap-1 text-xs font-semibold"
              style={{
                color: 'var(--accent-red)',
                background: 'none',
                border: 'none',
                cursor: submitting ? 'wait' : 'pointer',
                padding: 0,
              }}
            >
              <Trash2 size={12} /> Remove
            </button>
          ) : <span />}
          <button
            onClick={handleUpload}
            disabled={!file || submitting}
            className="flex items-center gap-2 text-sm font-bold"
            style={{
              padding: '9px 18px',
              borderRadius: '10px',
              background: 'var(--accent-gold)',
              color: '#0a0a0f',
              border: 'none',
              cursor: !file || submitting ? 'not-allowed' : 'pointer',
              opacity: !file || submitting ? 0.6 : 1,
            }}
          >
            {submitting ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
            Save
          </button>
        </div>
      </div>
    </div>
  )

  return createPortal(content, document.body)
}

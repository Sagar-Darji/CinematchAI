/**
 * PageLoader — thin gold bar at the very top of the content area.
 * Two modes:
 *   indeterminate (default): bouncing animation, used when progress unknown
 *   determinate: fills to `value` % (0-100), used when we know progress
 *
 * Usage:
 *   <PageLoader visible={loading} />
 *   <PageLoader visible={running} value={stepsCompleted / totalSteps * 100} />
 */

interface PageLoaderProps {
  visible: boolean
  /** 0–100. If omitted, runs indeterminate bounce animation. */
  value?: number
}

export function PageLoader({ visible, value }: PageLoaderProps) {
  if (!visible) return null

  const isDeterminate = value !== undefined

  return (
    <div
      className="top-loader-track"
      aria-hidden="true"
    >
      {isDeterminate ? (
        <div
          className="top-loader-fill"
          style={{ width: `${Math.min(100, Math.max(0, value!))}%`, transition: 'width 0.4s ease' }}
        />
      ) : (
        <>
          <div className="top-loader-bar1" />
          <div className="top-loader-bar2" />
        </>
      )}
    </div>
  )
}

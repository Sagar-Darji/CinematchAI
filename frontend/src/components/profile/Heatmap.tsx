import { useMemo } from 'react'

interface Props {
  /** ISO date string → count, e.g. { "2026-05-08": 3 } */
  counts: Record<string, number>
  year: number
}

/** GitHub-style heatmap: 7 rows (Sun→Sat) x ~53 columns (weeks). Each cell
 * is one calendar day in `year`, shaded by the watch count for that day.
 *
 * The grid is rendered in CSS — no SVG — so it scales fluidly and tooltips
 * use the native browser title attribute. */
export function Heatmap({ counts, year }: Props) {
  const cells = useMemo(() => buildYearGrid(year, counts), [year, counts])
  const max = useMemo(() => Math.max(1, ...Object.values(counts)), [counts])

  // Build month label positions (top-of-column for the first day of each month)
  const monthLabels = useMemo(() => {
    const labels: { col: number; label: string }[] = []
    let lastMonth = -1
    for (let col = 0; col < cells[0].length; col++) {
      // Pick the first non-empty cell in this column to determine month
      for (let row = 0; row < 7; row++) {
        const c = cells[row][col]
        if (c && c.month !== lastMonth) {
          labels.push({ col, label: MONTH_NAMES[c.month] })
          lastMonth = c.month
          break
        }
      }
    }
    return labels
  }, [cells])

  const totalWatches = Object.values(counts).reduce((a, b) => a + b, 0)
  const activeDays = Object.keys(counts).length

  return (
    <div>
      <div className="flex items-baseline justify-between mb-3">
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          <span className="font-bold text-white">{totalWatches}</span> watches in <span className="font-bold text-white">{activeDays}</span> active {activeDays === 1 ? 'day' : 'days'}
        </p>
        <Legend />
      </div>

      <div className="overflow-x-auto hide-scrollbar">
        <div style={{ minWidth: 'max-content' }}>
          {/* Month labels row */}
          <div className="flex" style={{ gap: '2px', paddingLeft: '20px', marginBottom: '4px', height: '12px' }}>
            {cells[0].map((_, col) => {
              const label = monthLabels.find((l) => l.col === col)
              return (
                <div key={col} className="text-[9px] font-semibold" style={{ width: '11px', color: 'var(--text-muted)' }}>
                  {label?.label ?? ''}
                </div>
              )
            })}
          </div>

          {/* 7 rows for Sun…Sat */}
          {cells.map((row, rowIdx) => (
            <div key={rowIdx} className="flex" style={{ gap: '2px', height: '11px', marginBottom: '2px' }}>
              <div className="text-[9px] font-semibold flex items-center" style={{ width: '18px', color: 'var(--text-muted)' }}>
                {[1, 3, 5].includes(rowIdx) ? DAY_NAMES[rowIdx] : ''}
              </div>
              {row.map((c, colIdx) => {
                if (!c) return <div key={colIdx} style={{ width: '11px', height: '11px' }} />
                const intensity = c.count === 0 ? 0 : Math.min(4, Math.ceil((c.count / max) * 4))
                return (
                  <div
                    key={colIdx}
                    title={`${c.iso}: ${c.count} ${c.count === 1 ? 'watch' : 'watches'}`}
                    style={{
                      width: '11px',
                      height: '11px',
                      borderRadius: '2px',
                      background: HEAT_COLORS[intensity],
                      border: intensity === 0 ? '1px solid var(--border)' : 'none',
                    }}
                  />
                )
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Legend() {
  return (
    <div className="flex items-center gap-1.5 text-[10px]" style={{ color: 'var(--text-muted)' }}>
      <span>Less</span>
      {HEAT_COLORS.map((color, i) => (
        <div key={i} style={{ width: '11px', height: '11px', borderRadius: '2px', background: color, border: i === 0 ? '1px solid var(--border)' : 'none' }} />
      ))}
      <span>More</span>
    </div>
  )
}

interface Cell {
  iso: string
  month: number
  count: number
}

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const HEAT_COLORS = [
  'transparent',                  // 0 — empty
  'rgba(245,197,24,0.22)',        // 1
  'rgba(245,197,24,0.45)',        // 2
  'rgba(245,197,24,0.72)',        // 3
  'rgba(245,197,24,1)',           // 4
]

/** Build a 7×N grid where each column is one calendar week. Rows are days
 * (Sun=0…Sat=6). Empty slots before Jan-1 / after Dec-31 are null. */
function buildYearGrid(year: number, counts: Record<string, number>): (Cell | null)[][] {
  const start = new Date(`${year}-01-01T00:00:00Z`)
  const end = new Date(`${year}-12-31T00:00:00Z`)
  // Number of weeks (columns) needed
  const startCol = 0
  // Calculate total cells to determine grid width
  const rows: (Cell | null)[][] = Array.from({ length: 7 }, () => [])

  // Pad the first column with nulls before Jan-1
  const startDow = start.getUTCDay()
  for (let r = 0; r < startDow; r++) rows[r].push(null)

  const cur = new Date(start)
  while (cur <= end) {
    const dow = cur.getUTCDay()
    const iso = cur.toISOString().slice(0, 10)
    rows[dow].push({
      iso,
      month: cur.getUTCMonth(),
      count: counts[iso] ?? 0,
    })
    cur.setUTCDate(cur.getUTCDate() + 1)
    // When we wrap past Saturday, pad earlier rows that haven't gotten a cell yet
    if (cur.getUTCDay() === 0) {
      const maxLen = Math.max(...rows.map((r) => r.length))
      for (let r = 0; r < 7; r++) {
        while (rows[r].length < maxLen) rows[r].push(null)
      }
    }
  }
  // Pad the trailing column after Dec-31
  const maxLen = Math.max(...rows.map((r) => r.length))
  for (let r = 0; r < 7; r++) {
    while (rows[r].length < maxLen) rows[r].push(null)
  }
  // Suppress unused-variable warning while keeping the parameter for future use.
  void startCol
  return rows
}

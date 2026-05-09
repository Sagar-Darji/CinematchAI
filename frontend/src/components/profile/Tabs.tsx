interface TabsProps<T extends string> {
  active: T
  options: { value: T; label: string; count?: number }[]
  onChange: (value: T) => void
}

export function Tabs<T extends string>({ active, options, onChange }: TabsProps<T>) {
  return (
    <div
      className="flex gap-1 overflow-x-auto hide-scrollbar"
      role="tablist"
      style={{
        borderBottom: '1px solid var(--border)',
        marginBottom: '1rem',
      }}
    >
      {options.map((opt) => {
        const isActive = opt.value === active
        return (
          <button
            key={opt.value}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(opt.value)}
            className="flex items-center gap-1.5 text-sm font-bold whitespace-nowrap"
            style={{
              padding: '10px 14px',
              background: 'none',
              border: 'none',
              borderBottom: isActive ? '2px solid var(--accent-gold)' : '2px solid transparent',
              color: isActive ? '#fff' : 'var(--text-muted)',
              cursor: 'pointer',
              marginBottom: '-1px',
            }}
          >
            {opt.label}
            {typeof opt.count === 'number' && opt.count > 0 && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded-full font-bold"
                style={{
                  background: isActive ? 'rgba(245,197,24,0.18)' : 'var(--bg-overlay)',
                  color: isActive ? 'var(--accent-gold)' : 'var(--text-muted)',
                  border: '1px solid var(--border)',
                }}
              >
                {opt.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

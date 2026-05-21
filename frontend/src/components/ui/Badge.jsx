const VARIANTS = {
  default: { background: 'var(--bg-high)', color: 'var(--text-muted)' },
  violet:  { background: 'var(--violet-soft)', color: 'var(--violet)' },
  green:   { background: 'var(--green-soft)', color: 'var(--green)' },
  red:     { background: 'var(--red-soft)', color: 'var(--red)' },
  amber:   { background: 'var(--amber-soft)', color: 'var(--amber)' },
}

export default function Badge({ children, variant = 'default' }) {
  const { background, color } = VARIANTS[variant] || VARIANTS.default
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 7px',
        borderRadius: 4,
        fontSize: 12,
        fontFamily: 'DM Mono, monospace',
        fontWeight: 400,
        background,
        color,
        letterSpacing: '0.02em',
      }}
    >
      {children}
    </span>
  )
}

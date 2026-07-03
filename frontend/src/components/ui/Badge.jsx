const VARIANTS = {
  default: { color: 'var(--text-muted)', background: 'transparent' },
  violet:  { color: 'var(--violet)', background: 'var(--violet-soft)' },
  green:   { color: 'var(--green)', background: 'var(--green-soft)' },
  red:     { color: 'var(--red)', background: 'var(--red-soft)' },
  amber:   { color: 'var(--amber)', background: 'var(--amber-soft)' },
}

/* Style « tampon encreur » : contour à l'encre, uppercase, légère rotation. */
export default function Badge({ children, variant = 'default' }) {
  const { color, background } = VARIANTS[variant] || VARIANTS.default
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        border: `1.5px solid ${color}`,
        borderRadius: 3,
        fontSize: 11,
        fontFamily: 'DM Mono, monospace',
        fontWeight: 500,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        transform: 'rotate(-1.5deg)',
        background,
        color,
        opacity: 0.92,
      }}
    >
      {children}
    </span>
  )
}

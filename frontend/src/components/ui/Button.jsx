export default function Button({ variant = 'primary', icon: Icon, children, ...props }) {
  const base = {
    borderRadius: 'var(--radius-sm)',
    padding: '7px 14px',
    fontSize: 12,
    fontWeight: 500,
    fontFamily: "'DM Sans', sans-serif",
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    transition: 'background 120ms ease',
    lineHeight: 1,
  }

  const variants = {
    primary: {
      ...base,
      background: 'var(--accent)',
      color: '#fff',
      border: 'none',
    },
    ghost: {
      ...base,
      background: 'var(--bg-high)',
      color: 'var(--text-secondary)',
      border: '1px solid var(--border)',
    },
  }

  return (
    <button style={variants[variant] || variants.primary} {...props}>
      {Icon && <Icon size={12} stroke={1.5} />}
      {children}
    </button>
  )
}

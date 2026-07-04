import { IconLoader2 } from '@tabler/icons-react'

export default function Button({
  variant = 'primary',
  icon: Icon,
  loading = false,
  children,
  disabled,
  ...props
}) {
  const isDisabled = disabled || loading

  const base = {
    borderRadius: 'var(--radius-sm)',
    padding: '9px 18px',
    fontSize: 14,
    fontWeight: 500,
    fontFamily: "'DM Sans', sans-serif",
    cursor: isDisabled ? 'not-allowed' : 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 7,
    transition: 'background 120ms ease, opacity 120ms ease',
    lineHeight: 1,
    opacity: isDisabled ? 0.5 : 1,
    border: 'none',
  }

  const variants = {
    primary: {
      ...base,
      background: 'var(--accent)',
      color: '#fff',
    },
    ghost: {
      ...base,
      background: 'var(--bg-high)',
      color: 'var(--text-secondary)',
      border: '1px solid var(--border)',
    },
    danger: {
      ...base,
      background: 'var(--red-soft)',
      color: 'var(--red)',
      border: '1px solid rgba(240,82,82,0.22)',
    },
  }

  return (
    <button style={variants[variant] || variants.primary} disabled={isDisabled} {...props}>
      {loading
        ? <IconLoader2 size={14} stroke={1.5} style={{ animation: 'spin 600ms linear infinite' }} />
        : Icon && <Icon size={14} stroke={1.5} />}
      {children}
    </button>
  )
}

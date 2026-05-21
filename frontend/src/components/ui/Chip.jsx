export default function Chip({ children, active, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '4px 12px',
        borderRadius: 'var(--radius-sm)',
        fontSize: 12,
        fontFamily: "'DM Sans', sans-serif",
        cursor: 'pointer',
        border: '1px solid var(--border)',
        background: active ? 'var(--bg-high)' : 'transparent',
        color: active ? 'var(--text-primary)' : 'var(--text-muted)',
        transition: 'background 120ms ease, color 120ms ease',
      }}
    >
      {children}
    </button>
  )
}

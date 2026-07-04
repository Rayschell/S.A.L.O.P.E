export default function EmptyState({ icon: Icon, title, description, action, style = {} }) {
  return (
    <div
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        padding: '64px 24px', gap: 10, textAlign: 'center',
        animation: 'fade-in-up 200ms ease',
        ...style,
      }}
    >
      {Icon && (
        <div style={{
          width: 48, height: 48, borderRadius: 12,
          background: 'var(--bg-high)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 4,
        }}>
          <Icon size={20} stroke={1.2} color="var(--text-muted)" />
        </div>
      )}
      <p style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-secondary)' }}>
        {title}
      </p>
      {description && (
        <p style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 280, lineHeight: 1.65 }}>
          {description}
        </p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          style={{
            marginTop: 6,
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: 'var(--accent)', color: '#fff',
            border: 'none', borderRadius: 'var(--radius-sm)',
            padding: '8px 16px', fontSize: 12, fontWeight: 500,
            cursor: 'pointer', fontFamily: "'DM Sans', sans-serif",
            transition: 'opacity 120ms ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
        >
          {action.icon && <action.icon size={12} stroke={1.5} />}
          {action.label}
        </button>
      )}
    </div>
  )
}

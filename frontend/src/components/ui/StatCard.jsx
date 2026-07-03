export default function StatCard({ label, value, color }) {
  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        padding: 12,
      }}
    >
      <p
        style={{
          fontSize: 11,
          fontFamily: 'DM Mono, monospace',
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          marginBottom: 6,
        }}
      >
        {label}
      </p>
      <p
        style={{
          fontSize: 20,
          fontWeight: 600,
          letterSpacing: '-0.02em',
          color: color || 'var(--text-primary)',
        }}
      >
        {value}
      </p>
    </div>
  )
}

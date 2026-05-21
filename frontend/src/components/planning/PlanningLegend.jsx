export default function PlanningLegend() {
  return (
    <div style={{ display: 'flex', gap: 16, marginTop: 12, padding: '0 14px 12px', flexWrap: 'wrap' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
        <span
          style={{
            display: 'inline-block',
            width: 10,
            height: 10,
            borderRadius: 3,
            background: 'rgba(52, 199, 123, 0.25)',
            border: '1px solid rgba(52, 199, 123, 0.4)',
          }}
        />
        Staff
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
        <span
          style={{
            display: 'inline-block',
            width: 10,
            height: 10,
            borderRadius: 3,
            background: 'rgba(240, 82, 82, 0.2)',
            border: '1px solid rgba(240, 82, 82, 0.4)',
          }}
        />
        Respo bar
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
        <span
          style={{
            display: 'inline-block',
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: 'var(--violet)',
            marginRight: 2,
          }}
        />
        Membre bureau
      </div>
    </div>
  )
}

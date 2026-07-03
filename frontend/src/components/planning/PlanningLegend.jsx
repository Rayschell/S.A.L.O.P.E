const item = { display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, color: 'var(--text-muted)' }
const swatch = (bg, border) => ({
  display: 'inline-block',
  width: 12,
  height: 12,
  borderRadius: 3,
  background: bg,
  border: border ? `1px solid ${border}` : 'none',
})

export default function PlanningLegend() {
  return (
    <div style={{ display: 'flex', gap: 16, marginTop: 12, padding: '0 14px 12px', flexWrap: 'wrap' }}>
      <div style={item}>
        <span style={swatch('rgba(52, 199, 123, 0.25)', 'rgba(52, 199, 123, 0.4)')} />
        Staff
      </div>
      <div style={item}>
        <span style={swatch('rgba(240, 82, 82, 0.2)', 'rgba(240, 82, 82, 0.4)')} />
        Respo bar
      </div>
      <div style={item}>
        <span style={swatch('rgba(52, 199, 123, 0.10)', 'var(--border)')} />
        Disponible
      </div>
      <div style={item}>
        <span style={swatch('rgba(245, 158, 11, 0.15)', 'var(--border)')} />
        Peut-être
      </div>
      <div style={item}>
        <span style={swatch('repeating-linear-gradient(45deg, transparent, transparent 3px, rgba(128,128,128,0.35) 3px, rgba(128,128,128,0.35) 4px)', 'var(--border)')} />
        Indisponible
      </div>
      <div style={item}>
        <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', marginRight: 2 }} />
        Affectation manuelle
      </div>
      <div style={item}>
        <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: 'var(--violet)', marginRight: 2 }} />
        Membre bureau
      </div>
    </div>
  )
}

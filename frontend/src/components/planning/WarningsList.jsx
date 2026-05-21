import { IconAlertTriangle, IconAlertCircle, IconInfoCircle } from '@tabler/icons-react'

const WARNING_LABELS = {
  no_respo_bar: 'Respo bar manquant',
  slot_understaffed: 'Créneau sous-effectif',
  no_bureau: 'Aucun membre bureau',
  maybe_forced: 'Disponibilité "maybe" forcée',
  affinity_unsatisfied: 'Affinité non satisfaite',
  over_quota: 'Quota dépassé (escalade)',
  long_pause: 'Pause 2h entre blocs (info)',
  no_slots: 'Info',
}

const WARNING_STYLE = {
  no_respo_bar: { bg: 'var(--red-soft)', border: 'rgba(240,82,82,0.2)', color: 'var(--red)', Icon: IconAlertCircle },
  slot_understaffed: { bg: 'var(--amber-soft)', border: 'rgba(245,158,11,0.2)', color: 'var(--amber)', Icon: IconAlertTriangle },
  maybe_forced: { bg: 'var(--amber-soft)', border: 'rgba(245,158,11,0.2)', color: 'var(--amber)', Icon: IconAlertTriangle },
  over_quota: { bg: 'var(--red-soft)', border: 'rgba(240,82,82,0.2)', color: 'var(--red)', Icon: IconAlertCircle },
  no_bureau: { bg: 'var(--accent-soft)', border: 'rgba(37,99,196,0.2)', color: 'var(--accent)', Icon: IconInfoCircle },
  affinity_unsatisfied: { bg: 'var(--violet-soft)', border: 'rgba(124,106,247,0.2)', color: 'var(--violet)', Icon: IconInfoCircle },
  long_pause: { bg: 'rgba(255,255,255,0.04)', border: 'var(--border)', color: 'var(--text-muted)', Icon: IconInfoCircle },
  no_slots: { bg: 'rgba(255,255,255,0.04)', border: 'var(--border)', color: 'var(--text-muted)', Icon: IconInfoCircle },
}

const DEFAULT_STYLE = { bg: 'rgba(255,255,255,0.04)', border: 'var(--border)', color: 'var(--text-muted)', Icon: IconInfoCircle }

export default function WarningsList({ warnings }) {
  if (warnings.length === 0) return null

  const grouped = {}
  for (const w of warnings) {
    if (!grouped[w.type]) grouped[w.type] = []
    grouped[w.type].push(w)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>
        {warnings.length} avertissement(s) après génération
      </p>
      {Object.entries(grouped).map(([type, items]) => {
        const { bg, border, color, Icon } = WARNING_STYLE[type] || DEFAULT_STYLE
        return (
          <div
            key={type}
            style={{
              background: bg,
              border: `1px solid ${border}`,
              borderRadius: 'var(--radius-sm)',
              padding: '10px 14px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: items.length > 1 ? 6 : 0 }}>
              <Icon size={13} stroke={1.5} color={color} />
              <span style={{ fontSize: 12, fontWeight: 500, color }}>
                {WARNING_LABELS[type] || type} ({items.length})
              </span>
            </div>
            {items.map((w, i) => (
              <p key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 3, paddingLeft: 20 }}>
                · {w.message}
              </p>
            ))}
          </div>
        )
      })}
    </div>
  )
}

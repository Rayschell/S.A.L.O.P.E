import { IconAlertTriangle } from '@tabler/icons-react'

export default function WarningBar({ message }) {
  return (
    <div
      style={{
        background: 'var(--amber-soft)',
        border: '1px solid rgba(245, 158, 11, 0.15)',
        borderRadius: 'var(--radius-sm)',
        padding: '10px 14px',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        fontSize: 12,
        color: 'var(--amber)',
      }}
    >
      <IconAlertTriangle size={14} stroke={1.5} />
      {message}
    </div>
  )
}

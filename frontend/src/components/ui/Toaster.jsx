import { useState, useEffect } from 'react'
import { IconAlertCircle, IconCheck } from '@tabler/icons-react'

let _id = 0
const listeners = new Set()

function emit(toast) {
  listeners.forEach((fn) => fn(toast))
}

export const toast = {
  error(msg) { emit({ id: ++_id, type: 'error', msg }) },
  success(msg) { emit({ id: ++_id, type: 'success', msg }) },
}

export default function Toaster() {
  const [toasts, setToasts] = useState([])

  useEffect(() => {
    const handler = (t) => {
      setToasts((prev) => [...prev, t])
      setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== t.id)), 4000)
    }
    listeners.add(handler)
    return () => listeners.delete(handler)
  }, [])

  if (!toasts.length) return null

  return (
    <div style={{ position: 'fixed', bottom: 20, right: 20, zIndex: 10000, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {toasts.map((t) => {
        const color = t.type === 'error' ? 'var(--red)' : 'var(--green)'
        const Icon = t.type === 'error' ? IconAlertCircle : IconCheck
        return (
          <div
            key={t.id}
            onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-mid)',
              borderLeft: `3px solid ${color}`,
              borderRadius: 'var(--radius-md)',
              padding: '10px 14px',
              fontSize: 13,
              fontFamily: "'DM Sans', sans-serif",
              boxShadow: '0 4px 16px rgba(0,0,0,0.35)',
              cursor: 'pointer',
              color: 'var(--text-primary)',
              maxWidth: 320,
            }}
          >
            <Icon size={14} stroke={1.5} color={color} style={{ flexShrink: 0 }} />
            <span>{t.msg}</span>
          </div>
        )
      })}
    </div>
  )
}

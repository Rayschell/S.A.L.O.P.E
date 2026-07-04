import { useState, useEffect } from 'react'
import {
  IconAlertCircle, IconCheck, IconAlertTriangle, IconInfoCircle, IconX,
} from '@tabler/icons-react'

let _id = 0
const listeners = new Set()

function emit(t) { listeners.forEach((fn) => fn(t)) }

export const toast = {
  error(msg, opts)   { emit({ id: ++_id, type: 'error',   msg, ...opts }) },
  success(msg, opts) { emit({ id: ++_id, type: 'success', msg, ...opts }) },
  warning(msg, opts) { emit({ id: ++_id, type: 'warning', msg, ...opts }) },
  info(msg, opts)    { emit({ id: ++_id, type: 'info',    msg, ...opts }) },
}

const DURATION = 4500

const TYPE = {
  error:   { color: 'var(--red)',    Icon: IconAlertCircle },
  success: { color: 'var(--green)',  Icon: IconCheck },
  warning: { color: 'var(--amber)',  Icon: IconAlertTriangle },
  info:    { color: 'var(--accent)', Icon: IconInfoCircle },
}

export default function Toaster() {
  const [toasts, setToasts] = useState([])

  const dismiss = (id) => setToasts((prev) => prev.filter((x) => x.id !== id))

  useEffect(() => {
    const handler = (t) => {
      setToasts((prev) => [...prev, t])
      setTimeout(() => dismiss(t.id), DURATION)
    }
    listeners.add(handler)
    return () => listeners.delete(handler)
  }, [])

  if (!toasts.length) return null

  return (
    <div style={{
      position: 'fixed', bottom: 20, right: 20, zIndex: 10000,
      display: 'flex', flexDirection: 'column', gap: 8,
      pointerEvents: 'none',
    }}>
      {toasts.map((t) => {
        const { color, Icon } = TYPE[t.type] || TYPE.info
        return (
          <div
            key={t.id}
            style={{
              display: 'flex', flexDirection: 'column',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-mid)',
              borderLeft: `3px solid ${color}`,
              borderRadius: 'var(--radius-md)',
              boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
              maxWidth: 340, minWidth: 240,
              overflow: 'hidden',
              animation: 'fade-in-up 150ms ease',
              pointerEvents: 'all',
            }}
          >
            <div style={{
              display: 'flex', alignItems: 'flex-start', gap: 8,
              padding: '10px 12px 10px 14px',
              justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, flex: 1, minWidth: 0 }}>
                <Icon size={14} stroke={1.5} color={color} style={{ flexShrink: 0, marginTop: 1 }} />
                <span style={{
                  fontSize: 13, fontFamily: "'DM Sans', sans-serif",
                  color: 'var(--text-primary)', lineHeight: 1.45,
                }}>
                  {t.msg}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0, marginTop: 1 }}>
                {t.action && (
                  <button
                    onClick={() => { t.action.onClick(); dismiss(t.id) }}
                    style={{
                      fontSize: 12, fontWeight: 600, color,
                      background: 'transparent', border: 'none',
                      cursor: 'pointer', fontFamily: "'DM Sans', sans-serif",
                      padding: '1px 4px', borderRadius: 4,
                      transition: 'opacity 120ms ease',
                    }}
                  >
                    {t.action.label}
                  </button>
                )}
                <button
                  onClick={() => dismiss(t.id)}
                  style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: 'var(--text-muted)', display: 'flex', alignItems: 'center',
                    padding: 2, borderRadius: 4,
                    transition: 'color 120ms ease',
                  }}
                >
                  <IconX size={12} stroke={1.5} />
                </button>
              </div>
            </div>
            <div style={{ height: 2, background: 'var(--border)', position: 'relative', overflow: 'hidden' }}>
              <div style={{
                position: 'absolute', left: 0, top: 0, height: '100%',
                background: color, opacity: 0.45,
                animation: `progress-shrink ${DURATION}ms linear forwards`,
              }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

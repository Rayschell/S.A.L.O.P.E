import { useState, useEffect } from 'react'
import { IconTrash, IconAlertTriangle } from '@tabler/icons-react'

let _resolve = null
const listeners = new Set()

export function showConfirm(opts) {
  return new Promise((resolve) => {
    _resolve = resolve
    listeners.forEach((fn) => fn(opts))
  })
}

export default function ConfirmModal() {
  const [state, setState] = useState(null)

  useEffect(() => {
    const handler = (opts) => setState(opts)
    listeners.add(handler)
    return () => listeners.delete(handler)
  }, [])

  useEffect(() => {
    if (!state) return
    const onKey = (e) => { if (e.key === 'Escape') close(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [state])

  if (!state) return null

  const close = (confirmed) => {
    setState(null)
    if (_resolve) { _resolve(confirmed); _resolve = null }
  }

  const isDanger = state.variant === 'danger'
  const ModalIcon = isDanger ? IconTrash : IconAlertTriangle

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.65)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 9999,
      }}
      onClick={() => close(false)}
    >
      <div
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-mid)',
          borderRadius: 'var(--radius-lg)',
          padding: 24,
          width: '100%',
          maxWidth: 380,
          margin: '0 16px',
          animation: 'scale-in 140ms ease',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start', marginBottom: 20 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 9, flexShrink: 0,
            background: isDanger ? 'var(--red-soft)' : 'var(--amber-soft)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <ModalIcon size={16} stroke={1.5} color={isDanger ? 'var(--red)' : 'var(--amber)'} />
          </div>
          <div>
            <h3 style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 5 }}>
              {state.title}
            </h3>
            {state.message && (
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                {state.message}
              </p>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={() => close(false)} style={btnGhost}>
            {state.cancelLabel || 'Annuler'}
          </button>
          <button
            onClick={() => close(true)}
            autoFocus
            style={{
              ...btnBase,
              background: isDanger ? 'var(--red)' : 'var(--accent)',
              color: '#fff',
            }}
          >
            {state.confirmLabel || 'Confirmer'}
          </button>
        </div>
      </div>
    </div>
  )
}

const btnBase = {
  borderRadius: 'var(--radius-sm)',
  padding: '7px 14px',
  fontSize: 12,
  fontWeight: 500,
  fontFamily: "'DM Sans', sans-serif",
  cursor: 'pointer',
  border: 'none',
  transition: 'opacity 120ms ease',
}

const btnGhost = {
  ...btnBase,
  background: 'var(--bg-high)',
  color: 'var(--text-secondary)',
  border: '1px solid var(--border)',
}

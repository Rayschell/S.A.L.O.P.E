import { Component } from 'react'
import { IconAlertTriangle, IconRefresh } from '@tabler/icons-react'

export default class ErrorBoundary extends Component {
  state = { hasError: false, error: null }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div style={{
        minHeight: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg-base)', gap: 16, padding: 24, textAlign: 'center',
      }}>
        <div style={{
          width: 52, height: 52, borderRadius: 14,
          background: 'var(--red-soft)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <IconAlertTriangle size={24} stroke={1.5} color="var(--red)" />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <h1 style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-primary)' }}>
            Quelque chose s'est mal passé
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 320, lineHeight: 1.6, margin: '0 auto' }}>
            Une erreur inattendue s'est produite. Recharge la page pour continuer.
          </p>
          {this.state.error && (
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, fontFamily: 'DM Mono, monospace' }}>
              {this.state.error.message}
            </p>
          )}
        </div>
        <button
          onClick={() => window.location.reload()}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: 'var(--accent)', color: '#fff',
            border: 'none', borderRadius: 'var(--radius-sm)',
            padding: '8px 16px', fontSize: 12, fontWeight: 500,
            cursor: 'pointer', fontFamily: "'DM Sans', sans-serif",
          }}
        >
          <IconRefresh size={12} stroke={1.5} />
          Recharger la page
        </button>
      </div>
    )
  }
}

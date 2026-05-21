import { useState } from 'react'
import { eventsApi } from '../../api/events.js'
import NameResolutionModal from './NameResolutionModal.jsx'
import { IconUpload } from '@tabler/icons-react'

export default function CsvImport({ eventId, onImported, disabled }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [pendingData, setPendingData] = useState(null)

  const handleUpload = async () => {
    if (!file) return
    setError('')
    setUploading(true)
    try {
      const data = await eventsApi.importCsv(eventId, file)
      setResult(data)
      if (data.pending?.length > 0) {
        setPendingData(data.pending)
      } else {
        onImported()
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur lors de l'import.")
    } finally {
      setUploading(false)
    }
  }

  const handleResolved = async (resolutions) => {
    await eventsApi.resolvePending(eventId, resolutions)
    setPendingData(null)
    setResult(null)
    setFile(null)
    onImported()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          Importez un export CSV de meeting poll Strawpoll. Les noms seront automatiquement résolus
          via les alias connus (fuzzy matching). Les cas ambigus seront soumis à validation manuelle.
        </p>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <label
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '7px 12px',
            fontSize: 12,
            background: 'var(--bg-high)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            cursor: disabled ? 'not-allowed' : 'pointer',
            color: 'var(--text-secondary)',
            fontFamily: "'DM Sans', sans-serif",
            opacity: disabled ? 0.5 : 1,
          }}
        >
          <input
            type="file"
            accept=".csv"
            disabled={disabled}
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            style={{ display: 'none' }}
          />
          {file ? file.name : 'Choisir un fichier…'}
        </label>
        <button
          onClick={handleUpload}
          disabled={!file || uploading || disabled}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '7px 14px',
            fontSize: 12,
            background: 'var(--violet)',
            color: '#fff',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            cursor: !file || uploading || disabled ? 'not-allowed' : 'pointer',
            opacity: !file || uploading || disabled ? 0.5 : 1,
            fontWeight: 500,
            fontFamily: "'DM Sans', sans-serif",
          }}
        >
          <IconUpload size={11} stroke={1.5} />
          {uploading ? 'Import…' : 'Importer'}
        </button>
      </div>

      {error && (
        <div
          style={{
            background: 'var(--red-soft)',
            border: '1px solid rgba(240, 82, 82, 0.2)',
            borderRadius: 'var(--radius-sm)',
            padding: '8px 12px',
            fontSize: 12,
            color: 'var(--red)',
          }}
        >
          {error}
        </div>
      )}

      {result && !pendingData && (
        <div
          style={{
            background: 'var(--green-soft)',
            border: '1px solid rgba(52, 199, 123, 0.2)',
            borderRadius: 'var(--radius-sm)',
            padding: '8px 12px',
            fontSize: 12,
            color: 'var(--green)',
          }}
        >
          {result.imported_count} ligne(s) importée(s) avec succès.
        </div>
      )}

      {pendingData && (
        <NameResolutionModal
          pending={pendingData}
          onResolved={handleResolved}
          onCancel={() => setPendingData(null)}
        />
      )}
    </div>
  )
}

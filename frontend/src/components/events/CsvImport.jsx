import { useState } from 'react'
import { eventsApi } from '../../api/events.js'
import NameResolutionModal from './NameResolutionModal.jsx'

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
      setError(err.response?.data?.detail || 'Erreur lors de l\'import.')
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
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-700">Import CSV Strawpoll</h2>
      <p className="text-sm text-gray-500">
        Importez un export CSV de meeting poll Strawpoll. Les noms seront automatiquement résolus
        via les alias connus (fuzzy matching). Les cas ambigus seront soumis à validation manuelle.
      </p>

      <div className="flex items-center gap-3">
        <input
          type="file"
          accept=".csv"
          disabled={disabled}
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border file:border-gray-300 file:text-sm file:bg-white file:cursor-pointer"
        />
        <button
          onClick={handleUpload}
          disabled={!file || uploading || disabled}
          className="px-4 py-2 text-sm bg-blue-700 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
        >
          {uploading ? 'Import…' : 'Importer'}
        </button>
      </div>

      {error && (
        <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">
          {error}
        </p>
      )}

      {result && !pendingData && (
        <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-800">
          ✅ {result.imported_count} ligne(s) importée(s) avec succès.
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

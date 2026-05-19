import { useState } from 'react'

export default function NameResolutionModal({ pending, onResolved, onCancel }) {
  // resolutions: {csv_name, member_id?, create_new, availabilities}
  const [resolutions, setResolutions] = useState(
    pending.map((p) => ({
      csv_name: p.csv_name,
      member_id: p.suggestions?.[0]?.member_id ?? null,
      create_new: p.suggestions?.length === 0,
      availabilities: p.availabilities,
    }))
  )

  const updateResolution = (idx, updates) => {
    setResolutions((prev) => {
      const next = [...prev]
      next[idx] = { ...next[idx], ...updates }
      return next
    })
  }

  const handleConfirm = () => {
    onResolved(resolutions)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-800">
            Résolution manuelle des noms ({pending.length})
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Les noms suivants n'ont pas pu être résolus automatiquement. Choisissez le membre correspondant ou créez-en un nouveau.
          </p>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-4 space-y-5">
          {pending.map((p, idx) => {
            const res = resolutions[idx]
            return (
              <div key={p.csv_name} className="border border-gray-200 rounded-lg p-4">
                <p className="font-medium text-gray-800 mb-3">
                  📋 <span className="font-mono bg-gray-100 px-1 rounded">{p.csv_name}</span>
                </p>

                <div className="space-y-2">
                  {p.suggestions.map((s) => (
                    <label key={s.member_id} className="flex items-center gap-3 cursor-pointer text-sm">
                      <input
                        type="radio"
                        name={`resolution-${idx}`}
                        checked={!res.create_new && res.member_id === s.member_id}
                        onChange={() =>
                          updateResolution(idx, { member_id: s.member_id, create_new: false })
                        }
                      />
                      <span>{s.display_name}</span>
                      <span className="text-xs text-gray-400">Score : {s.score}%</span>
                    </label>
                  ))}

                  <label className="flex items-center gap-3 cursor-pointer text-sm">
                    <input
                      type="radio"
                      name={`resolution-${idx}`}
                      checked={res.create_new}
                      onChange={() =>
                        updateResolution(idx, { create_new: true, member_id: null })
                      }
                    />
                    <span className="text-blue-700">➕ Créer un nouveau membre « {p.csv_name} »</span>
                  </label>
                </div>
              </div>
            )
          })}
        </div>

        <div className="px-6 py-4 border-t flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm rounded border hover:bg-gray-50"
          >
            Annuler
          </button>
          <button
            onClick={handleConfirm}
            className="px-4 py-2 text-sm rounded bg-blue-700 text-white hover:bg-blue-600"
          >
            Confirmer les résolutions
          </button>
        </div>
      </div>
    </div>
  )
}

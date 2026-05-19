const ROLE_LABELS = { staff: 'Staff', bureau: 'Bureau' }
const ROLE_COLORS = {
  staff: 'bg-gray-100 text-gray-700',
  bureau: 'bg-blue-100 text-blue-800',
}

export default function MemberTable({ members, isBureau, onEdit, onDelete, onResetCounters }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 shadow-sm bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
          <tr>
            <th className="px-4 py-3 text-left">Nom</th>
            <th className="px-4 py-3 text-left">Email</th>
            <th className="px-4 py-3 text-left">Rôles</th>
            <th className="px-4 py-3 text-right">Heures</th>
            <th className="px-4 py-3 text-right">Respo bar</th>
            {isBureau && <th className="px-4 py-3 text-right">Actions</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {members.map((m) => (
            <tr key={m.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 font-medium text-gray-800">
                {m.prenom} {m.nom}
              </td>
              <td className="px-4 py-3 text-gray-500">{m.email || '—'}</td>
              <td className="px-4 py-3">
                <div className="flex gap-1 flex-wrap">
                  {(m.roles || []).map((r) => (
                    <span key={r} className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[r] || 'bg-gray-100 text-gray-600'}`}>
                      {ROLE_LABELS[r] || r}
                    </span>
                  ))}
                </div>
              </td>
              <td className="px-4 py-3 text-right tabular-nums">{m.heures_cumulees.toFixed(1)}h</td>
              <td className="px-4 py-3 text-right tabular-nums">{m.shifts_respo_bar_cumules}</td>
              {isBureau && (
                <td className="px-4 py-3 text-right">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => onEdit(m)}
                      className="text-xs px-2 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100"
                    >
                      Modifier
                    </button>
                    <button
                      onClick={() => onResetCounters(m.id)}
                      className="text-xs px-2 py-1 rounded bg-orange-50 text-orange-700 hover:bg-orange-100"
                    >
                      Réinit.
                    </button>
                    <button
                      onClick={() => onDelete(m.id)}
                      className="text-xs px-2 py-1 rounded bg-red-50 text-red-600 hover:bg-red-100"
                    >
                      Suppr.
                    </button>
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

import { useState } from 'react'
import { saisonsApi } from '../../api/saisons.js'
import { IconPlus, IconTrash, IconPencil, IconCheck, IconX } from '@tabler/icons-react'

const EMPTY = { nom: '', date_debut: '', date_fin: '' }

/**
 * Modale de gestion des saisons (mandats de bureau, ~avril → avril).
 * CRUD bureau : liste éditable inline + formulaire d'ajout.
 */
export default function SaisonManager({ saisons, onChanged, onClose }) {
  const [editingId, setEditingId] = useState(null) // id en cours d'édition, 'new' pour l'ajout
  const [form, setForm] = useState(EMPTY)
  const [busy, setBusy] = useState(false)

  const startEdit = (s) => {
    setEditingId(s.id)
    setForm({ nom: s.nom, date_debut: s.date_debut, date_fin: s.date_fin ?? '' })
  }

  const startAdd = () => {
    setEditingId('new')
    setForm(EMPTY)
  }

  const cancelEdit = () => {
    setEditingId(null)
    setForm(EMPTY)
  }

  // date_fin vide = saison en cours (pas de fin)
  const valid = form.nom.trim() && form.date_debut && (!form.date_fin || form.date_debut < form.date_fin)

  const save = async () => {
    if (!valid) return
    setBusy(true)
    try {
      const payload = { ...form, date_fin: form.date_fin || null }
      if (editingId === 'new') await saisonsApi.create(payload)
      else await saisonsApi.update(editingId, payload)
      cancelEdit()
      onChanged()
    } finally {
      setBusy(false)
    }
  }

  const remove = async (s) => {
    if (!confirm(`Supprimer la saison « ${s.nom} » ? Les stats reviendront au cumul total.`)) return
    setBusy(true)
    try {
      await saisonsApi.delete(s.id)
      if (editingId === s.id) cancelEdit()
      onChanged()
    } finally {
      setBusy(false)
    }
  }

  const fmtDate = (d) => new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })

  const editorRow = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', flexWrap: 'wrap' }}>
      <input
        type="text"
        value={form.nom}
        onChange={(e) => setForm((f) => ({ ...f, nom: e.target.value }))}
        placeholder="Mandat 2026-2027"
        autoFocus
        style={{ ...inputStyle, flex: '1 1 140px' }}
      />
      <input
        type="date"
        value={form.date_debut}
        onChange={(e) => setForm((f) => ({ ...f, date_debut: e.target.value }))}
        style={inputStyle}
      />
      <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>→</span>
      <input
        type="date"
        value={form.date_fin}
        onChange={(e) => setForm((f) => ({ ...f, date_fin: e.target.value }))}
        style={inputStyle}
      />
      <button onClick={save} disabled={!valid || busy} title="Enregistrer" style={{ ...iconBtnStyle, color: valid ? 'var(--green)' : 'var(--text-muted)', cursor: valid && !busy ? 'pointer' : 'not-allowed' }}>
        <IconCheck size={15} stroke={1.5} />
      </button>
      <button onClick={cancelEdit} title="Annuler" style={iconBtnStyle}>
        <IconX size={15} stroke={1.5} />
      </button>
    </div>
  )

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-mid)', borderRadius: 'var(--radius-lg)', padding: 24, width: '100%', maxWidth: 560, margin: '0 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <h2 style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>Saisons</h2>
          <button onClick={onClose} style={iconBtnStyle} title="Fermer">
            <IconX size={16} stroke={1.5} />
          </button>
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14 }}>
          Une saison correspond à un mandat de bureau (souvent avril → avril). Le filtre de la page
          Membres, le badge ✦ et les histogrammes se calculent sur la saison sélectionnée.
          Laisser la date de fin vide pour la saison en cours.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {saisons.length === 0 && editingId !== 'new' && (
            <p style={{ fontSize: 13, color: 'var(--text-muted)', padding: '10px 0' }}>
              Aucune saison définie — les stats affichent tout l'historique.
            </p>
          )}
          {saisons.map((s) =>
            editingId === s.id ? (
              <div key={s.id}>{editorRow}</div>
            ) : (
              <div key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: 13.5, color: 'var(--text-primary)', fontWeight: 500 }}>{s.nom}</span>
                <span style={{ fontSize: 12, fontFamily: 'DM Mono, monospace', color: 'var(--text-muted)' }}>
                  {fmtDate(s.date_debut)} → {s.date_fin ? fmtDate(s.date_fin) : 'en cours'}
                </span>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
                  <button onClick={() => startEdit(s)} title="Modifier" style={iconBtnStyle}>
                    <IconPencil size={14} stroke={1.5} />
                  </button>
                  <button onClick={() => remove(s)} title="Supprimer" style={{ ...iconBtnStyle, color: 'var(--red)' }}>
                    <IconTrash size={14} stroke={1.5} />
                  </button>
                </div>
              </div>
            )
          )}
          {editingId === 'new' ? (
            editorRow
          ) : (
            <button
              onClick={startAdd}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6, alignSelf: 'flex-start',
                marginTop: 12, background: 'var(--bg-high)', color: 'var(--text-secondary)',
                border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
                padding: '6px 12px', fontSize: 12.5, cursor: 'pointer',
                fontFamily: "'DM Sans', sans-serif",
              }}
            >
              <IconPlus size={13} stroke={1.5} />
              Ajouter une saison
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

const inputStyle = {
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)',
  padding: '6px 10px',
  fontSize: 13,
  color: 'var(--text-primary)',
  fontFamily: "'DM Sans', sans-serif",
  outline: 'none',
}

const iconBtnStyle = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  color: 'var(--text-muted)',
  display: 'flex',
  alignItems: 'center',
  padding: 4,
}

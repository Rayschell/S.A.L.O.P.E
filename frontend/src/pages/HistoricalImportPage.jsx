import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { historiqueApi } from '../api/historique.js'
import { membersApi } from '../api/members.js'
import { IconUpload, IconCheck, IconX, IconAlertTriangle, IconHistory } from '@tabler/icons-react'

// ── Helpers ───────────────────────────────────────────────────────────────────

const CELL_COLOR = { staff: '#22543d', respo_bar: '#742a2a' }
const CELL_BG    = { staff: 'rgba(52,199,123,0.22)', respo_bar: 'rgba(240,82,82,0.22)' }
const CELL_LABEL = { staff: 'Staff', respo_bar: 'Respo' }

// ── Step 1: upload + metadata form ───────────────────────────────────────────

function UploadStep({ onNext }) {
  const [nom, setNom] = useState('')
  const [date, setDate] = useState('')
  const [type, setType] = useState('soiree')
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  const onFileChange = (f) => {
    setFile(f)
    setError(null)
    if (f) setPreview(URL.createObjectURL(f))
  }

  const onDrop = (e) => {
    e.preventDefault()
    const f = e.dataTransfer.files[0]
    if (f) onFileChange(f)
  }

  const handleSubmit = async () => {
    if (!nom.trim() || !date || !file) {
      setError('Remplissez tous les champs et choisissez une image.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const result = await historiqueApi.preview(file)
      onNext({ nom, date, type, parsed: result })
    } catch (e) {
      setError(e.response?.data?.detail || "Erreur lors du parsing de l'image.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 560 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={labelStyle}>Nom de l'événement</label>
        <input
          value={nom}
          onChange={(e) => setNom(e.target.value)}
          placeholder="ex. Soirée Février 2025"
          style={inputStyle}
        />
      </div>

      <div style={{ display: 'flex', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
          <label style={labelStyle}>Date</label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={inputStyle} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
          <label style={labelStyle}>Type</label>
          <select value={type} onChange={(e) => setType(e.target.value)} style={inputStyle}>
            <option value="soiree">Soirée</option>
            <option value="afterwork">Afterwork</option>
          </select>
        </div>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `2px dashed ${file ? 'var(--green)' : 'var(--border-mid)'}`,
          borderRadius: 10,
          padding: 28,
          textAlign: 'center',
          cursor: 'pointer',
          background: file ? 'rgba(52,199,123,0.05)' : 'var(--bg-elevated)',
          transition: 'all 180ms ease',
        }}
      >
        <input ref={inputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => onFileChange(e.target.files[0])} />
        {preview ? (
          <img src={preview} alt="preview" style={{ maxWidth: '100%', maxHeight: 180, borderRadius: 6, objectFit: 'contain' }} />
        ) : (
          <>
            <IconUpload size={28} stroke={1.5} color="var(--text-muted)" style={{ marginBottom: 8 }} />
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Glissez l'image ici ou cliquez pour parcourir</p>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>PNG, JPEG, WEBP</p>
          </>
        )}
      </div>

      {file && (
        <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
          📎 {file.name}
        </p>
      )}

      {error && <p style={{ fontSize: 12, color: 'var(--red)' }}>{error}</p>}

      <button onClick={handleSubmit} disabled={loading} style={btnPrimaryStyle}>
        {loading ? 'Analyse en cours…' : 'Analyser l\'image →'}
      </button>

      <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
        L'image doit être une capture nette d'une grille de planning avec un fond bleu en en-tête,
        des cellules vertes (staff) et rouges (respo bar). L'OCR peut faire des erreurs — vous pourrez corriger avant d'importer.
      </p>
    </div>
  )
}

// ── Step 2: validate parsed grid ─────────────────────────────────────────────

function ValidateStep({ meta, parsed, onBack, onCommit }) {
  const { nom, date, type } = meta
  const [slots, setSlots] = useState(parsed.slots)
  const [members, setMembers] = useState(parsed.members)
  const [allMembers, setAllMembers] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // {csv_name: member_id | null | 'new'}
  const [resolutionMap, setResolutionMap] = useState(() => {
    const m = {}
    for (const row of parsed.members) {
      m[row.csv_name] = row.member_id ?? null
    }
    return m
  })

  useEffect(() => {
    membersApi.list().then(setAllMembers)
  }, [])

  const unresolvedNames = new Set(parsed.unresolved.map((u) => u.csv_name))

  const updateSlot = (idx, field, val) => {
    setSlots((prev) => prev.map((s, i) => i === idx ? { ...s, [field]: val } : s))
  }

  const toggleCell = (memberIdx, slotIdx) => {
    setMembers((prev) => prev.map((m, mi) => {
      if (mi !== memberIdx) return m
      const existing = m.assignments.find((a) => a.slot_index === slotIdx)
      let next
      if (!existing) {
        next = [...m.assignments, { slot_index: slotIdx, type_affectation: 'staff' }]
      } else if (existing.type_affectation === 'staff') {
        next = m.assignments.map((a) => a.slot_index === slotIdx ? { ...a, type_affectation: 'respo_bar' } : a)
      } else {
        next = m.assignments.filter((a) => a.slot_index !== slotIdx)
      }
      return { ...m, assignments: next }
    }))
  }

  const removeMember = (idx) => {
    setMembers((prev) => prev.filter((_, i) => i !== idx))
  }

  const handleCommit = async () => {
    const resolutions = Object.entries(resolutionMap)
      .filter(([, v]) => v !== null)
      .map(([csv_name, v]) => ({
        csv_name,
        member_id: v === 'new' ? null : v,
        create_new: v === 'new',
      }))

    setLoading(true)
    setError(null)
    try {
      await onCommit({
        event_nom: nom,
        event_date: date,
        event_type: type,
        slots,
        members,
        resolutions,
      })
    } catch (e) {
      setError(e.response?.data?.detail || "Erreur lors de l'import.")
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header recap */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{nom}</span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace' }}>{date}</span>
        <span style={{
          fontSize: 11, padding: '2px 8px', borderRadius: 99,
          background: type === 'soiree' ? 'rgba(124,106,247,0.15)' : 'rgba(37,99,196,0.15)',
          color: type === 'soiree' ? '#7c6af7' : '#2563c4',
        }}>{type}</span>
        <button onClick={onBack} style={{ marginLeft: 'auto', ...btnGhostStyle }}>← Retour</button>
      </div>

      {/* Unresolved names */}
      {parsed.unresolved.length > 0 && (
        <div style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: 8, padding: '10px 14px' }}>
          <p style={{ fontSize: 12, fontWeight: 500, color: '#f59e0b', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <IconAlertTriangle size={14} stroke={1.5} /> {parsed.unresolved.length} nom(s) non reconnu(s) — choisissez ci-dessous
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {parsed.unresolved.map((u) => (
              <div key={u.csv_name} style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12, fontFamily: 'DM Mono, monospace', color: 'var(--text-secondary)', minWidth: 140 }}>
                  {u.csv_name}
                </span>
                <select
                  value={resolutionMap[u.csv_name] ?? ''}
                  onChange={(e) => setResolutionMap((prev) => ({ ...prev, [u.csv_name]: e.target.value || null }))}
                  style={{ ...inputStyle, flex: 1, minWidth: 180, fontSize: 12 }}
                >
                  <option value="">— Ignorer ce membre —</option>
                  <option value="new">✦ Créer nouveau membre</option>
                  {u.suggestions.map((s) => (
                    <option key={s.member_id} value={s.member_id}>
                      {s.display_name} ({Math.round(s.score * 100)}%)
                    </option>
                  ))}
                  {allMembers.filter(m => !u.suggestions.find(s => s.member_id === m.id)).map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.prenom} {m.nom}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Slot header editors */}
      <div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
          Vérifiez les créneaux détectés (format HH:MM) :
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {slots.map((s, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 6, padding: '4px 8px' }}>
              <input
                value={s.heure_debut}
                onChange={(e) => updateSlot(i, 'heure_debut', e.target.value)}
                style={{ width: 48, background: 'none', border: 'none', color: 'var(--text-primary)', fontFamily: 'DM Mono, monospace', fontSize: 12, textAlign: 'center' }}
              />
              <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>–</span>
              <input
                value={s.heure_fin}
                onChange={(e) => updateSlot(i, 'heure_fin', e.target.value)}
                style={{ width: 48, background: 'none', border: 'none', color: 'var(--text-primary)', fontFamily: 'DM Mono, monospace', fontSize: 12, textAlign: 'center' }}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Grid preview */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', fontSize: 11, whiteSpace: 'nowrap' }}>
          <thead>
            <tr>
              <th style={thStyle}>Membre</th>
              {slots.map((s, i) => (
                <th key={i} style={{ ...thStyle, fontFamily: 'DM Mono, monospace', fontSize: 10 }}>
                  {s.heure_debut}–{s.heure_fin}
                </th>
              ))}
              <th style={thStyle} />
            </tr>
          </thead>
          <tbody>
            {members.map((m, mi) => {
              const isUnresolved = unresolvedNames.has(m.csv_name) && !resolutionMap[m.csv_name]
              return (
                <tr key={mi} style={{ opacity: isUnresolved ? 0.4 : 1 }}>
                  <td style={{ ...tdStyle, color: isUnresolved ? 'var(--amber)' : 'var(--text-primary)', fontWeight: 500 }}>
                    {m.csv_name}
                  </td>
                  {slots.map((_, si) => {
                    const asgn = m.assignments.find((a) => a.slot_index === si)
                    const t = asgn?.type_affectation
                    return (
                      <td
                        key={si}
                        onClick={() => toggleCell(mi, si)}
                        style={{
                          ...tdStyle,
                          background: t ? CELL_BG[t] : 'transparent',
                          color: t ? CELL_COLOR[t] : 'transparent',
                          cursor: 'pointer',
                          fontWeight: 600,
                          textAlign: 'center',
                          userSelect: 'none',
                          minWidth: 60,
                        }}
                        title="Cliquer pour changer : vide → staff → respo bar → vide"
                      >
                        {t ? CELL_LABEL[t] : '·'}
                      </td>
                    )
                  })}
                  <td style={tdStyle}>
                    <button
                      onClick={() => removeMember(mi)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 2 }}
                      title="Retirer ce membre"
                    >
                      <IconX size={12} stroke={1.5} />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>
        Cliquez sur une cellule pour changer : vide → Staff → Respo bar → vide
      </p>

      {error && <p style={{ fontSize: 12, color: 'var(--red)' }}>{error}</p>}

      <button onClick={handleCommit} disabled={loading} style={{ ...btnPrimaryStyle, alignSelf: 'flex-start' }}>
        <IconCheck size={14} stroke={2} />
        {loading ? 'Import en cours…' : 'Importer cet événement'}
      </button>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function HistoricalImportPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)  // 1 = upload, 2 = validate
  const [meta, setMeta] = useState(null)
  const [parsed, setParsed] = useState(null)

  const handleNext = ({ nom, date, type, parsed: p }) => {
    setMeta({ nom, date, type })
    setParsed(p)
    setStep(2)
  }

  const handleCommit = async (payload) => {
    const result = await historiqueApi.commit(payload)
    navigate(`/events/${result.event_id}`)
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <IconHistory size={16} stroke={1.5} color="var(--text-muted)" />
        <h1 style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-primary)' }}>
          Import planning historique
        </h1>
        <div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
          {[1, 2].map((s) => (
            <div
              key={s}
              style={{
                width: 24, height: 24, borderRadius: '50%', fontSize: 11, fontWeight: 600,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: step >= s ? 'var(--accent)' : 'var(--bg-elevated)',
                color: step >= s ? '#fff' : 'var(--text-muted)',
                border: `1px solid ${step >= s ? 'var(--accent)' : 'var(--border)'}`,
              }}
            >
              {s}
            </div>
          ))}
        </div>
      </div>

      {step === 1 && <UploadStep onNext={handleNext} />}
      {step === 2 && parsed && (
        <ValidateStep
          meta={meta}
          parsed={parsed}
          onBack={() => setStep(1)}
          onCommit={handleCommit}
        />
      )}
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const labelStyle = {
  fontSize: 12,
  fontWeight: 500,
  color: 'var(--text-secondary)',
}

const inputStyle = {
  width: '100%',
  padding: '7px 10px',
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  color: 'var(--text-primary)',
  fontSize: 13,
  outline: 'none',
  boxSizing: 'border-box',
}

const btnPrimaryStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  padding: '8px 16px',
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  fontSize: 13,
  fontWeight: 500,
  cursor: 'pointer',
}

const btnGhostStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  padding: '6px 12px',
  background: 'none',
  color: 'var(--text-secondary)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  fontSize: 12,
  cursor: 'pointer',
}

const thStyle = {
  padding: '6px 10px',
  textAlign: 'left',
  fontSize: 11,
  fontWeight: 600,
  color: 'var(--text-muted)',
  borderBottom: '1px solid var(--border)',
  whiteSpace: 'nowrap',
}

const tdStyle = {
  padding: '5px 10px',
  borderBottom: '1px solid var(--border)',
  fontSize: 12,
  color: 'var(--text-secondary)',
}

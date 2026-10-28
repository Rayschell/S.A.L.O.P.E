import { useEffect, useRef, useState } from 'react'
import { logosApi } from '../../api/logos.js'
import { IconCheck, IconPhotoPlus, IconTrash, IconX } from '@tabler/icons-react'

const MAX_BYTES = 2 * 1024 * 1024
// Couleurs du thème LATEB : cadre, fond, Respo bar, Staff (cf. export_img.LATEB_THEME)
const LATEB_COULEURS = ['#ff6200', '#fbebcf', '#fde0b8', '#e65400']

/**
 * Modale de choix du logo de l'export PNG (bureau).
 * Le logo LATEB original (logo_id = null) est toujours proposé et non supprimable.
 * Import PNG/WebP ≤ 2 Mo ; supprimer un logo remet ses événements sur l'original.
 * Un logo importé peut imposer ses couleurs à l'export (thème dérivé côté backend).
 */
export default function LogoPicker({ currentLogoId, onSelect, onClose }) {
  const [logos, setLogos] = useState([])
  const [busy, setBusy] = useState(false)
  const [nom, setNom] = useState('')
  const [fichier, setFichier] = useState(null)
  const [fileError, setFileError] = useState(null)
  const fileInput = useRef(null)

  const reload = () => logosApi.list().then(setLogos)

  useEffect(() => {
    reload()
  }, [])

  const choose = async (logoId) => {
    if (logoId === currentLogoId) return
    setBusy(true)
    try {
      await onSelect(logoId)
    } finally {
      setBusy(false)
    }
  }

  const pickFile = (e) => {
    const f = e.target.files?.[0] ?? null
    setFileError(null)
    if (f && !['image/png', 'image/webp'].includes(f.type)) {
      setFileError('Formats acceptés : PNG ou WebP.')
      setFichier(null)
      return
    }
    if (f && f.size > MAX_BYTES) {
      setFileError('Image trop lourde (2 Mo maximum).')
      setFichier(null)
      return
    }
    setFichier(f)
    if (f && !nom.trim()) setNom(f.name.replace(/\.[^.]+$/, ''))
  }

  const upload = async () => {
    if (!fichier || !nom.trim()) return
    setBusy(true)
    try {
      const logo = await logosApi.upload(nom.trim(), fichier)
      setNom('')
      setFichier(null)
      if (fileInput.current) fileInput.current.value = ''
      await reload()
      await onSelect(logo.id)
    } finally {
      setBusy(false)
    }
  }

  const toggleCouleurs = async (logo) => {
    setBusy(true)
    try {
      const updated = await logosApi.setUtiliserCouleurs(logo.id, !logo.utiliser_couleurs)
      setLogos((prev) => prev.map((l) => (l.id === updated.id ? updated : l)))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (logo) => {
    if (!confirm(`Supprimer le logo « ${logo.nom} » ? Les événements qui l'utilisent reviendront au logo LATEB.`)) return
    setBusy(true)
    try {
      await logosApi.delete(logo.id)
      await reload()
      if (logo.id === currentLogoId) await onSelect(null)
    } finally {
      setBusy(false)
    }
  }

  const options = [{ id: null, nom: 'LATEB (original)', couleurs: LATEB_COULEURS, utiliser_couleurs: true }, ...logos]

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-mid)', borderRadius: 'var(--radius-lg)', padding: 24, width: '100%', maxWidth: 560, margin: '0 16px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <h2 style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>Logo de l'export</h2>
          <button onClick={onClose} style={iconBtnStyle} title="Fermer">
            <IconX size={16} stroke={1.5} />
          </button>
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14 }}>
          Logo affiché en haut du planning exporté en PNG pour cet événement.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
          {options.map((logo) => {
            const selected = logo.id === (currentLogoId ?? null)
            const couleurs = logo.utiliser_couleurs && logo.couleurs ? logo.couleurs : LATEB_COULEURS
            return (
              <div key={logo.id ?? 'default'} style={{ position: 'relative' }}>
                <button
                  onClick={() => choose(logo.id)}
                  disabled={busy}
                  aria-pressed={selected}
                  style={{
                    width: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'stretch',
                    gap: 8,
                    padding: 8,
                    background: 'var(--bg-elevated)',
                    border: selected ? '2px solid var(--accent)' : '1px solid var(--border)',
                    margin: selected ? 0 : 1,
                    borderRadius: 'var(--radius-md)',
                    cursor: busy ? 'wait' : 'pointer',
                    fontFamily: "'DM Sans', sans-serif",
                    textAlign: 'left',
                  }}
                >
                  {/* Cadre + fond du thème réellement utilisé à l'export */}
                  <div style={{ height: 96, borderRadius: 'var(--radius-sm)', background: couleurs[1], border: `3px solid ${couleurs[0]}`, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 8 }}>
                    <img
                      src={logosApi.imageUrl(logo.id)}
                      alt=""
                      style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
                    />
                  </div>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-primary)', fontWeight: selected ? 500 : 400, minWidth: 0 }}>
                    {selected && <IconCheck size={14} stroke={2} style={{ color: 'var(--accent)', flexShrink: 0 }} />}
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{logo.nom}</span>
                  </span>
                  <span style={{ display: 'flex', gap: 4 }} title="Cadre, fond, Respo bar, Staff">
                    {couleurs.map((c, i) => (
                      <span key={i} style={{ width: 16, height: 16, borderRadius: 4, background: c, border: '1px solid var(--border-mid)' }} />
                    ))}
                  </span>
                </button>
                {logo.id !== null && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6, fontSize: 12, color: logo.couleurs ? 'var(--text-secondary)' : 'var(--text-muted)', cursor: logo.couleurs && !busy ? 'pointer' : 'not-allowed' }}>
                    <input
                      type="checkbox"
                      checked={logo.utiliser_couleurs && !!logo.couleurs}
                      disabled={busy || !logo.couleurs}
                      onChange={() => toggleCouleurs(logo)}
                      style={{ accentColor: 'var(--accent)' }}
                    />
                    {logo.couleurs ? 'Utiliser les couleurs du logo' : 'Pas de couleur vive détectée'}
                  </label>
                )}
                {logo.id !== null && (
                  <button
                    onClick={() => remove(logo)}
                    disabled={busy}
                    title={`Supprimer « ${logo.nom} »`}
                    style={{ ...iconBtnStyle, position: 'absolute', top: 12, right: 12, background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', color: 'var(--red)' }}
                  >
                    <IconTrash size={14} stroke={1.5} />
                  </button>
                )}
              </div>
            )
          })}
        </div>

        <div style={{ marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
          <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 8 }}>Importer un logo</p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <input
              ref={fileInput}
              type="file"
              accept="image/png,image/webp"
              onChange={pickFile}
              style={{ fontSize: 12.5, color: 'var(--text-secondary)', flex: '1 1 200px', minWidth: 0 }}
            />
            <input
              type="text"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              placeholder="Nom (ex : Halloween)"
              style={{ ...inputStyle, flex: '1 1 140px' }}
            />
            <button
              onClick={upload}
              disabled={!fichier || !nom.trim() || busy}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                background: 'var(--accent)', color: '#fff', border: 'none',
                borderRadius: 'var(--radius-sm)', padding: '7px 12px', fontSize: 12.5,
                fontFamily: "'DM Sans', sans-serif",
                opacity: !fichier || !nom.trim() || busy ? 0.5 : 1,
                cursor: !fichier || !nom.trim() || busy ? 'not-allowed' : 'pointer',
              }}
            >
              <IconPhotoPlus size={14} stroke={1.5} />
              {busy ? 'Envoi…' : 'Importer'}
            </button>
          </div>
          <p style={{ fontSize: 12, color: fileError ? 'var(--red)' : 'var(--text-muted)', marginTop: 6 }}>
            {fileError ?? 'PNG ou WebP, 2 Mo maximum. Fond transparent conseillé ; les bords vides sont rognés automatiquement.'}
          </p>
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

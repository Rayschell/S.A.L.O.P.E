import { useEffect, useState } from 'react'
import { eventsApi } from '../../api/events.js'
import NameResolutionModal from './NameResolutionModal.jsx'
import { toast } from '../ui/Toaster.jsx'
import { IconCopy, IconLink, IconTrash, IconUserQuestion } from '@tabler/icons-react'

/**
 * Alternative à l'import CSV : lien d'inscription public (/dispo/:token).
 * Gère le toggle « inscriptions ouvertes », la deadline optionnelle, la copie
 * du lien, et la résolution des soumissions dont le nom n'a pas été reconnu
 * (réutilise NameResolutionModal, même shape que le flux CSV).
 */
export default function PublicPollAdmin({ eventId, onImported, disabled }) {
  const [link, setLink] = useState(null) // {public_token, inscriptions_ouvertes, inscriptions_deadline, pending_count, slots_count}
  const [submissions, setSubmissions] = useState([])
  const [deadline, setDeadline] = useState('')
  const [busy, setBusy] = useState(false)
  const [resolving, setResolving] = useState(null) // soumission ouverte dans le modal
  const [copied, setCopied] = useState(false)

  const load = async () => {
    const data = await eventsApi.getPublicLink(eventId)
    setLink(data)
    setDeadline(data.inscriptions_deadline ? data.inscriptions_deadline.slice(0, 16) : '')
    if (data.pending_count > 0) {
      setSubmissions(await eventsApi.listPublicSubmissions(eventId))
    } else {
      setSubmissions([])
    }
  }

  useEffect(() => { load() }, [eventId])

  const save = async (ouvertes) => {
    setBusy(true)
    try {
      const data = await eventsApi.updatePublicLink(eventId, {
        inscriptions_ouvertes: ouvertes,
        inscriptions_deadline: deadline || null,
      })
      setLink((prev) => ({ ...data, pending_count: prev?.pending_count ?? data.pending_count }))
    } finally {
      setBusy(false)
    }
  }

  const pollUrl = link?.public_token ? `${window.location.origin}/dispo/${link.public_token}` : null

  const copyLink = async () => {
    await navigator.clipboard.writeText(pollUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleResolved = async (resolutions) => {
    await eventsApi.resolvePublicSubmissions(eventId, resolutions)
    setResolving(null)
    toast.success('Soumission résolue')
    await load()
    onImported()
  }

  const ignore = async (sub) => {
    if (!confirm(`Ignorer la réponse de « ${sub.csv_name} » ?`)) return
    await eventsApi.deletePublicSubmission(eventId, sub.id)
    await load()
  }

  if (!link) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, borderTop: '1px solid var(--border)', paddingTop: 20, marginTop: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <IconLink size={15} stroke={1.5} style={{ color: 'var(--accent)' }} />
        <h3 style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>
          Lien d'inscription public
        </h3>
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: -8 }}>
        Alternative au CSV : les membres remplissent leurs dispos directement, sans compte.
        Le lien est permanent — le bouton « Inscriptions ouvertes » contrôle seulement si
        le formulaire peut être rempli. Un nom non reconnu est mis en attente ci-dessous.
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 13, color: 'var(--text-secondary)', cursor: disabled || link.slots_count === 0 ? 'not-allowed' : 'pointer' }}>
          <input
            type="checkbox"
            checked={link.inscriptions_ouvertes}
            disabled={disabled || busy || link.slots_count === 0}
            onChange={(e) => save(e.target.checked)}
            style={{ accentColor: 'var(--accent)' }}
          />
          Inscriptions ouvertes
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12.5, color: 'var(--text-muted)' }}>
          Limite :
          <input
            type="datetime-local"
            value={deadline}
            disabled={disabled || busy || link.slots_count === 0}
            onChange={(e) => setDeadline(e.target.value)}
            onBlur={() => link.inscriptions_ouvertes && save(true)}
            style={{
              background: 'var(--bg-elevated)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)', padding: '5px 8px', fontSize: 12,
              color: 'var(--text-primary)', fontFamily: "'DM Sans', sans-serif", outline: 'none',
            }}
          />
        </label>
      </div>

      {link.slots_count === 0 && (
        <p style={{ fontSize: 12.5, color: 'var(--amber)', marginTop: -6 }}>
          Aucun créneau sur cet événement — importez un CSV pour pouvoir ouvrir les
          inscriptions (les créneaux se définissent normalement à la création de l'événement).
        </p>
      )}

      {pollUrl && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <code style={{
            fontSize: 12, fontFamily: 'DM Mono, monospace', color: 'var(--text-secondary)',
            background: 'var(--bg-elevated)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)', padding: '6px 10px',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {pollUrl}
          </code>
          <button
            onClick={copyLink}
            title="Copier le lien"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5, padding: '6px 10px',
              fontSize: 12, background: 'var(--bg-high)', color: copied ? 'var(--green)' : 'var(--text-secondary)',
              border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
              fontFamily: "'DM Sans', sans-serif", flexShrink: 0,
            }}
          >
            <IconCopy size={13} stroke={1.5} />
            {copied ? 'Copié ✓' : 'Copier'}
          </button>
        </div>
      )}

      {submissions.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
            <IconUserQuestion size={14} stroke={1.5} style={{ color: 'var(--amber)' }} />
            <span style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>
              {submissions.length} nom(s) en attente de validation
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {submissions.map((sub) => (
              <div key={sub.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{sub.csv_name}</span>
                <span style={{ fontSize: 11, fontFamily: 'DM Mono, monospace', color: 'var(--text-muted)' }}>
                  {new Date(sub.updated_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                </span>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                  <button
                    onClick={() => setResolving(sub)}
                    disabled={disabled}
                    style={{
                      padding: '4px 10px', fontSize: 12, background: 'var(--accent-soft)',
                      color: 'var(--accent)', border: '1px solid var(--accent)',
                      borderRadius: 'var(--radius-sm)', cursor: disabled ? 'not-allowed' : 'pointer',
                      fontFamily: "'DM Sans', sans-serif",
                    }}
                  >
                    Résoudre
                  </button>
                  <button
                    onClick={() => ignore(sub)}
                    disabled={disabled}
                    title="Ignorer cette réponse"
                    style={{ background: 'none', border: 'none', cursor: disabled ? 'not-allowed' : 'pointer', color: 'var(--red)', display: 'flex', alignItems: 'center', padding: 4 }}
                  >
                    <IconTrash size={14} stroke={1.5} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {resolving && (
        <NameResolutionModal
          pending={[resolving]}
          onResolved={handleResolved}
          onCancel={() => setResolving(null)}
        />
      )}
    </div>
  )
}

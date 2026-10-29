import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { publicApi } from '../api/publicClient.js'
import { IconGlassFull, IconCheck, IconQuestionMark, IconX } from '@tabler/icons-react'

const STATUTS = [
  { value: 'yes', label: 'Dispo', icon: IconCheck, color: 'var(--green)', soft: 'var(--green-soft)' },
  { value: 'maybe', label: 'Peut-être', icon: IconQuestionMark, color: 'var(--amber)', soft: 'var(--amber-soft)' },
  { value: 'no', label: 'Pas dispo', icon: IconX, color: 'var(--red)', soft: 'var(--red-soft)' },
]

const CLOSED_MESSAGES = {
  closed: 'Les inscriptions sont fermées pour cet événement.',
  deadline: 'La date limite d’inscription est passée.',
}

/**
 * Page publique (sans compte) : un membre saisit son prénom + nom et coche
 * sa disponibilité par créneau. Re-soumettre avec le même nom écrase les
 * réponses précédentes.
 */
export default function PublicPollPage() {
  const { token } = useParams()
  const [poll, setPoll] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [nom, setNom] = useState('')
  const [reponses, setReponses] = useState({}) // {creneau_id: 'yes'|'maybe'|'no'}
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null) // null | 'matched' | 'pending'

  useEffect(() => {
    publicApi
      .getPoll(token)
      .then(setPoll)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false))
  }, [token])

  const eventDate = useMemo(() => {
    if (!poll) return ''
    return new Date(poll.event_date).toLocaleDateString('fr-FR', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    })
  }, [poll])

  const fmtHour = (iso) =>
    new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', hour12: false })

  const setAll = (statut) =>
    setReponses(Object.fromEntries(poll.slots.map((s) => [s.id, statut])))

  // Aucune réponse présélectionnée : chaque créneau doit être renseigné
  const nbSansReponse = poll ? poll.slots.filter((s) => !reponses[s.id]).length : 0
  const cannotSubmit = !poll?.ouvert || !nom.trim() || nbSansReponse > 0 || busy

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (cannotSubmit) return
    setBusy(true)
    setError('')
    try {
      const payload = {
        nom: nom.trim(),
        reponses: poll.slots.map((s) => ({ creneau_id: s.id, statut: reponses[s.id] })),
      }
      const res = await publicApi.submit(token, payload)
      setResult(res.status)
    } catch (err) {
      const status = err.response?.status
      if (status === 403 || status === 410) {
        setError(CLOSED_MESSAGES[status === 410 ? 'deadline' : 'closed'])
      } else {
        setError(err.response?.data?.detail || 'Une erreur est survenue, réessayez.')
      }
    } finally {
      setBusy(false)
    }
  }

  const page = (children) => (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)', display: 'flex', justifyContent: 'center', padding: '32px 16px' }}>
      <div style={{ width: '100%', maxWidth: 480 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
          <div style={{ width: 28, height: 28, background: 'var(--accent)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <IconGlassFull size={14} color="#fff" stroke={1.8} />
          </div>
          <span style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>S.A.L.O.P.E</span>
        </div>
        {children}
      </div>
    </div>
  )

  if (loading) {
    return page(<p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Chargement…</p>)
  }

  if (notFound) {
    return page(
      <div style={cardStyle}>
        <h1 style={titleStyle}>Sondage introuvable</h1>
        <p style={mutedStyle}>Ce lien d'inscription n'existe pas ou a été désactivé.</p>
      </div>
    )
  }

  if (result) {
    return page(
      <div style={cardStyle}>
        <h1 style={titleStyle}>
          {result === 'matched' ? 'Disponibilités enregistrées ✓' : 'Réponse envoyée ✓'}
        </h1>
        <p style={{ ...mutedStyle, marginBottom: 16 }}>
          {result === 'matched'
            ? 'Merci ! Tes disponibilités ont bien été prises en compte.'
            : 'Ton nom n’a pas été reconnu automatiquement : ta réponse sera validée par le bureau, rien d’autre à faire.'}
        </p>
        <button
          onClick={() => setResult(null)}
          style={{ ...primaryBtnStyle, background: 'var(--bg-high)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
        >
          Modifier mes réponses
        </button>
      </div>
    )
  }

  return page(
    <div style={cardStyle}>
      <h1 style={titleStyle}>{poll.event_nom}</h1>
      <p style={{ ...mutedStyle, marginBottom: 18, textTransform: 'capitalize' }}>{eventDate}</p>

      {!poll.ouvert && (
        <div style={bannerStyle}>{CLOSED_MESSAGES[poll.raison_fermeture] || CLOSED_MESSAGES.closed}</div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div>
          <label style={labelStyle}>Prénom Nom</label>
          <input
            type="text"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            required
            maxLength={100}
            disabled={!poll.ouvert}
            placeholder="Camille Dupont"
            style={inputStyle}
          />
        </div>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <label style={{ ...labelStyle, marginBottom: 0 }}>Mes disponibilités</label>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
              {[
                { value: 'yes', label: 'Dispo partout' },
                { value: 'no', label: 'Pas dispo partout' },
              ].map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  disabled={!poll.ouvert}
                  onClick={() => setAll(value)}
                  style={{
                    padding: '4px 8px', fontSize: 11.5, borderRadius: 'var(--radius-sm)',
                    fontFamily: "'DM Sans', sans-serif",
                    cursor: poll.ouvert ? 'pointer' : 'not-allowed',
                    background: 'transparent',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border)',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {poll.slots.map((slot) => (
              <div
                key={slot.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)', padding: '8px 10px',
                }}
              >
                <span style={{ fontSize: 13, fontFamily: 'DM Mono, monospace', color: 'var(--text-primary)', minWidth: 96 }}>
                  {fmtHour(slot.heure_debut)} – {fmtHour(slot.heure_fin)}
                </span>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
                  {STATUTS.map(({ value, label, icon: Icon, color, soft }) => {
                    const active = reponses[slot.id] === value
                    return (
                      <button
                        key={value}
                        type="button"
                        disabled={!poll.ouvert}
                        onClick={() => setReponses((r) => ({ ...r, [slot.id]: value }))}
                        title={label}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                          padding: '5px 9px', fontSize: 12, borderRadius: 'var(--radius-sm)',
                          fontFamily: "'DM Sans', sans-serif",
                          cursor: poll.ouvert ? 'pointer' : 'not-allowed',
                          background: active ? soft : 'transparent',
                          color: active ? color : 'var(--text-muted)',
                          border: `1px solid ${active ? color : 'var(--border)'}`,
                          transition: 'all 100ms ease',
                        }}
                      >
                        <Icon size={13} stroke={2} />
                        {label}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {error && (
          <div style={{ background: 'var(--red-soft)', border: '1px solid rgba(240, 82, 82, 0.2)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', fontSize: 12, color: 'var(--red)' }}>
            {error}
          </div>
        )}

        {poll.ouvert && nbSansReponse > 0 && (
          <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>
            {nbSansReponse === poll.slots.length
              ? 'Indique ta disponibilité pour chaque créneau.'
              : `Encore ${nbSansReponse} créneau${nbSansReponse > 1 ? 'x' : ''} sans réponse.`}
          </p>
        )}

        <button
          type="submit"
          disabled={cannotSubmit}
          style={{
            ...primaryBtnStyle,
            cursor: cannotSubmit ? 'not-allowed' : 'pointer',
            opacity: cannotSubmit ? 0.55 : 1,
          }}
        >
          {busy ? 'Envoi…' : 'Envoyer mes disponibilités'}
        </button>
        <p style={{ fontSize: 11.5, color: 'var(--text-muted)', textAlign: 'center', marginTop: -6 }}>
          Déjà répondu ? Re-soumettre avec le même nom remplace tes réponses.
        </p>
      </form>
    </div>
  )
}

const cardStyle = {
  background: 'var(--bg-surface)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-lg)',
  padding: '28px 24px',
}

const titleStyle = {
  fontSize: 19,
  fontWeight: 600,
  color: 'var(--text-primary)',
  marginBottom: 4,
}

const mutedStyle = { fontSize: 13, color: 'var(--text-muted)' }

const bannerStyle = {
  background: 'var(--amber-soft)',
  border: '1px solid var(--amber)',
  borderRadius: 'var(--radius-sm)',
  padding: '10px 12px',
  fontSize: 12.5,
  color: 'var(--amber)',
  marginBottom: 16,
}

const labelStyle = {
  display: 'block',
  fontSize: 11,
  color: 'var(--text-muted)',
  fontFamily: 'DM Mono, monospace',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  marginBottom: 6,
}

const inputStyle = {
  width: '100%',
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border-mid)',
  borderRadius: 'var(--radius-sm)',
  padding: '8px 12px',
  fontSize: 13,
  color: 'var(--text-primary)',
  outline: 'none',
  fontFamily: "'DM Sans', sans-serif",
}

const primaryBtnStyle = {
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  padding: '10px 14px',
  fontSize: 13,
  fontWeight: 500,
  fontFamily: "'DM Sans', sans-serif",
  transition: 'background 120ms ease',
}

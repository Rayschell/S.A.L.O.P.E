import { useMemo } from 'react'
import { IconUserOff, IconUserCheck } from '@tabler/icons-react'

/**
 * Shows all members who responded to this event (have at least one availability
 * entry). Bureau can toggle each member as excluded from planning generation.
 */
export default function ParticipantsFilter({
  members,
  availabilities,
  excludedIds,
  onToggle,
  onClearAll,
  disabled,
}) {
  // Members who have at least one availability entry for this event
  const respondents = useMemo(() => {
    const withAvail = new Set(availabilities.map((a) => a.membre_id))
    return members
      .filter((m) => withAvail.has(m.id))
      .sort((a, b) => `${a.nom} ${a.prenom}`.localeCompare(`${b.nom} ${b.prenom}`))
  }, [members, availabilities])

  const excludedCount = excludedIds.size

  if (respondents.length === 0) {
    return (
      <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
        Aucune disponibilité importée pour cet événement. Importez d'abord le CSV Strawpoll.
      </p>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <p style={{ fontSize: 15, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
        Sélectionnez les membres à <strong>exclure</strong> du planning généré automatiquement.
        Les membres exclus ne seront pas placés par le solveur, mais leurs affectations
        manuelles existantes sont conservées.
      </p>

      {excludedCount > 0 && (
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '5px 10px',
          background: 'rgba(240, 82, 82,0.10)',
          border: '1px solid rgba(240, 82, 82,0.25)',
          borderRadius: 6,
          fontSize: 14,
          color: 'var(--red)',
          alignSelf: 'flex-start',
        }}>
          <IconUserOff size={13} stroke={1.5} />
          {excludedCount} membre{excludedCount > 1 ? 's' : ''} exclu{excludedCount > 1 ? 's' : ''}
          <button
            onClick={onClearAll}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--text-muted)', marginLeft: 4 }}
          >
            Tout réinclure
          </button>
        </div>
      )}

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
        gap: 6,
      }}>
        {respondents.map((m) => {
          const excluded = excludedIds.has(m.id)
          return (
            <button
              key={m.id}
              onClick={() => !disabled && onToggle(m.id)}
              disabled={disabled}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '7px 10px',
                background: excluded
                  ? 'rgba(240, 82, 82,0.08)'
                  : 'var(--bg-elevated)',
                border: `1px solid ${excluded ? 'rgba(240, 82, 82,0.30)' : 'var(--border)'}`,
                borderRadius: 6,
                cursor: disabled ? 'default' : 'pointer',
                textAlign: 'left',
                transition: 'all 120ms ease',
                opacity: disabled ? 0.6 : 1,
              }}
            >
              <span style={{
                width: 18,
                height: 18,
                borderRadius: '50%',
                border: `2px solid ${excluded ? 'var(--red)' : 'var(--border-mid)'}`,
                background: excluded ? 'rgba(240, 82, 82,0.15)' : 'transparent',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>
                {excluded
                  ? <IconUserOff size={10} stroke={2} color="var(--red)" />
                  : <IconUserCheck size={10} stroke={2} color="var(--text-muted)" />
                }
              </span>
              <span style={{
                fontSize: 15,
                color: excluded ? 'var(--red)' : 'var(--text-primary)',
                textDecoration: excluded ? 'line-through' : 'none',
                fontWeight: excluded ? 400 : 400,
              }}>
                {m.prenom} {m.nom}
              </span>
              {m.roles?.includes('bureau') && (
                <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-muted)' }}>bureau</span>
              )}
            </button>
          )
        })}
      </div>

      <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
        {respondents.length - excludedCount} / {respondents.length} membres inclus dans la génération
      </p>
    </div>
  )
}

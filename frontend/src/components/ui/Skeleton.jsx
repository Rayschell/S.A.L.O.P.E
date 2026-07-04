export default function Skeleton({ width, height = 16, borderRadius = 6, style = {} }) {
  return (
    <div
      style={{
        width: width || '100%',
        height,
        borderRadius,
        background: 'var(--bg-high)',
        animation: 'skeleton-pulse 1.5s ease-in-out infinite',
        flexShrink: 0,
        ...style,
      }}
    />
  )
}

export function SkeletonText({ lines = 1, style = {} }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, ...style }}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} height={12} width={i === lines - 1 && lines > 1 ? '70%' : '100%'} />
      ))}
    </div>
  )
}

export function SkeletonCard({ style = {} }) {
  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        padding: '16px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        ...style,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 7 }}>
          <Skeleton height={14} width="58%" />
          <Skeleton height={11} width="38%" />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5, alignItems: 'flex-end' }}>
          <Skeleton height={20} width={62} borderRadius={999} />
          <Skeleton height={20} width={62} borderRadius={999} />
        </div>
      </div>
      <Skeleton height={30} borderRadius={6} />
    </div>
  )
}

export function SkeletonRow({ style = {} }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 12px',
        borderBottom: '1px solid var(--border)',
        ...style,
      }}
    >
      <Skeleton width={28} height={28} borderRadius="50%" />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 5 }}>
        <Skeleton height={12} width="45%" />
        <Skeleton height={10} width="28%" />
      </div>
      <Skeleton height={20} width={50} borderRadius={999} />
      <Skeleton height={20} width={50} borderRadius={999} />
    </div>
  )
}

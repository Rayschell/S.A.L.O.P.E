// Position d'un popup `position: fixed` sous l'élément cliqué, gardé dans l'écran
// (au-dessus de l'élément s'il n'y a pas la place en dessous).
export function popupPos(rect, width, height) {
  const x = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8))
  const below = rect.bottom + 6
  const y = below + height > window.innerHeight - 8 ? Math.max(8, rect.top - height - 6) : below
  return { x, y }
}

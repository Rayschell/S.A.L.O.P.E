"""
Thème de couleurs de l'export PNG dérivé d'un logo importé.

On extrait les teintes vives dominantes (hors transparence et hors contours
quasi noirs / quasi blancs), puis on les répartit sur les rôles de l'export :
cadre, fond, pastilles Respo bar / Staff, textes. Chaque couleur de texte est
ajustée jusqu'à atteindre un contraste WCAG suffisant.
"""
from __future__ import annotations

import colorsys
import io
from typing import Dict, List, Optional, Tuple

from PIL import Image

RGB = Tuple[int, int, int]

SAMPLE_SIDE = 160
MIN_SATURATION = 0.35
MIN_HUE_GAP = 40  # degrés : en dessous, deux teintes ne se distinguent pas assez


# ---------------------------------------------------------------------------
# Outils couleur
# ---------------------------------------------------------------------------


def _hls(c: RGB) -> Tuple[float, float, float]:
    return colorsys.rgb_to_hls(*(v / 255 for v in c))


def _from_hls(h: float, l: float, s: float) -> RGB:
    return tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, max(0, min(1, l)), max(0, min(1, s))))


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    """t = 0 → a, t = 1 → b."""
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _luminance(c: RGB) -> float:
    def ch(v: int) -> float:
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = c
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: RGB, b: RGB) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _darken_until(c: RGB, against: RGB, ratio: float) -> RGB:
    h, l, s = _hls(c)
    while contrast(c, against) < ratio and l > 0:
        l -= 0.02
        c = _from_hls(h, l, s)
    return c


def _lighten_until(c: RGB, against: RGB, ratio: float) -> RGB:
    h, l, s = _hls(c)
    while contrast(c, against) < ratio and l < 1:
        l += 0.02
        c = _from_hls(h, l, s)
    return c


def _hue_gap(a: RGB, b: RGB) -> float:
    d = abs(_hls(a)[0] - _hls(b)[0]) * 360
    return min(d, 360 - d)


def hex_color(c: RGB) -> str:
    return "#%02x%02x%02x" % c


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _clusters(pixels: List[RGB], n: int) -> List[Tuple[int, RGB]]:
    """Regroupe les pixels en ≤ n couleurs, triées par nombre de pixels."""
    if not pixels:
        return []
    strip = Image.new("RGB", (len(pixels), 1))
    strip.putdata(pixels)
    q = strip.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    palette = q.getpalette()
    out = []
    for count, idx in sorted(q.getcolors(), reverse=True):
        out.append((count, tuple(palette[idx * 3: idx * 3 + 3])))
    return out


def _accents(pixels: List[RGB]) -> List[RGB]:
    """Teintes vives distinctes, de la plus marquante à la moins marquante."""
    groups: List[Tuple[float, RGB]] = []  # (score, couleur représentative)
    for count, c in _clusters(pixels, 10):
        h, l, s = _hls(c)
        if s < MIN_SATURATION or not 0.2 < l < 0.8:
            continue
        score = count * s
        for i, (g_score, g_c) in enumerate(groups):
            if _hue_gap(c, g_c) < 20:
                groups[i] = (g_score + score, g_c)
                break
        else:
            groups.append((score, c))
    groups.sort(key=lambda g: g[0], reverse=True)
    return [c for _, c in groups]


def extract_theme(png: bytes) -> Optional[Dict[str, RGB]]:
    """Thème complet de l'export, ou None si le logo n'a aucune couleur vive."""
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    img.thumbnail((SAMPLE_SIDE, SAMPLE_SIDE))
    opaque = [p[:3] for p in img.get_flattened_data() if p[3] >= 200]
    if not opaque:
        return None

    accents = _accents(opaque)
    if not accents:
        return None
    primary = accents[0]
    secondary = next((c for c in accents[1:] if _hue_gap(c, primary) >= MIN_HUE_GAP), None)

    # Fond : la couleur claire du logo si elle est assez présente, sinon un
    # voile très clair de la couleur principale.
    lights = [c for c in opaque if 0.8 < _hls(c)[1] < 0.98]
    if len(lights) >= 0.04 * len(opaque):
        h, _, s = _hls(_clusters(lights, 4)[0][1])
        bg = _from_hls(h, 0.9, min(s, 0.6))
    else:
        h, _, _ = _hls(primary)
        bg = _from_hls(h, 0.93, 0.55)

    # Teinte sombre → « Respo bar » (texte blanc) mais aussi cadre, « LATEB » et
    # textes, comme l'orange du thème LATEB. Teinte claire → « Staff » (texte
    # foncé) et bandeaux. Ainsi les deux couleurs du logo apparaissent même sur
    # un afterwork sans respo.
    if secondary is None:
        respo_base, staff_base = primary, _from_hls(_hls(primary)[0], 0.72, _hls(primary)[2])
    elif _hls(primary)[1] <= _hls(secondary)[1]:
        respo_base, staff_base = primary, secondary
    else:
        respo_base, staff_base = secondary, primary

    white = (255, 255, 255)
    rh, _, _ = _hls(respo_base)
    sh, _, _ = _hls(staff_base)

    # Texte : nuance très sombre de la teinte du cadre, jamais un gris neutre
    text = _darken_until(_from_hls(rh, 0.12, 0.4), bg, 12)
    text_muted = _darken_until(_from_hls(rh, 0.32, 0.5), bg, 5)

    respo = _darken_until(respo_base, white, 4.5)
    staff_text = _from_hls(sh, 0.12, 0.6)
    staff = _lighten_until(staff_base, staff_text, 4.5)

    frame = respo_base
    brand = _darken_until(respo_base, bg, 3)

    return {
        "frame": frame,
        "bg": bg,
        "card": _mix(bg, white, 0.6),
        "card_border": _mix(bg, text, 0.12),
        "row_alt": _mix(bg, white, 0.3),
        "band": _mix(_mix(bg, white, 0.2), staff_base, 0.18),
        "rule": _mix(bg, text, 0.07),
        "text": text,
        "text_muted": text_muted,
        "brand": brand,
        "respo": respo,
        "respo_text": white,
        "staff": staff,
        "staff_text": staff_text,
        "shadow": text,
    }


def theme_swatches(theme: Dict[str, RGB]) -> List[str]:
    """Aperçu compact pour l'interface : cadre, fond, bandeaux, texte LATEB.

    Pas de Respo bar / Staff : les bulles gardent les couleurs LATEB à l'export.
    """
    return [hex_color(theme[k]) for k in ("frame", "bg", "band", "brand")]


def logo_et_theme(db, event) -> Tuple[Optional[bytes], Optional[Dict[str, RGB]]]:
    """(logo PNG, thème) de l'événement — même règle pour l'export et l'aperçu.

    Pas de logo → (None, None) : logo et thème LATEB. Logo importé → son PNG,
    et son thème seulement si `utiliser_couleurs` (sinon thème LATEB).
    """
    from ..models.models import Logo

    logo = db.get(Logo, event.logo_id) if event.logo_id else None
    if logo is None:
        return None, None
    return logo.contenu, extract_theme(logo.contenu) if logo.utiliser_couleurs else None

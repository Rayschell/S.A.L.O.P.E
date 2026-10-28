"""
Server-side PNG export of the planning grid using Pillow.

Charte LATEB (cf. carte.lateb.eu + logo) : fond crème, cadre orange,
police Baloo 2. Respo bar = orange, staff = jaune bière.
Rendu en x2 pour rester net sur mobile (partage WhatsApp / Discord).
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..models.models import Assignment, AssignmentTypeEnum, Event, Member, Slot

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
FONT_PATH = ASSETS_DIR / "fonts" / "Baloo2.ttf"
LOGO_PATH = ASSETS_DIR / "lateb_logo.png"

# Toutes les dimensions ci-dessous sont en px logiques, multipliées par SCALE.
SCALE = 2

# ---------------------------------------------------------------------------
# Couleurs
# ---------------------------------------------------------------------------
# Thème LATEB (logo original). Un logo importé peut fournir le sien via
# services/logo_theme.extract_theme, avec les mêmes clés.
LATEB_THEME = {
    "frame": (255, 98, 0),          # orange LATEB (#ff6200)
    "bg": (251, 235, 207),          # crème (#fbebcf)
    "card": (255, 250, 240),
    "card_border": (234, 212, 172),
    "row_alt": (253, 243, 224),
    "band": (253, 224, 184),        # en-tête + ligne total
    "rule": (240, 222, 190),
    "text": (42, 28, 14),           # brun très sombre, issu du trait du logo
    "text_muted": (122, 74, 18),    # brun (#7a4a12), lisible sur crème
    "brand": (230, 84, 0),          # orange un cran plus sombre pour le texte
    "respo": (217, 72, 0),          # orange profond, texte blanc
    "respo_text": (255, 255, 255),
    "staff": (253, 196, 14),        # jaune bière du logo (#fdc40e)
    "staff_text": (74, 42, 6),
    "shadow": (122, 74, 18),
}
SHADOW_ALPHA = 40

# Les bulles de shift gardent toujours les couleurs LATEB, quel que soit le
# thème du logo : seul l'habillage (cadre, fond, textes, bandeaux) change.
SHIFT_KEYS = ("respo", "respo_text", "staff", "staff_text")

FRAME = 6
MARGIN = 32
LOGO_H = 92
HEADER_GAP = 24
CARD_RADIUS = 16
CARD_PAD = 8
COL_W = 104
ROW_H = 38
HEAD_H = 52
NAME_COL_MIN = 180
PILL_INSET_X = 6
PILL_INSET_Y = 5
PILL_RADIUS = 9

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _font(size: int, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    try:
        font = ImageFont.truetype(str(FONT_PATH), size * SCALE)
        font.set_variation_by_name(weight)
        return font
    except OSError:
        return ImageFont.load_default(size * SCALE)


_F_BRAND = _font(22, "ExtraBold")
_F_TITLE = _font(34, "Bold")
_F_SUBTITLE = _font(17, "Medium")
_F_HEAD = _font(15, "Bold")
_F_HEAD_SMALL = _font(12, "Medium")
_F_NAME = _font(15, "Medium")
_F_PILL = _font(14, "Bold")
_F_TOTAL = _font(15, "Bold")
_F_SMALL = _font(13, "Medium")


def _s(v: float) -> int:
    return round(v * SCALE)


def _heure(dt: datetime) -> str:
    return f"{dt.hour}h" if dt.minute == 0 else f"{dt.hour}h{dt.minute:02d}"


def _date_longue(dt: datetime) -> str:
    return f"{JOURS[dt.weekday()].capitalize()} {dt.day} {MOIS[dt.month - 1]} {dt.year}"


def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    return draw.textlength(text, font=font) / SCALE


def _load_logo(height: int, logo_png: bytes | None = None) -> Image.Image | None:
    """Logo de l'événement (PNG normalisé) ou, à défaut, le logo LATEB original.

    Tient dans une boîte `height` de haut et 2.4 × `height` de large, pour
    qu'un logo très horizontal n'écrase pas le titre.
    """
    try:
        source = io.BytesIO(logo_png) if logo_png else LOGO_PATH
        logo = Image.open(source).convert("RGBA")
    except OSError:
        return None
    ratio = min(height / logo.height, height * 2.4 / logo.width)
    size = (max(1, round(logo.width * ratio)), max(1, round(logo.height * ratio)))
    return logo.resize(size, Image.LANCZOS)


def export_planning_png(
    event: Event,
    slots: List[Slot],
    members: List[Member],
    assignments_db: List[Assignment],
    logo_png: bytes | None = None,
    theme: Dict[str, Tuple[int, int, int]] | None = None,
) -> bytes:
    """
    Render the planning as a PNG image and return the raw bytes.
    """
    t = {**(theme or LATEB_THEME), **{k: LATEB_THEME[k] for k in SHIFT_KEYS}}
    asgn_map: Dict[Tuple[int, int], str] = {}
    slot_counts: Dict[int, int] = {}
    for a in assignments_db:
        asgn_map[(a.membre_id, a.creneau_id)] = a.type.value
        slot_counts[a.creneau_id] = slot_counts.get(a.creneau_id, 0) + 1

    assigned_member_ids = {a.membre_id for a in assignments_db}
    visible_members = [m for m in members if m.id in assigned_member_ids]
    if not visible_members:
        visible_members = members

    # Tri "en escalier" : ceux qui commencent tôt en haut, puis à début égal
    # ceux qui finissent tôt. Le nom ne sert qu'à départager.
    slot_idx = {s.id: i for i, s in enumerate(slots)}
    member_span: Dict[int, Tuple[int, int]] = {}
    for a in assignments_db:
        i = slot_idx.get(a.creneau_id)
        if i is None:
            continue
        lo, hi = member_span.get(a.membre_id, (i, i))
        member_span[a.membre_id] = (min(lo, i), max(hi, i))
    visible_members = sorted(
        visible_members,
        key=lambda m: (*member_span.get(m.id, (len(slots), len(slots))), m.nom, m.prenom),
    )

    # Une soirée qui passe minuit (même jusqu'au matin) reste une seule
    # soirée : on n'affiche les jours que si l'événement dépasse 24h.
    multi_jours = bool(slots) and (
        slots[-1].heure_fin - slots[0].heure_debut > timedelta(hours=24)
    )

    # ------------------------------------------------------------------
    # Mesures
    # ------------------------------------------------------------------
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    names = [f"{m.prenom} {m.nom}" for m in visible_members]
    name_col_w = max(
        [NAME_COL_MIN] + [_text_w(measure, n, _F_NAME) + 2 * 16 for n in names]
    )

    title = event.nom
    subtitle = _date_longue(event.date)
    if slots:
        subtitle += f"  ·  {_heure(slots[0].heure_debut)} – {_heure(slots[-1].heure_fin)}"

    table_w = name_col_w + len(slots) * COL_W
    card_w = table_w + 2 * CARD_PAD
    header_text_w = max(
        _text_w(measure, title, _F_TITLE), _text_w(measure, subtitle, _F_SUBTITLE)
    )
    logo = _load_logo(_s(LOGO_H), logo_png)
    logo_w = logo.width / SCALE if logo else 0
    content_w = max(card_w, logo_w + 20 + header_text_w)
    # Si le titre est plus large que la grille, on élargit les créneaux
    # plutôt que de laisser un vide à droite de la carte.
    col_w = COL_W
    if slots and content_w > card_w:
        col_w = COL_W + (content_w - card_w) / len(slots)
    card_w = content_w

    head_h = HEAD_H + (16 if multi_jours else 0)
    table_h = head_h + len(visible_members) * ROW_H + ROW_H
    card_h = table_h + 2 * CARD_PAD

    width = FRAME * 2 + MARGIN * 2 + content_w
    header_top = FRAME + MARGIN
    card_top = header_top + LOGO_H + HEADER_GAP
    height = card_top + card_h + MARGIN + FRAME

    img = Image.new("RGB", (_s(width), _s(height)), t["frame"])
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [_s(FRAME), _s(FRAME), _s(width - FRAME) - 1, _s(height - FRAME) - 1],
        fill=t["bg"],
    )

    # ------------------------------------------------------------------
    # En-tête : logo + LATEB + nom de l'event + date
    # ------------------------------------------------------------------
    left = FRAME + MARGIN
    if logo:
        # Centré verticalement dans la hauteur réservée (logos plus larges que hauts)
        img.paste(logo, (_s(left), _s(header_top) + (_s(LOGO_H) - logo.height) // 2), logo)
    text_x = left + (logo_w + 20 if logo else 0)
    draw.text((_s(text_x), _s(header_top + 4)), "LATEB", font=_F_BRAND, fill=t["brand"])
    draw.text((_s(text_x), _s(header_top + 26)), title, font=_F_TITLE, fill=t["text"])
    draw.text(
        (_s(text_x), _s(header_top + 66)), subtitle, font=_F_SUBTITLE, fill=t["text_muted"]
    )

    # ------------------------------------------------------------------
    # Carte (ombre douce + fond)
    # ------------------------------------------------------------------
    card_box = [_s(left), _s(card_top), _s(left + card_w), _s(card_top + card_h)]
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [card_box[0], card_box[1] + _s(4), card_box[2], card_box[3] + _s(4)],
        radius=_s(CARD_RADIUS),
        fill=(*t["shadow"], SHADOW_ALPHA),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(_s(8)))
    img.paste(shadow, (0, 0), shadow)
    draw.rounded_rectangle(
        card_box, radius=_s(CARD_RADIUS), fill=t["card"],
        outline=t["card_border"], width=_s(1),
    )

    tx = left + CARD_PAD
    ty = card_top + CARD_PAD
    inner_w = card_w - 2 * CARD_PAD

    def col_x(i: int) -> float:
        return tx + name_col_w + i * col_w

    # ------------------------------------------------------------------
    # Ligne d'en-tête (créneaux)
    # ------------------------------------------------------------------
    draw.rounded_rectangle(
        [_s(tx), _s(ty), _s(tx + inner_w), _s(ty + head_h)],
        radius=_s(CARD_RADIUS - CARD_PAD), fill=t["band"],
    )
    draw.text(
        (_s(tx + 16), _s(ty + head_h / 2)), "Bénévole",
        font=_F_SMALL, fill=t["text_muted"], anchor="lm",
    )
    for i, slot in enumerate(slots):
        cx = col_x(i) + col_w / 2
        if multi_jours:
            jour = f"{JOURS[slot.heure_debut.weekday()][:3]}. {slot.heure_debut.day}"
            draw.text(
                (_s(cx), _s(ty + 18)), jour,
                font=_F_HEAD_SMALL, fill=t["text_muted"], anchor="mm",
            )
        y_mid = ty + head_h / 2 + (8 if multi_jours else 0)
        label = f"{_heure(slot.heure_debut)} – {_heure(slot.heure_fin)}"
        draw.text((_s(cx), _s(y_mid)), label, font=_F_HEAD, fill=t["text"], anchor="mm")

    # ------------------------------------------------------------------
    # Lignes membres (fond + nom)
    # ------------------------------------------------------------------
    for row_idx, name in enumerate(names):
        y = ty + head_h + row_idx * ROW_H
        if row_idx % 2 == 1:
            draw.rectangle([_s(tx), _s(y), _s(tx + inner_w), _s(y + ROW_H)], fill=t["row_alt"])
        draw.text(
            (_s(tx + 16), _s(y + ROW_H / 2)), name,
            font=_F_NAME, fill=t["text"], anchor="lm",
        )

    # Séparateurs verticaux discrets entre créneaux (sous les bulles, pour
    # ne pas couper celles qui couvrent plusieurs créneaux)
    for i in range(len(slots)):
        x = col_x(i)
        draw.line(
            [(_s(x), _s(ty + head_h)), (_s(x), _s(ty + head_h + len(visible_members) * ROW_H))],
            fill=t["rule"], width=_s(1),
        )

    # Bulles : les créneaux consécutifs de même type fusionnent en une seule
    for row_idx, member in enumerate(visible_members):
        y = ty + head_h + row_idx * ROW_H
        i = 0
        while i < len(slots):
            asgn_type = asgn_map.get((member.id, slots[i].id))
            if asgn_type == AssignmentTypeEnum.respo_bar.value:
                fill, text_color, label = t["respo"], t["respo_text"], "Respo bar"
            elif asgn_type == AssignmentTypeEnum.staff.value:
                fill, text_color, label = t["staff"], t["staff_text"], "Staff"
            else:
                i += 1
                continue
            j = i
            while (
                j + 1 < len(slots)
                and asgn_map.get((member.id, slots[j + 1].id)) == asgn_type
                and slots[j + 1].heure_debut == slots[j].heure_fin
            ):
                j += 1
            x0, x1 = col_x(i), col_x(j + 1)
            draw.rounded_rectangle(
                [
                    _s(x0 + PILL_INSET_X), _s(y + PILL_INSET_Y),
                    _s(x1 - PILL_INSET_X), _s(y + ROW_H - PILL_INSET_Y),
                ],
                radius=_s(PILL_RADIUS), fill=fill,
            )
            draw.text(
                (_s((x0 + x1) / 2), _s(y + ROW_H / 2)), label,
                font=_F_PILL, fill=text_color, anchor="mm",
            )
            i = j + 1

    # ------------------------------------------------------------------
    # Ligne total
    # ------------------------------------------------------------------
    total_y = ty + head_h + len(visible_members) * ROW_H
    draw.rounded_rectangle(
        [_s(tx), _s(total_y), _s(tx + inner_w), _s(total_y + ROW_H)],
        radius=_s(CARD_RADIUS - CARD_PAD), fill=t["band"],
    )
    draw.text(
        (_s(tx + 16), _s(total_y + ROW_H / 2)), "Effectif",
        font=_F_SMALL, fill=t["text_muted"], anchor="lm",
    )
    for i, slot in enumerate(slots):
        count = slot_counts.get(slot.id, 0)
        draw.text(
            (_s(col_x(i) + col_w / 2), _s(total_y + ROW_H / 2)),
            str(count),
            font=_F_TOTAL, fill=t["text"] if count else t["respo"], anchor="mm",
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

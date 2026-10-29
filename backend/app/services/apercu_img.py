"""
Image d'aperçu (Open Graph) des liens de dispos : une « affiche » 1200×630.

Même charte que l'export PNG (police Baloo 2, thème LATEB ou thème dérivé du
logo de l'événement) : logo à gauche ; surtitre, nom, date/horaires et une
pastille « Je donne mes dispos → » à droite.
"""
from __future__ import annotations

import io
import unicodedata
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .export_img import FONT_PATH, LATEB_THEME, _load_logo
from .logo_theme import _darken_until

RGB = Tuple[int, int, int]

LARGEUR, HAUTEUR = 1200, 630
CADRE = 14
MARGE = 70
LOGO_MAX = (400, 380)
GOUTTIERE = 56
INTERLIGNE = 24  # entre deux blocs (surtitre, nom, date)

SURTITRE = "ON A BESOIN DE TOI"
NOM_GENERIQUE = "Planning du bar"
PASTILLE = "Je donne mes dispos →"
BLANC: RGB = (255, 255, 255)

# Nom : on réduit la police pas à pas jusqu'à tenir sur 2 lignes, puis ellipse.
NOM_TAILLES = range(92, 55, -6)
NOM_LIGNES_MAX = 2


def _font(size: int, weight: str) -> ImageFont.FreeTypeFont:
    try:
        font = ImageFont.truetype(str(FONT_PATH), size)
        font.set_variation_by_name(weight)
        return font
    except OSError:
        return ImageFont.load_default(size)


def texte_affichable(texte: str) -> str:
    """Retire ce que Baloo 2 ne sait pas dessiner (emoji, pictogrammes) pour
    éviter les carrés vides sur l'image, puis compacte les espaces."""
    garde = (
        c for c in texte
        if ord(c) <= 0xFFFF
        and unicodedata.category(c) not in ("So", "Cf", "Cs")
        and not 0xFE00 <= ord(c) <= 0xFE0F
    )
    return " ".join("".join(garde).split())


def _lignes(draw: ImageDraw.ImageDraw, texte: str, font, largeur: int) -> List[str]:
    """Découpage glouton par mots."""
    lignes: List[str] = []
    for mot in texte.split():
        essai = f"{lignes[-1]} {mot}" if lignes else mot
        if lignes and draw.textlength(essai, font=font) <= largeur:
            lignes[-1] = essai
        else:
            lignes.append(mot)
    return lignes


def _ellipse(draw: ImageDraw.ImageDraw, texte: str, font, largeur: int) -> str:
    if draw.textlength(texte, font=font) <= largeur:
        return texte
    while texte and draw.textlength(texte + "…", font=font) > largeur:
        texte = texte[:-1]
    return texte.rstrip() + "…"


def _ajuster_nom(draw: ImageDraw.ImageDraw, nom: str, largeur: int):
    """(police, lignes) : la plus grande taille où le nom tient en 2 lignes,
    sinon la plus petite avec la dernière ligne tronquée par une ellipse."""
    for taille in NOM_TAILLES:
        font = _font(taille, "ExtraBold")
        lignes = _lignes(draw, nom, font, largeur)
        if len(lignes) <= NOM_LIGNES_MAX and all(
            draw.textlength(l, font=font) <= largeur for l in lignes
        ):
            return font, lignes
    lignes = _lignes(draw, nom, font, largeur)
    gardees = lignes[: NOM_LIGNES_MAX - 1]
    reste = " ".join(lignes[NOM_LIGNES_MAX - 1:])
    if not reste:
        # Un seul mot, trop large même à la plus petite taille : pas de 2e ligne
        # vide, on force l'ellipse sur l'unique ligne.
        return font, [_ellipse(draw, lignes[0], font, largeur)]
    gardees = [_ellipse(draw, l, font, largeur) for l in gardees]
    return font, gardees + [_ellipse(draw, reste, font, largeur)]


def _hauteur_ligne(font) -> int:
    # Les métriques de Baloo 2 réservent beaucoup d'espace au-dessus et en
    # dessous : on empile les lignes au pas de la taille de police.
    return round(font.size * 1.1)


def rendre_apercu_png(
    nom: Optional[str],
    ligne_date: Optional[str],
    logo_png: Optional[bytes],
    theme: Optional[Dict[str, RGB]],
) -> bytes:
    """PNG 1200×630. `nom=None` → affiche générique LATEB (sans surtitre ni date).
    `ligne_date` peut contenir un saut de ligne (date, puis horaires)."""
    t = theme or LATEB_THEME
    img = Image.new("RGB", (LARGEUR, HAUTEUR), t["bg"])
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, LARGEUR - 1, HAUTEUR - 1), outline=t["frame"], width=CADRE)

    x_texte = MARGE
    logo = _load_logo(LOGO_MAX[1], logo_png)
    if logo is not None:
        logo.thumbnail(LOGO_MAX, Image.LANCZOS)
        img.paste(logo, (MARGE, (HAUTEUR - logo.height) // 2), logo)
        x_texte = MARGE + logo.width + GOUTTIERE
    largeur = LARGEUR - MARGE - x_texte

    # Blocs de texte : (lignes, police, couleur), empilés puis centrés verticalement.
    blocs: List[Tuple[List[str], ImageFont.FreeTypeFont, RGB]] = []
    nom_propre = texte_affichable(nom or "") or NOM_GENERIQUE
    if nom is not None:
        blocs.append(([SURTITRE], _font(30, "Bold"), t["text_muted"]))
    f_nom, l_nom = _ajuster_nom(draw, nom_propre, largeur)
    blocs.append((l_nom, f_nom, t["text"]))
    if ligne_date:
        f_date = _font(40, "Bold")
        blocs.append(
            ([_ellipse(draw, l, f_date, largeur) for l in ligne_date.split("\n")], f_date, t["brand"])
        )

    f_pastille = _font(32, "Bold")
    pad_x, pad_y = 30, 12
    h_pastille = _hauteur_ligne(f_pastille) + 2 * pad_y
    hauteurs = [len(lignes) * _hauteur_ligne(f) for lignes, f, _ in blocs]
    total = sum(hauteurs) + INTERLIGNE * len(blocs) + 18 + h_pastille
    y = (HAUTEUR - total) // 2

    for lignes, font, couleur in blocs:
        for ligne in lignes:
            draw.text((x_texte, y + font.size * 0.85), ligne, font=font, fill=couleur, anchor="ls")
            y += _hauteur_ligne(font)
        y += INTERLIGNE
    y += 18

    # Pastille : couleur du cadre, assombrie jusqu'à un contraste AA avec le blanc.
    fond = _darken_until(t["frame"], BLANC, 4.5)
    w_pastille = draw.textlength(PASTILLE, font=f_pastille) + 2 * pad_x
    draw.rounded_rectangle(
        (x_texte, y, x_texte + w_pastille, y + h_pastille), radius=h_pastille // 2, fill=fond
    )
    draw.text(
        (x_texte + pad_x, y + h_pastille / 2), PASTILLE, font=f_pastille, fill=BLANC, anchor="lm"
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

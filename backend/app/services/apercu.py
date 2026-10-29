"""
Aperçu Open Graph des liens de dispos (/dispo/{token}).

Les robots d'aperçu (Discord, WhatsApp, Telegram…) n'exécutent pas le JS de
la SPA : on leur sert une petite page HTML dont le <head> porte les balises
Open Graph (titre, description, image), avec un simple lien vers le formulaire
pour un humain égaré. Pas de redirection automatique : un navigateur dont l'UA
ressemble à un robot serait renvoyé ici en boucle par nginx.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import List, Tuple

from ..models.models import Event, Slot
from .export_img import JOURS, MOIS, _heure

SITE_NOM = "LATEB · Planning du bar"
COULEUR_LATEB = "#ff6200"
TEXTES_GENERIQUES: Tuple[str, str] = (
    "Planning du bar LATEB",
    "Donne tes dispos pour les prochaines soirées du bar.",
)


def date_courte(dt: datetime) -> str:
    """« Samedi 31 octobre » — sans l'année, inutile pour un événement proche."""
    return f"{JOURS[dt.weekday()].capitalize()} {dt.day} {MOIS[dt.month - 1]}"


def textes_apercu(event: Event, slots: List[Slot]) -> Tuple[str, str]:
    """(titre, description) de la carte. `slots` triés par heure_debut."""
    titre = f"{event.nom} — donne tes dispos"
    if not slots:
        return titre, f"{date_courte(event.date)}."
    debut, fin = slots[0].heure_debut, slots[-1].heure_fin
    return titre, f"{date_courte(debut)} · {_heure(debut)} → {_heure(fin)}."


def page_apercu_html(
    titre: str, description: str, url: str, image_url: str, couleur: str
) -> str:
    t, d, u, i, c = (escape(v, quote=True) for v in (titre, description, url, image_url, couleur))
    site = escape(SITE_NOM, quote=True)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{t}</title>
<meta name="description" content="{d}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{site}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{u}">
<meta property="og:image" content="{i}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="{c}">
</head>
<body>
<p><a href="{u}">{t}</a></p>
</body>
</html>
"""

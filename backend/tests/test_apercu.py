"""Tests de l'aperçu Open Graph des liens /dispo/{token} (carte Discord)."""
from __future__ import annotations

import io
from datetime import datetime, timedelta

import pytest
from PIL import Image, ImageDraw

from app.config import settings
from app.models.models import Event, EventTypeEnum, Logo, Slot
from app.services.apercu import page_apercu_html, textes_apercu
from app.services.apercu_img import (
    LARGEUR,
    _ajuster_nom,
    rendre_apercu_png,
    texte_affichable,
)
from app.services.logo_theme import extract_theme, logo_et_theme
from tests.test_public_poll import _make_event_with_slots, _open_poll


# ---------------------------------------------------------------------------
# Textes et HTML
# ---------------------------------------------------------------------------


def test_textes_apercu_avec_creneaux_passant_minuit():
    d = datetime(2026, 10, 31, 20, 0)
    ev = Event(nom="Soirée Halloween", date=d)
    slots = [
        Slot(heure_debut=d + timedelta(hours=i), heure_fin=d + timedelta(hours=i + 1))
        for i in range(6)
    ]
    assert textes_apercu(ev, slots) == (
        "Soirée Halloween — donne tes dispos",
        "Samedi 31 octobre · 20h → 2h.",
    )


def test_textes_apercu_sans_creneau():
    ev = Event(nom="Afterwork", date=datetime(2026, 11, 5, 18, 30))
    assert textes_apercu(ev, [])[1] == "Jeudi 5 novembre."


def test_textes_apercu_minutes():
    d = datetime(2026, 11, 5, 18, 30)
    ev = Event(nom="Afterwork", date=d)
    slots = [Slot(heure_debut=d, heure_fin=datetime(2026, 11, 5, 21, 0))]
    assert textes_apercu(ev, slots)[1] == "Jeudi 5 novembre · 18h30 → 21h."


def test_page_apercu_html_balises_og():
    html = page_apercu_html("T", "D", "https://x/dispo/abc", "https://x/img.png", "#ff6200")
    for attendu in [
        'property="og:title" content="T"',
        'property="og:description" content="D"',
        'property="og:url" content="https://x/dispo/abc"',
        'property="og:image" content="https://x/img.png"',
        'property="og:image:width" content="1200"',
        'property="og:image:height" content="630"',
        'property="og:site_name" content="LATEB · Planning du bar"',
        'property="og:type" content="website"',
        'name="twitter:card" content="summary_large_image"',
        'name="theme-color" content="#ff6200"',
        "<title>T</title>",
        '<a href="https://x/dispo/abc">',
    ]:
        assert attendu in html


def test_page_apercu_html_sans_redirection_auto():
    # Un humain dont l'UA ressemble à un robot (navigateur intégré d'une appli)
    # reçoit cette page : une redirection automatique vers /dispo/{token} le
    # renverrait ici en boucle. Il n'a qu'un lien à cliquer.
    html = page_apercu_html("T", "D", "https://x/dispo/abc", "https://x/img.png", "#ff6200")
    assert "refresh" not in html


def test_page_apercu_html_echappe():
    html = page_apercu_html('<b>"Fête" & co</b>', "D", "u", "i", "#000000")
    assert "<b>" not in html
    assert "&lt;b&gt;&quot;Fête&quot; &amp; co&lt;/b&gt;" in html


# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------


def _taille(png: bytes):
    return Image.open(io.BytesIO(png)).size


def _logo_png(color=(120, 40, 200)) -> bytes:
    img = Image.new("RGBA", (120, 80), (0, 0, 0, 0))
    img.paste((*color, 255), (10, 10, 110, 70))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_rendre_apercu_png_dimensions():
    png = rendre_apercu_png("Soirée Halloween", "Samedi 31 octobre\n20h → 2h", None, None)
    assert _taille(png) == (1200, 630)


def test_rendre_apercu_png_generique():
    assert _taille(rendre_apercu_png(None, None, None, None)) == (1200, 630)


def test_rendre_apercu_png_nom_tres_long():
    png = rendre_apercu_png("Grande soirée " * 8, "Samedi 31 octobre\n20h → 2h", None, None)
    assert _taille(png) == (1200, 630)


@pytest.mark.parametrize("nom", ["Grande soirée " * 8, "Anticonstitutionnellement" * 3])
def test_ajuster_nom_tient_sur_deux_lignes(nom):
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    largeur = 600
    font, lignes = _ajuster_nom(draw, nom, largeur)
    assert len(lignes) <= 2
    assert all(draw.textlength(l, font=font) <= largeur for l in lignes)
    assert lignes[-1].endswith("…")


def test_rendre_apercu_png_logo_importe_et_theme():
    logo = _logo_png()
    png = rendre_apercu_png("X", "Y", logo, extract_theme(logo))
    assert _taille(png) == (1200, 630)


def test_texte_affichable_retire_emoji():
    assert texte_affichable("🎃 Soirée  Halloween 🍺") == "Soirée Halloween"


def test_logo_et_theme(db_session):
    ev = Event(nom="E", date=datetime(2026, 10, 31, 20), type=EventTypeEnum.soiree)
    db_session.add(ev)
    db_session.flush()
    assert logo_et_theme(db_session, ev) == (None, None)

    contenu = _logo_png()
    avec = Logo(nom="Avec", contenu=contenu, utiliser_couleurs=True)
    sans = Logo(nom="Sans", contenu=contenu, utiliser_couleurs=False)
    db_session.add_all([avec, sans])
    db_session.flush()

    ev.logo_id = avec.id
    png, theme = logo_et_theme(db_session, ev)
    assert png == contenu and isinstance(theme, dict) and "frame" in theme

    ev.logo_id = sans.id
    assert logo_et_theme(db_session, ev) == (contenu, None)


# ---------------------------------------------------------------------------
# Routes publiques
# ---------------------------------------------------------------------------


@pytest.fixture()
def base_url(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://salope.lateb.eu/")


def _event_avec_lien(client, db_session) -> tuple[str, Event]:
    event, _ = _make_event_with_slots(db_session, n_slots=2)
    return _open_poll(client, event.id), event


def test_apercu_html_token_connu(client, db_session, base_url):
    token, _ = _event_avec_lien(client, db_session)
    res = client.get(f"/api/public/polls/{token}/apercu")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert res.headers["cache-control"] == "no-cache"
    assert 'content="Soirée poll — donne tes dispos"' in res.text
    assert 'content="Mardi 1 septembre · 20h → 22h."' in res.text
    assert f'content="https://salope.lateb.eu/dispo/{token}"' in res.text
    assert f'content="https://salope.lateb.eu/api/public/polls/{token}/apercu.png"' in res.text
    assert 'name="theme-color" content="#ff6200"' in res.text


def test_apercu_html_inscriptions_fermees_identique(client, db_session, base_url):
    token, event = _event_avec_lien(client, db_session)
    avant = client.get(f"/api/public/polls/{token}/apercu").text
    res = client.put(f"/api/events/{event.id}/public-link", json={"inscriptions_ouvertes": False})
    assert res.status_code == 200, res.text
    assert client.get(f"/api/public/polls/{token}/apercu").text == avant


def test_apercu_html_token_inconnu(client, base_url):
    res = client.get("/api/public/polls/inconnu/apercu")
    assert res.status_code == 200
    assert 'content="Planning du bar LATEB"' in res.text
    assert 'content="https://salope.lateb.eu/api/public/apercu.png"' in res.text


def test_apercu_png_token_connu(client, db_session):
    token, _ = _event_avec_lien(client, db_session)
    res = client.get(f"/api/public/polls/{token}/apercu.png")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.headers["cache-control"] == "public, max-age=3600"
    assert _taille(res.content) == (1200, 630)


def test_apercu_png_token_inconnu(client):
    assert client.get("/api/public/polls/inconnu/apercu.png").status_code == 404


def test_apercu_png_generique(client):
    res = client.get("/api/public/apercu.png")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert _taille(res.content) == (1200, 630)

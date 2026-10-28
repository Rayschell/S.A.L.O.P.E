"""Thème de l'export dérivé des couleurs d'un logo."""
from __future__ import annotations

import io

from PIL import Image, ImageDraw

from app.services.logo_theme import _hue_gap, contrast, extract_theme


def _logo(*colors, light=None) -> bytes:
    """Bandes verticales de couleurs pleines, contour noir, fond transparent."""
    img = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 299, 199), outline=(0, 0, 0, 255), width=8)
    fills = list(colors) + ([light] if light else [])
    w = 284 // len(fills)
    for i, c in enumerate(fills):
        d.rectangle((8 + i * w, 8, 8 + (i + 1) * w - 1, 191), fill=(*c, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


GREEN = (61, 194, 26)
RED = (155, 27, 27)
BONE = (243, 236, 203)


def test_two_hues_split_between_respo_and_staff():
    t = extract_theme(_logo(GREEN, RED, light=BONE))
    # Rouge (plus sombre) → Respo bar, vert → Staff
    assert _hue_gap(t["respo"], RED) < 15
    assert _hue_gap(t["staff"], GREEN) < 15
    assert _hue_gap(t["respo"], t["staff"]) >= 40


def test_light_logo_colour_becomes_background():
    t = extract_theme(_logo(GREEN, RED, light=BONE))
    assert _hue_gap(t["bg"], BONE) < 15


def test_text_is_readable():
    for png in (_logo(GREEN, RED, light=BONE), _logo((255, 220, 0)), _logo((40, 60, 200))):
        t = extract_theme(png)
        assert contrast(t["respo_text"], t["respo"]) >= 4.5
        assert contrast(t["staff_text"], t["staff"]) >= 4.5
        assert contrast(t["text"], t["bg"]) >= 7
        assert contrast(t["text_muted"], t["bg"]) >= 4.5
        assert contrast(t["text"], t["band"]) >= 4.5


def test_single_hue_still_distinguishes_pills():
    t = extract_theme(_logo((239, 110, 20)))
    assert t["respo"] != t["staff"]
    assert contrast(t["respo"], t["staff"]) >= 1.8


def test_grey_logo_has_no_theme():
    assert extract_theme(_logo((128, 128, 128), (30, 30, 30))) is None

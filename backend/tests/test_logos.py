"""Logos d'export : import, choix par événement, suppression, rendu PNG."""
from __future__ import annotations

import io
from datetime import datetime

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.models.models import Event, EventTypeEnum, Logo


def _image_bytes(fmt: str, size=(120, 80), margin: int = 10, color=(255, 98, 0)) -> bytes:
    """Image avec un bord transparent de `margin` px autour d'un rectangle plein."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    img.paste((*color, 255), (margin, margin, size[0] - margin, size[1] - margin))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _upload(client: TestClient, nom: str = "Halloween", data: bytes | None = None,
            filename: str = "logo.png", mime: str = "image/png"):
    return client.post(
        "/api/logos",
        data={"nom": nom},
        files={"fichier": (filename, data or _image_bytes("PNG"), mime)},
    )


def _create_event(db: Session) -> Event:
    event = Event(nom="Soirée Logo", date=datetime(2026, 10, 31, 20), type=EventTypeEnum.soiree)
    db.add(event)
    db.flush()
    return event


def test_upload_png_then_list(client: TestClient):
    res = _upload(client)
    assert res.status_code == 201, res.text
    logo = res.json()
    assert logo["nom"] == "Halloween"

    listed = client.get("/api/logos").json()
    assert [l["nom"] for l in listed] == ["Halloween"]


def test_upload_webp_is_accepted(client: TestClient):
    res = _upload(client, data=_image_bytes("WEBP"), filename="logo.webp", mime="image/webp")
    assert res.status_code == 201, res.text


def test_upload_is_normalised_to_cropped_png(client: TestClient):
    logo_id = _upload(client, data=_image_bytes("WEBP"), filename="l.webp", mime="image/webp").json()["id"]
    res = client.get(f"/api/logos/{logo_id}/image")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(res.content))
    assert img.format == "PNG"
    # Le bord transparent de 10 px est rogné
    assert img.size == (100, 60)


def test_upload_rejects_jpeg(client: TestClient):
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), (255, 0, 0)).save(buf, format="JPEG")
    res = _upload(client, data=buf.getvalue(), filename="logo.jpg", mime="image/jpeg")
    assert res.status_code == 422


def test_upload_rejects_non_image(client: TestClient):
    res = _upload(client, data=b"pas une image", filename="logo.png")
    assert res.status_code == 422


def test_upload_rejects_too_large(client: TestClient):
    res = _upload(client, data=b"\x89PNG" + b"0" * (2 * 1024 * 1024 + 1))
    assert res.status_code == 413


def test_upload_requires_name(client: TestClient):
    res = _upload(client, nom="   ")
    assert res.status_code == 422


def test_set_event_logo_and_reset(client: TestClient, db_session: Session):
    event = _create_event(db_session)
    logo_id = _upload(client).json()["id"]

    res = client.put(f"/api/events/{event.id}/logo", json={"logo_id": logo_id})
    assert res.status_code == 200, res.text
    assert res.json()["logo_id"] == logo_id
    assert client.get(f"/api/events/{event.id}").json()["logo_id"] == logo_id

    res = client.put(f"/api/events/{event.id}/logo", json={"logo_id": None})
    assert res.json()["logo_id"] is None


def test_set_event_logo_unknown_logo(client: TestClient, db_session: Session):
    event = _create_event(db_session)
    res = client.put(f"/api/events/{event.id}/logo", json={"logo_id": 999999})
    assert res.status_code == 404


def test_delete_logo_resets_events_to_default(client: TestClient, db_session: Session):
    event = _create_event(db_session)
    logo_id = _upload(client).json()["id"]
    client.put(f"/api/events/{event.id}/logo", json={"logo_id": logo_id})

    res = client.delete(f"/api/logos/{logo_id}")
    assert res.status_code == 204
    assert client.get("/api/logos").json() == []
    assert client.get(f"/api/events/{event.id}").json()["logo_id"] is None
    assert db_session.get(Logo, logo_id) is None


def test_export_uses_event_logo(client: TestClient, db_session: Session):
    event = _create_event(db_session)
    default_png = client.get(f"/api/events/{event.id}/export-png").content

    logo_id = _upload(client).json()["id"]
    client.put(f"/api/events/{event.id}/logo", json={"logo_id": logo_id})
    custom = client.get(f"/api/events/{event.id}/export-png")

    assert custom.status_code == 200
    assert Image.open(io.BytesIO(custom.content)).format == "PNG"
    assert custom.content != default_png


def test_logo_exposes_theme_swatches(client: TestClient):
    logo = _upload(client).json()
    assert logo["utiliser_couleurs"] is True
    assert len(logo["couleurs"]) == 4
    assert all(c.startswith("#") for c in logo["couleurs"])


def test_toggle_logo_colours_changes_export(client: TestClient, db_session: Session):
    event = _create_event(db_session)
    green = _image_bytes("PNG", color=(61, 194, 26))
    logo_id = _upload(client, data=green).json()["id"]
    client.put(f"/api/events/{event.id}/logo", json={"logo_id": logo_id})
    themed = client.get(f"/api/events/{event.id}/export-png").content

    res = client.patch(f"/api/logos/{logo_id}", json={"utiliser_couleurs": False})
    assert res.status_code == 200
    assert res.json()["utiliser_couleurs"] is False
    plain = client.get(f"/api/events/{event.id}/export-png").content

    # Cadre : couleur du logo d'un côté, orange LATEB de l'autre
    corner = lambda png: Image.open(io.BytesIO(png)).convert("RGB").getpixel((2, 2))
    assert corner(plain) == (255, 98, 0)
    assert corner(themed) != (255, 98, 0)

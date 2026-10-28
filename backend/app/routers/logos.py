"""Logos d'export PNG — import, liste, aperçu, suppression."""
from __future__ import annotations

import io
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from ..core.deps import get_current_member, get_db, require_bureau
from ..models.models import Event, Logo
from ..schemas.schemas import LogoRead, LogoUpdate
from ..services.logo_theme import extract_theme, theme_swatches

router = APIRouter(prefix="/api/logos", tags=["logos"])

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
ALLOWED_FORMATS = {"PNG", "WEBP"}
# Au-delà, inutile : l'export affiche le logo à ~184 px de haut (92 px × 2)
MAX_STORED_SIDE = 800


def _normalise(data: bytes) -> bytes:
    """Valide l'image puis la stocke en PNG RGBA, bords transparents rognés."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=422, detail="Fichier image illisible")
    if img.format not in ALLOWED_FORMATS:
        raise HTTPException(status_code=422, detail="Formats acceptés : PNG ou WebP")

    img = img.convert("RGBA")
    bbox = img.getchannel("A").getbbox()
    if bbox is None:
        raise HTTPException(status_code=422, detail="L'image est entièrement transparente")
    img = img.crop(bbox)
    img.thumbnail((MAX_STORED_SIDE, MAX_STORED_SIDE), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _read(logo: Logo) -> LogoRead:
    theme = extract_theme(logo.contenu)
    return LogoRead(
        id=logo.id,
        nom=logo.nom,
        created_at=logo.created_at,
        utiliser_couleurs=logo.utiliser_couleurs,
        couleurs=theme_swatches(theme) if theme else None,
    )


def _get_or_404(db: Session, logo_id: int) -> Logo:
    logo = db.get(Logo, logo_id)
    if logo is None:
        raise HTTPException(status_code=404, detail="Logo introuvable")
    return logo


@router.get("", response_model=List[LogoRead])
def list_logos(
    db: Session = Depends(get_db),
    _=Depends(get_current_member),
):
    return [_read(l) for l in db.query(Logo).order_by(Logo.created_at).all()]


@router.post("", response_model=LogoRead, status_code=201)
async def upload_logo(
    nom: str = Form(...),
    fichier: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_bureau),
):
    nom = nom.strip()
    if not nom:
        raise HTTPException(status_code=422, detail="Le nom du logo est requis")
    data = await fichier.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image trop lourde (2 Mo maximum)")

    logo = Logo(nom=nom, contenu=_normalise(data))
    db.add(logo)
    db.commit()
    db.refresh(logo)
    return _read(logo)


@router.patch("/{logo_id}", response_model=LogoRead)
def update_logo(
    logo_id: int,
    payload: LogoUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_bureau),
):
    logo = _get_or_404(db, logo_id)
    logo.utiliser_couleurs = payload.utiliser_couleurs
    db.commit()
    db.refresh(logo)
    return _read(logo)


@router.get("/{logo_id}/image")
def logo_image(
    logo_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_member),
):
    logo = _get_or_404(db, logo_id)
    return Response(
        content=logo.contenu,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.delete("/{logo_id}", status_code=204)
def delete_logo(
    logo_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_bureau),
):
    logo = _get_or_404(db, logo_id)
    # Les événements qui l'utilisaient reviennent au logo original
    db.query(Event).filter(Event.logo_id == logo_id).update(
        {Event.logo_id: None}, synchronize_session="fetch"
    )
    db.delete(logo)
    db.commit()

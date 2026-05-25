"""Parse a historical planning image (spreadsheet grid: members × time slots).

Expected format (as seen in Excel/Google-Sheets exports):
- Row 0 (blue header): "Nom" | "HH:MM - HH:MM" | "HH:MM - HH:MM" | ...
- Rows 1..N-1: member name | green cell (staff) | red cell (respo_bar) | empty
- Last row: "Total ✓ voix" (skipped)

Colors detected:
- Green background → staff
- Red background   → respo_bar
- Other            → not assigned
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pytesseract
from PIL import Image
from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from ..config import settings
from ..models.models import (
    Assignment,
    AssignmentSourceEnum,
    AssignmentTypeEnum,
    Event,
    EventStatutEnum,
    EventTypeEnum,
    Member,
    MemberAlias,
    Slot,
    StatsMemberHeureRelative,
)

# ── Time-range pattern ────────────────────────────────────────────────────────
# Matches "22:00 - 23:00", "0:00-1:00", "00h00 – 01h00", etc.
_TIME_RE = re.compile(
    r'(\d{1,2})\s*[h:]\s*(\d{2})\s*[-–—]+\s*(\d{1,2})\s*[h:]\s*(\d{2})'
)

_SKIP_KEYWORDS = frozenset(['total', 'nom', 'voix', 'name'])


# ── Color helpers ─────────────────────────────────────────────────────────────

def _is_header_blue(r: int, g: int, b: int) -> bool:
    """Header row has a clearly blue background."""
    return b > 100 and b > r * 1.1 and b > g * 1.05 and r + g + b > 100


def _is_neutral_gray(r: int, g: int, b: int) -> bool:
    """
    Pixel looks like a grid separator line: neutral gray of any shade,
    not a clearly colored cell or pure white background.
    Catches Excel borders that range from dark-gray to medium-gray.
    """
    if _is_header_blue(r, g, b):
        return False
    if _classify_pixel(r, g, b) is not None:
        return False
    saturation = max(r, g, b) - min(r, g, b)
    return saturation < 40 and max(r, g, b) < 240  # neutral, not pure white


def _classify_pixel(r: int, g: int, b: int) -> Optional[str]:
    """Classify a cell pixel as staff (green), respo_bar (red), or None."""
    # Green: g clearly dominant
    if g > 100 and g > r + 20 and g > b + 10:
        return "staff"
    # Red: r clearly dominant
    if r > 150 and r > g + 60 and r > b + 60:
        return "respo_bar"
    return None


# ── Grid detection ────────────────────────────────────────────────────────────

def _find_header_bounds(img: Image.Image) -> Tuple[int, int]:
    """Scan from the top to find the y-range of the blue header row."""
    w, h = img.size
    step = max(1, w // 40)

    start: Optional[int] = None
    end: Optional[int] = None

    for y in range(min(h, 300)):
        blue = sum(
            1 for x in range(0, w, step)
            if _is_header_blue(*img.getpixel((x, y))[:3])
        )
        ratio = blue / max(1, w // step)
        if ratio > 0.30 and start is None:
            start = y
        elif ratio <= 0.10 and start is not None:
            end = y
            break

    return (start or 0, end or max(40, (start or 0) + 50))


def _find_col_seps(img: Image.Image, hdr_y1: int, hdr_y2: int, min_gap: int = 15) -> List[int]:
    """
    Find column separator x-positions by scanning the header row for gaps in
    blue coverage.  This works whether the separator lines are white, light
    gray, or dark — as long as they are NOT the same blue as the header cells.

    A separator x-column has blue_ratio ≈ 0 %.
    A text character inside a blue cell has blue_ratio ≈ 40-60 % (text
    characters don't fill the full cell height, so most y-samples are still
    blue background).  We use 0.20 as the threshold to distinguish them.
    """
    w = img.size[0]
    y_step = max(1, (hdr_y2 - hdr_y1) // 12)
    n_samples = max(1, len(range(hdr_y1, hdr_y2, y_step)))

    seps: List[int] = []
    in_sep = False
    for x in range(w):
        blue = sum(
            1 for y in range(hdr_y1, hdr_y2, y_step)
            if _is_header_blue(*img.getpixel((x, y))[:3])
        )
        ratio = blue / n_samples
        if ratio < 0.20 and not in_sep:
            seps.append(x)
            in_sep = True
        elif ratio >= 0.20:
            in_sep = False

    merged: List[int] = []
    for s in seps:
        if not merged or s - merged[-1] >= min_gap:
            merged.append(s)
    return merged


def _find_col_seps_ocr(img: Image.Image, hdr_y1: int, hdr_y2: int) -> List[int]:
    """
    OCR-based column detection. Used when header borders are invisible (e.g.
    screenshots from the app which uses rgba(255,255,255,0.1) separators).

    Runs Tesseract on the header row and groups detected words into cells
    by horizontal proximity, then places separators at midpoints between
    consecutive cell groups.
    """
    hdr_h = max(hdr_y2 - hdr_y1, 1)
    header = img.crop((0, hdr_y1, img.width, hdr_y2))
    scale = max(2, 80 // hdr_h)
    header_up = header.resize((header.width * scale, header.height * scale), Image.LANCZOS)

    data = pytesseract.image_to_data(
        header_up, lang="fra+eng", config="--psm 11 --oem 3",
        output_type=pytesseract.Output.DICT,
    )

    words: List[Tuple[int, int]] = []
    for i, text in enumerate(data["text"]):
        if not str(text).strip():
            continue
        raw_conf = data["conf"][i]
        conf = int(raw_conf) if str(raw_conf).lstrip("-").isdigit() else -1
        if conf < 0:
            continue
        x1 = data["left"][i] // scale
        x2 = x1 + data["width"][i] // scale
        words.append((x1, x2))

    if len(words) < 2:
        return []

    words.sort()

    # Merge words that are close together (same cell) into cell bounding boxes
    gap_thr = max(10, img.width // 30)
    cells: List[List[int]] = [[words[0][0], words[0][1]]]
    for x1, x2 in words[1:]:
        if x1 - cells[-1][1] < gap_thr:
            cells[-1][1] = max(cells[-1][1], x2)
        else:
            cells.append([x1, x2])

    if len(cells) < 2:
        return []

    # Separators at midpoints between consecutive cell groups
    return [(cells[i][1] + cells[i + 1][0]) // 2 for i in range(len(cells) - 1)]


def _find_row_seps(img: Image.Image, x1: int, x2: int, y1: int, y2: int, min_gap: int = 8) -> List[int]:
    """
    Find row separator y-positions in the body by looking for horizontal
    strips of neutral-gray pixels (any shade, not pure white or cell colors).
    """
    x_step = max(1, (x2 - x1) // 40)
    n_samples = max(1, len(range(x1, x2, x_step)))

    seps: List[int] = []
    in_sep = False
    for y in range(y1, y2):
        gray = sum(
            1 for x in range(x1, x2, x_step)
            if _is_neutral_gray(*img.getpixel((x, y))[:3])
        )
        ratio = gray / n_samples
        if ratio > 0.40 and not in_sep:
            seps.append(y)
            in_sep = True
        elif ratio < 0.15:
            in_sep = False

    merged: List[int] = []
    for s in seps:
        if not merged or s - merged[-1] >= min_gap:
            merged.append(s)
    return merged


def _find_row_seps_ocr(
    img: Image.Image,
    name_x1: int,
    name_x2: int,
    body_y1: int,
) -> List[int]:
    """
    OCR-based row detection. Used when row borders are invisible (app screenshots).
    Runs Tesseract on the name column and uses text line positions to infer rows.
    """
    _, total_h = img.size
    col_w = max(name_x2 - name_x1, 1)
    col = img.crop((name_x1, body_y1, name_x2, total_h))
    scale = max(2, 200 // col_w)
    col_up = col.resize((col.width * scale, col.height * scale), Image.LANCZOS)

    data = pytesseract.image_to_data(
        col_up, lang="fra+eng", config="--psm 6 --oem 3",
        output_type=pytesseract.Output.DICT,
    )

    # Group tokens into lines by (block, par, line) keys
    line_ranges: Dict[tuple, List[int]] = {}
    for i, text in enumerate(data["text"]):
        if not str(text).strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        y_top = data["top"][i] // scale + body_y1
        y_bot = y_top + data["height"][i] // scale
        if key not in line_ranges:
            line_ranges[key] = [y_top, y_bot]
        else:
            line_ranges[key][0] = min(line_ranges[key][0], y_top)
            line_ranges[key][1] = max(line_ranges[key][1], y_bot)

    if not line_ranges:
        return []

    sorted_lines = sorted(v for v in line_ranges.values())

    # Merge lines that are very close (within 15px) = same logical row
    merged: List[List[int]] = [list(sorted_lines[0])]
    for y1, y2 in sorted_lines[1:]:
        if y1 - merged[-1][1] < 15:
            merged[-1][1] = max(merged[-1][1], y2)
        else:
            merged.append([y1, y2])

    # Separators at midpoints between adjacent rows
    return [(merged[i][1] + merged[i + 1][0]) // 2 for i in range(len(merged) - 1)]


def _ranges_from_seps(seps: List[int], total: int, offset: int = 0) -> List[Tuple[int, int]]:
    """Convert separator positions to (start, end) cell ranges, skipping tiny gaps."""
    edges = [offset] + seps + [total]
    result = []
    for i in range(len(edges) - 1):
        a = edges[i] + 1 if i > 0 else edges[i]
        b = edges[i + 1]
        if b - a >= 5:
            result.append((a, b))
    return result


# ── Cell operations ───────────────────────────────────────────────────────────

def _cell_type(img: Image.Image, x1: int, y1: int, x2: int, y2: int) -> Optional[str]:
    """Sample the background color of a cell region."""
    m = max(2, min(4, (x2 - x1) // 6, (y2 - y1) // 6))
    region = img.crop((x1 + m, y1 + m, x2 - m, y2 - m))

    counts: Dict[str, int] = {"staff": 0, "respo_bar": 0, "other": 0}
    for r, g, b in region.getdata():
        t = _classify_pixel(r, g, b)
        counts[t or "other"] += 1

    total = sum(counts.values()) or 1
    for t in ("staff", "respo_bar"):
        if counts[t] / total > 0.20:
            return t
    return None


def _ocr_cell(img: Image.Image, x1: int, y1: int, x2: int, y2: int) -> str:
    """OCR a single cell region."""
    if x2 - x1 < 3 or y2 - y1 < 3:
        return ""
    region = img.crop((x1, y1, x2, y2))
    # Upscale for legibility
    scale = max(2, min(4, 60 // max(region.height, 1)))
    region = region.resize((region.width * scale, region.height * scale), Image.LANCZOS)
    raw = pytesseract.image_to_string(region, lang="fra+eng", config="--psm 7 --oem 3")
    return " ".join(raw.split())


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_planning_image(img_bytes: bytes) -> Dict[str, Any]:
    """
    Parse a planning-grid image.

    Returns:
        {
          "slots":   [{"heure_debut": "HH:MM", "heure_fin": "HH:MM"}, ...],
          "members": [{"name": str, "assignments": [{"slot_index": int, "type": "staff"|"respo_bar"}]}, ...],
        }
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = img.size

    # 1. Locate header row
    hdr_y1, hdr_y2 = _find_header_bounds(img)

    # 2. Find column separators using blue-density profile in the header row.
    #    Works for Excel exports (white/visible borders).
    v_seps = _find_col_seps(img, hdr_y1, hdr_y2, min_gap=15)
    col_ranges = _ranges_from_seps(v_seps, w)

    if len(col_ranges) < 2:
        # Fallback: OCR word positions in the header (works for app screenshots
        # where column borders are rgba(255,255,255,0.1) and invisible).
        v_seps = _find_col_seps_ocr(img, hdr_y1, hdr_y2)
        col_ranges = _ranges_from_seps(v_seps, w)

    if len(col_ranges) < 2:
        raise ValueError(
            "Impossible de détecter les colonnes "
            f"(header={hdr_y1}-{hdr_y2}px, {len(col_ranges)} colonnes trouvées). "
            "Vérifiez que la ligne d'en-tête bleue est bien visible et que "
            "chaque créneau horaire a sa propre colonne."
        )

    # 3. Find row separators.
    #    Try visible-border detection first (Excel), then OCR fallback (app screenshots
    #    where row borders are rgba(255,255,255,0.07) and invisible).
    name_col = col_ranges[0]
    h_seps = _find_row_seps(img, 0, w, hdr_y2, h, min_gap=8)
    row_ranges = _ranges_from_seps(h_seps, h, offset=hdr_y2)

    if not row_ranges:
        h_seps = _find_row_seps_ocr(img, name_col[0], name_col[1], hdr_y2)
        row_ranges = _ranges_from_seps(h_seps, h, offset=hdr_y2)

    if not row_ranges:
        raise ValueError("Impossible de détecter les lignes de membres dans l'image.")

    slot_cols = col_ranges[1:]

    # 4. OCR slot headers
    slots: List[Dict[str, str]] = []
    for x1, x2 in slot_cols:
        text = _ocr_cell(img, x1, hdr_y1, x2, hdr_y2)
        m = _TIME_RE.search(text)
        if m:
            slots.append({
                "heure_debut": f"{int(m.group(1)):02d}:{m.group(2)}",
                "heure_fin":   f"{int(m.group(3)):02d}:{m.group(4)}",
            })
        else:
            # Try looser: two HH:MM tokens
            times = re.findall(r'\d{1,2}[h:]\d{2}', text)
            if len(times) >= 2:
                def _fmt(t: str) -> str:
                    parts = re.split(r'[h:]', t)
                    return f"{int(parts[0]):02d}:{parts[1]}"
                slots.append({"heure_debut": _fmt(times[0]), "heure_fin": _fmt(times[1])})
            else:
                slots.append({"heure_debut": "??:??", "heure_fin": "??:??"})

    # 5. Parse member rows
    members: List[Dict[str, Any]] = []
    for y1, y2 in row_ranges:
        name = _ocr_cell(img, name_col[0], y1, name_col[1], y2)
        if not name:
            continue
        if any(kw in name.lower() for kw in _SKIP_KEYWORDS):
            continue
        # Skip lines that look like pure numbers (totals)
        if re.fullmatch(r'[\d\s]+', name):
            continue

        assignments: List[Dict[str, Any]] = []
        for slot_idx, (x1, x2) in enumerate(slot_cols):
            t = _cell_type(img, x1, y1, x2, y2)
            if t:
                assignments.append({"slot_index": slot_idx, "type": t})

        members.append({"name": name, "assignments": assignments})

    return {"slots": slots, "members": members}


# ── Name resolution ───────────────────────────────────────────────────────────

def _build_name_map(db: Session) -> Dict[str, int]:
    name_map: Dict[str, int] = {}
    for m in db.query(Member).all():
        name_map[f"{m.prenom} {m.nom}".lower()] = m.id
        name_map[f"{m.nom} {m.prenom}".lower()] = m.id
        name_map[m.nom.lower()] = m.id
    for alias in db.query(MemberAlias).all():
        name_map[alias.valeur.lower()] = alias.membre_id
    return name_map


def resolve_names(
    names: List[str],
    db: Session,
) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
    """
    Fuzzy-match names to existing members.
    Returns (resolved: {name: member_id}, unresolved: [{csv_name, suggestions}])
    """
    threshold = settings.FUZZY_MATCH_THRESHOLD
    name_map = _build_name_map(db)
    choices = list(name_map.keys())

    resolved: Dict[str, int] = {}
    unresolved: List[Dict[str, Any]] = []

    for name in names:
        nl = name.lower().strip()
        if nl in name_map:
            resolved[name] = name_map[nl]
            continue

        matches = process.extract(nl, choices, scorer=fuzz.token_sort_ratio, limit=3)
        best_score = matches[0][1] if matches else 0

        if best_score >= threshold:
            resolved[name] = name_map[matches[0][0]]
        else:
            suggestions = [
                {
                    "member_id": name_map[alias],
                    "display_name": alias.title(),
                    "score": round(score / 100, 2),
                }
                for alias, score, _ in matches[:3]
            ]
            unresolved.append({"csv_name": name, "suggestions": suggestions})

    return resolved, unresolved


# ── Commit import ─────────────────────────────────────────────────────────────

def commit_historical_import(
    db: Session,
    event_nom: str,
    event_date_str: str,
    event_type: EventTypeEnum,
    slots_data: List[Dict[str, str]],
    members_data: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create the historical event (published) with slots and assignments."""

    base_date = datetime.strptime(event_date_str, "%Y-%m-%d")

    # ── Event ──────────────────────────────────────────────────────────────
    event = Event(
        nom=event_nom,
        date=base_date,
        type=event_type,
        statut=EventStatutEnum.publie,
    )
    db.add(event)
    db.flush()

    # ── Slots ───────────────────────────────────────────────────────────────
    slot_objs: List[Slot] = []
    for idx, s in enumerate(slots_data):
        try:
            h_s, m_s = map(int, s["heure_debut"].split(":"))
            h_e, m_e = map(int, s["heure_fin"].split(":"))
        except (ValueError, KeyError):
            h_s = m_s = h_e = m_e = 0

        start = base_date.replace(hour=h_s, minute=m_s, second=0, microsecond=0)
        end   = base_date.replace(hour=h_e, minute=m_e, second=0, microsecond=0)
        if end <= start:
            end += timedelta(days=1)

        slot = Slot(
            evenement_id=event.id,
            heure_debut=start,
            heure_fin=end,
            heure_relative=idx,
            max_personnes=99,
        )
        db.add(slot)
        slot_objs.append(slot)

    db.flush()

    # ── Resolution map ──────────────────────────────────────────────────────
    res_map: Dict[str, Dict[str, Any]] = {r["csv_name"]: r for r in resolutions}

    # Auto-resolve names that aren't in the explicit resolutions
    auto_names = [m["name"] for m in members_data if m["name"] not in res_map]
    auto_resolved, _ = resolve_names(auto_names, db)

    # ── Assignments ─────────────────────────────────────────────────────────
    assignments_created = 0
    respo_bar_members: set = set()

    for mdata in members_data:
        name = mdata["name"]

        # Determine member_id
        if name in res_map:
            r = res_map[name]
            if r.get("create_new"):
                parts = name.split()
                prenom = parts[0] if parts else name
                nom    = " ".join(parts[1:]) if len(parts) > 1 else parts[0]
                new_m  = Member(nom=nom, prenom=prenom, roles=["staff"])
                db.add(new_m)
                db.flush()
                member_id: Optional[int] = new_m.id
            else:
                member_id = r.get("member_id")
        else:
            member_id = auto_resolved.get(name)

        if not member_id:
            continue

        for a in mdata.get("assignments", []):
            slot_idx = a.get("slot_index", -1)
            if slot_idx < 0 or slot_idx >= len(slot_objs):
                continue
            slot = slot_objs[slot_idx]

            asgn_type = (
                AssignmentTypeEnum.respo_bar
                if a.get("type") == "respo_bar"
                else AssignmentTypeEnum.staff
            )

            # Skip duplicates
            if db.query(Assignment).filter_by(creneau_id=slot.id, membre_id=member_id).first():
                continue

            db.add(Assignment(
                creneau_id=slot.id,
                membre_id=member_id,
                type=asgn_type,
                source=AssignmentSourceEnum.manuel,
            ))
            assignments_created += 1

            if asgn_type == AssignmentTypeEnum.respo_bar:
                respo_bar_members.add(member_id)

            # Increment fois_staffe stat
            stat = db.query(StatsMemberHeureRelative).filter_by(
                membre_id=member_id,
                type_evenement=event_type,
                heure_relative=slot.heure_relative,
            ).first()
            if stat:
                stat.fois_staffe += 1
            else:
                db.add(StatsMemberHeureRelative(
                    membre_id=member_id,
                    type_evenement=event_type,
                    heure_relative=slot.heure_relative,
                    fois_disponible=0,
                    fois_staffe=1,
                ))

    # Increment respo_bar shift counter
    for mid in respo_bar_members:
        m = db.query(Member).filter_by(id=mid).first()
        if m:
            m.shifts_respo_bar_cumules = (m.shifts_respo_bar_cumules or 0) + 1

    db.commit()
    return {"event_id": event.id, "assignments_created": assignments_created}

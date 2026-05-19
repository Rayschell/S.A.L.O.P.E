"""
Server-side PNG export of the planning grid using Pillow.
"""
from __future__ import annotations

import io
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

from ..models.models import Assignment, AssignmentTypeEnum, Event, Member, Slot

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
COLOR_BG = (255, 255, 255)
COLOR_HEADER = (37, 99, 235)       # blue-600
COLOR_HEADER_TEXT = (255, 255, 255)
COLOR_STAFF = (187, 247, 208)      # green-200
COLOR_STAFF_BORDER = (21, 128, 61) # green-700
COLOR_RESPO = (254, 202, 202)      # red-200
COLOR_RESPO_BORDER = (185, 28, 28) # red-700
COLOR_BORDER = (209, 213, 219)     # gray-300
COLOR_TOTAL_BG = (243, 244, 246)   # gray-100
COLOR_TEXT = (17, 24, 39)          # gray-900

COL_W = 90
ROW_H = 32
NAME_COL_W = 180
HEADER_H = 64
PADDING = 8
FONT_SIZE = 13
TITLE_FONT_SIZE = 16

try:
    _FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", FONT_SIZE)
    _FONT_BOLD = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", FONT_SIZE
    )
    _FONT_TITLE = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", TITLE_FONT_SIZE
    )
except OSError:
    _FONT = ImageFont.load_default()
    _FONT_BOLD = _FONT
    _FONT_TITLE = _FONT


def export_planning_png(
    event: Event,
    slots: List[Slot],
    members: List[Member],
    assignments_db: List[Assignment],
) -> bytes:
    """
    Render the planning as a PNG image and return the raw bytes.
    """
    # Build lookup: (member_id, slot_id) -> assignment_type
    asgn_map: Dict[Tuple[int, int], str] = {}
    slot_counts: Dict[int, int] = {}
    for a in assignments_db:
        asgn_map[(a.membre_id, a.creneau_id)] = a.type.value
        slot_counts[a.creneau_id] = slot_counts.get(a.creneau_id, 0) + 1

    # Only show members who have at least one availability / assignment
    assigned_member_ids = {a.membre_id for a in assignments_db}
    visible_members = [m for m in members if m.id in assigned_member_ids]
    if not visible_members:
        visible_members = members

    n_slots = len(slots)
    n_members = len(visible_members)

    img_width = NAME_COL_W + n_slots * COL_W + 2 * PADDING
    # title area + header row + member rows + total row
    img_height = PADDING + TITLE_FONT_SIZE + PADDING + HEADER_H + n_members * ROW_H + ROW_H + PADDING

    img = Image.new("RGB", (img_width, img_height), COLOR_BG)
    draw = ImageDraw.Draw(img)

    # ------------------------------------------------------------------
    # Title
    # ------------------------------------------------------------------
    title = f"{event.nom}  —  {event.date.strftime('%d/%m/%Y')}"
    draw.text((PADDING, PADDING), title, font=_FONT_TITLE, fill=COLOR_HEADER)

    top = PADDING + TITLE_FONT_SIZE + PADDING

    # ------------------------------------------------------------------
    # Header row (slot labels)
    # ------------------------------------------------------------------
    draw.rectangle([0, top, img_width, top + HEADER_H], fill=COLOR_HEADER)
    # First cell (member name column)
    draw.text(
        (PADDING, top + (HEADER_H - FONT_SIZE) // 2),
        "Membre",
        font=_FONT_BOLD,
        fill=COLOR_HEADER_TEXT,
    )
    for col_idx, slot in enumerate(slots):
        x = NAME_COL_W + col_idx * COL_W
        label_line1 = slot.heure_debut.strftime("%d/%m")
        label_line2 = f"{slot.heure_debut.strftime('%H:%M')}-{slot.heure_fin.strftime('%H:%M')}"
        draw.text(
            (x + PADDING, top + 4),
            label_line1,
            font=_FONT,
            fill=COLOR_HEADER_TEXT,
        )
        draw.text(
            (x + PADDING, top + 4 + FONT_SIZE + 2),
            label_line2,
            font=_FONT,
            fill=COLOR_HEADER_TEXT,
        )
        # Vertical separator
        draw.line([(x, top), (x, top + HEADER_H)], fill=COLOR_HEADER_TEXT, width=1)

    # ------------------------------------------------------------------
    # Member rows
    # ------------------------------------------------------------------
    for row_idx, member in enumerate(visible_members):
        y = top + HEADER_H + row_idx * ROW_H
        # Row background (alternating)
        bg = (249, 250, 251) if row_idx % 2 == 0 else COLOR_BG
        draw.rectangle([0, y, img_width, y + ROW_H], fill=bg)

        # Member name
        name = f"{member.prenom} {member.nom}"
        draw.text((PADDING, y + (ROW_H - FONT_SIZE) // 2), name, font=_FONT, fill=COLOR_TEXT)

        # Cells
        for col_idx, slot in enumerate(slots):
            x = NAME_COL_W + col_idx * COL_W
            asgn_type = asgn_map.get((member.id, slot.id))
            if asgn_type == AssignmentTypeEnum.respo_bar.value:
                cell_color = COLOR_RESPO
                border_color = COLOR_RESPO_BORDER
                label = "Respo"
            elif asgn_type == AssignmentTypeEnum.staff.value:
                cell_color = COLOR_STAFF
                border_color = COLOR_STAFF_BORDER
                label = "Staff"
            else:
                cell_color = COLOR_BG
                border_color = COLOR_BORDER
                label = ""

            draw.rectangle([x + 1, y + 1, x + COL_W - 1, y + ROW_H - 1], fill=cell_color)
            draw.rectangle(
                [x + 1, y + 1, x + COL_W - 1, y + ROW_H - 1],
                outline=border_color,
                width=1,
            )
            if label:
                draw.text(
                    (x + PADDING, y + (ROW_H - FONT_SIZE) // 2),
                    label,
                    font=_FONT,
                    fill=COLOR_TEXT,
                )

        # Horizontal separator
        draw.line([(0, y + ROW_H), (img_width, y + ROW_H)], fill=COLOR_BORDER, width=1)

    # ------------------------------------------------------------------
    # Total row
    # ------------------------------------------------------------------
    total_y = top + HEADER_H + n_members * ROW_H
    draw.rectangle([0, total_y, img_width, total_y + ROW_H], fill=COLOR_TOTAL_BG)
    draw.text(
        (PADDING, total_y + (ROW_H - FONT_SIZE) // 2),
        "Total ✓ voix",
        font=_FONT_BOLD,
        fill=COLOR_TEXT,
    )
    for col_idx, slot in enumerate(slots):
        x = NAME_COL_W + col_idx * COL_W
        count = slot_counts.get(slot.id, 0)
        draw.text(
            (x + PADDING, total_y + (ROW_H - FONT_SIZE) // 2),
            str(count),
            font=_FONT_BOLD,
            fill=COLOR_TEXT,
        )

    # Outer border
    draw.rectangle([0, top, img_width - 1, img_height - 1], outline=COLOR_BORDER, width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

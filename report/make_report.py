"""Turn the confirmed issue list into a PDF inventory report."""

import math
import os
from datetime import datetime

from fpdf import FPDF


def _text(value):
    """Blank for empty or missing values; drop characters the built-in PDF font can't draw."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).encode("latin-1", "replace").decode("latin-1")


def _cap(value):
    """Capital first letter, rest unchanged."""
    text = _text(value).strip()
    return text[:1].upper() + text[1:]


def _timestamp(seconds):
    """12.0 -> '0:12'. Blank if the time is missing."""
    try:
        s = int(float(seconds))
    except (TypeError, ValueError):
        return ""
    return f"{s // 60}:{s % 60:02d}"


def make_pdf(issues, tenant_name, property_address):
    """Return the report as PDF bytes. Only issues with confirmed=True are included."""
    created_at = datetime.now().strftime("%d/%m/%Y at %H:%M")
    confirmed = [i for i in issues if i.get("confirmed")]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Move-in Inventory Report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 7, f"Tenant: {_text(tenant_name)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Property: {_text(property_address)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Created: {created_at}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if not confirmed:
        pdf.cell(0, 7, "No issues recorded.", new_x="LMARGIN", new_y="NEXT")

    rooms = []
    for i in confirmed:
        if _text(i.get("room")) not in rooms:
            rooms.append(_text(i.get("room")))

    for room in rooms:
        if pdf.get_y() + 100 > pdf.page_break_trigger:  # don't leave a room heading alone at the bottom
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 9, _cap(room) or "Room not set", new_x="LMARGIN", new_y="NEXT")
        for i in confirmed:
            if _text(i.get("room")) != room:
                continue
            if pdf.get_y() + 90 > pdf.page_break_trigger:  # keep each issue and its photo on one page
                pdf.add_page()
            pdf.set_font("Helvetica", "B", 11)
            line = f"{_cap(i.get('item'))}: {_cap(i.get('issue'))} ({_cap(i.get('severity'))})"
            pdf.multi_cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=10)
            ts = _timestamp(i.get("frame_time_s"))
            if ts:
                pdf.cell(0, 5, f"Seen at {ts} in the video", new_x="LMARGIN", new_y="NEXT")
            if _text(i.get("note")):
                pdf.multi_cell(0, 5, f"Note: {_text(i.get('note'))}", new_x="LMARGIN", new_y="NEXT")
            frame = _text(i.get("frame_path"))
            if frame and os.path.exists(frame):
                pdf.image(frame, x=pdf.l_margin, w=90, h=70, keep_aspect_ratio=True)  # fits portrait or landscape
            pdf.ln(4)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(
        0, 4,
        "Record of the property's condition made by the tenant at move-in. "
        "General guidance only, not legal advice. For deposit disputes see GOV.UK "
        "(tenancy deposit protection), Shelter or Citizens Advice.",
    )
    return bytes(pdf.output())

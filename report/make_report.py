"""Turn the confirmed issue list into a PDF inventory report."""

import math
import os
from datetime import datetime

from fpdf import FPDF

NAVY = (31, 58, 96)
GREY = (110, 110, 110)
LIGHT = (242, 245, 249)
SEVERITY_COLOURS = {"minor": (46, 139, 87), "moderate": (230, 145, 30), "major": (200, 50, 50)}


def _text(value):
    """Blank for empty or missing values; drop characters the built-in PDF font can't draw."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).replace("–", "-").replace("’", "'").encode("latin-1", "replace").decode("latin-1")


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


class _Report(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(*GREY)
        self.cell(0, 5, "Move-in Co-pilot - tenant's record of the property's condition at move-in", align="L")
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")


def make_pdf(issues, tenant_name, property_address):
    """Return the report as PDF bytes. Only issues with confirmed=True are included."""
    created_at = datetime.now().strftime("%d/%m/%Y at %H:%M")
    confirmed = [i for i in issues if i.get("confirmed")]

    pdf = _Report()
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    # Title band
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 28, style="F")
    pdf.set_xy(pdf.l_margin, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Move-in Inventory Report")
    pdf.set_y(34)

    # Details box
    pdf.set_fill_color(*LIGHT)
    pdf.set_text_color(0, 0, 0)
    for label, value in [("Tenant", tenant_name), ("Property", property_address), ("Created", created_at)]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(25, 7, f"  {label}", fill=True)
        pdf.set_font("Helvetica", size=10)
        pdf.cell(width - 25, 7, _text(value) or "-", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Summary line
    rooms = []
    for i in confirmed:
        if _text(i.get("room")) not in rooms:
            rooms.append(_text(i.get("room")))
    counts = {s: sum(1 for i in confirmed if _text(i.get("severity")).lower() == s) for s in SEVERITY_COLOURS}
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(0, 0, 0)
    if confirmed:
        summary = (f"{len(confirmed)} issues recorded in {len(rooms)} room(s): "
                   + ", ".join(f"{n} {s}" for s, n in counts.items() if n) + ".")
    else:
        summary = "No issues recorded."
    pdf.multi_cell(0, 5, summary, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    photo_w = 55
    text_x = pdf.l_margin + photo_w + 6
    text_w = width - photo_w - 6
    for room in rooms:
        if pdf.get_y() + 75 > pdf.page_break_trigger:  # don't leave a room heading alone at the bottom
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 9, _cap(room) or "Room not set", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*NAVY)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + width, pdf.get_y())
        pdf.ln(3)
        pdf.set_text_color(0, 0, 0)

        for i in confirmed:
            if _text(i.get("room")) != room:
                continue
            if pdf.get_y() + 62 > pdf.page_break_trigger:  # keep each issue and its photo on one page
                pdf.add_page()
            top = pdf.get_y()

            # Photo on the left (fits portrait or landscape)
            frame = _text(i.get("frame_path"))
            if frame and os.path.exists(frame):
                pdf.image(frame, x=pdf.l_margin, y=top, w=photo_w, h=55, keep_aspect_ratio=True)
            else:
                pdf.set_fill_color(*LIGHT)
                pdf.rect(pdf.l_margin, top, photo_w, 20, style="F")
                pdf.set_xy(pdf.l_margin, top + 7)
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(*GREY)
                pdf.cell(photo_w, 5, "No photo (added by the tenant)", align="C")
                pdf.set_text_color(0, 0, 0)

            # Text on the right
            severity = _text(i.get("severity")).lower()
            pdf.set_xy(text_x, top)
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(text_w, 6, _cap(i.get("item")), new_x="LEFT", new_y="NEXT")
            if severity:
                pdf.set_x(text_x)
                pdf.set_fill_color(*SEVERITY_COLOURS.get(severity, GREY))
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", "B", 8)
                pdf.cell(pdf.get_string_width(severity.upper()) + 6, 5, severity.upper(), fill=True,
                         align="C", new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)
                pdf.ln(1)
            pdf.set_x(text_x)
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(text_w, 5, _cap(i.get("issue")), new_x="LEFT", new_y="NEXT")
            ts = _timestamp(i.get("frame_time_s"))
            if ts:
                pdf.set_x(text_x)
                pdf.set_text_color(*GREY)
                pdf.multi_cell(text_w, 5, f"Seen at {ts} in the video", new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)
            if _text(i.get("note")):
                pdf.set_x(text_x)
                pdf.set_font("Helvetica", "I", 10)
                pdf.multi_cell(text_w, 5, f"Tenant's note: \"{_text(i.get('note'))}\"", new_x="LEFT", new_y="NEXT")

            photo_bottom = top + (57 if frame and os.path.exists(frame) else 22)
            pdf.set_y(max(pdf.get_y(), photo_bottom) + 4)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(
        0, 4,
        "Record of the property's condition made by the tenant at move-in. "
        "General guidance only, not legal advice. For deposit disputes see GOV.UK "
        "(tenancy deposit protection), Shelter or Citizens Advice.",
    )
    return bytes(pdf.output())

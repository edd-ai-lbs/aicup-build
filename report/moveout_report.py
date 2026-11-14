"""Turn the move-out comparison (move-in vs move-out, per room) into a PDF report.
Same look as make_report.py; uses its helpers."""

import os
from datetime import datetime

from report.make_report import GREY, LIGHT, NAVY, SEVERITY_COLOURS, _cap, _Report, _text, _timestamp

GROUPS = [
    ("new_damage", "New since move-in"),
    ("cleaning_needed", "Clean before you leave"),
    ("already_recorded", "Already there at move-in (the tenant shouldn't pay for these)"),
    ("fixed", "Fixed"),
]


class _MoveOutReport(_Report):
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(*GREY)
        self.cell(0, 5, "Edd.AI - tenant's comparison of the property at move-in and move-out", align="L")
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")


def _photo(pdf, path, x, y, label):
    """One 85 x 60 mm photo with a caption under it, or a grey box if there's no photo."""
    if path and os.path.exists(path):
        pdf.image(path, x=x, y=y, w=85, h=60, keep_aspect_ratio=True)
    else:
        pdf.set_fill_color(*LIGHT)
        pdf.rect(x, y, 85, 60, style="F")
        pdf.set_xy(x, y + 27)
        pdf.set_text_color(*GREY)
        pdf.cell(85, 6, "Not visible in this video", align="C")
    pdf.set_xy(x, y + 61)
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(*GREY)
    pdf.cell(85, 4, label, align="C")
    pdf.set_text_color(0, 0, 0)


def make_moveout_pdf(results):
    """results: {room: {"findings": [...], "summary": "..."}} from compare_room_videos. Returns PDF bytes."""
    pdf = _MoveOutReport()
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 28, style="F")
    pdf.set_xy(pdf.l_margin, 8)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 12, "Move-out Comparison Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(34)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, f"Created: {datetime.now().strftime('%d/%m/%Y at %H:%M')}   ·   "
                   f"Rooms compared: {_text(', '.join(results))}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for room, result in results.items():
        if pdf.get_y() + 60 > pdf.page_break_trigger:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 10, _cap(room), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 5, _text(result.get("summary")), new_x="LMARGIN", new_y="NEXT")

        todo = [f for f in result["findings"] if f.get("fix_before_leaving")]
        if todo:
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 6, "To do before you leave", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=10)
            for f in todo:
                pdf.multi_cell(0, 5, f"[  ]  {_cap(f.get('item'))}: {_text(f.get('description'))}",
                               new_x="LMARGIN", new_y="NEXT")

        for status, title in GROUPS:
            found = [f for f in result["findings"] if f.get("status") == status]
            if not found:
                continue
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(*NAVY)
            pdf.cell(0, 7, f"{title} ({len(found)})", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            for f in found:
                if pdf.get_y() + 95 > pdf.page_break_trigger:  # keep each finding and its photos together
                    pdf.add_page()
                severity = _text(f.get("severity")).lower()
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(pdf.get_string_width(_cap(f.get("item"))) + 4, 6, _cap(f.get("item")))
                pdf.set_fill_color(*SEVERITY_COLOURS.get(severity, GREY))
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", "B", 8)
                pdf.cell(pdf.get_string_width(_cap(severity)) + 6, 5, _cap(severity), fill=True, align="C",
                         new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Helvetica", size=10)
                pdf.multi_cell(0, 5, _text(f.get("description")), new_x="LMARGIN", new_y="NEXT")
                top = pdf.get_y() + 2
                _photo(pdf, _text(f.get("before_path")), pdf.l_margin, top,
                       f"Move-in {_timestamp(f.get('before_time_s'))}".strip())
                _photo(pdf, _text(f.get("after_path")), pdf.l_margin + 95, top,
                       f"Move-out {_timestamp(f.get('after_time_s'))}".strip())
                pdf.set_xy(pdf.l_margin, top + 67)
                pdf.set_font("Helvetica", size=9)
                pdf.set_text_color(*GREY)
                pdf.multi_cell(0, 4.5, f"Who sorts it: {_text(f.get('responsibility'))}. "
                                       f"{_text(f.get('responsibility_reason'))} "
                                       f"Source: {_text(f.get('responsibility_source'))} "
                                       f"{_text(f.get('responsibility_url'))}",
                               new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)
                pdf.ln(4)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(0, 4, "Comparison of the tenant's move-in and move-out videos, made by the tenant. "
                         "General guidance only, not legal advice. For deposit disputes see GOV.UK "
                         "(tenancy deposit protection), Shelter or Citizens Advice.")
    return bytes(pdf.output())

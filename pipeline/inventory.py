"""Agency inventory (PDF) vs what the tenant's videos found -> disagreements + a draft reply."""

import base64
import json

import anthropic
from dotenv import load_dotenv

load_dotenv()

STATUSES = ["missing_from_inventory", "inventory_only", "not_filmed", "agrees"]

PROMPT = """The attached PDF is the check-in inventory a UK letting agency sent to a tenant.
The tenant filmed the flat, and an AI found these issues (number: room | item | issue | severity):
{issues}

Rooms the tenant filmed: {rooms}

Compare the inventory with the findings. Return one finding per inventory item or video issue that matters:
- "missing_from_inventory": the video shows damage the inventory doesn't mention or describes as
  good/clean/working. These matter most: the tenant should raise them with the agency.
- "inventory_only": the inventory notes damage that is not in the video findings (the tenant should check it).
- "not_filmed": an inventory room the tenant did not film (one finding per room, not per item).
- "agrees": the inventory and the video say the same thing about an item.
Match rooms and items by meaning, not exact words (e.g. "Bedroom" and "Bedroom 1"). For
"issue_number" give the matching video issue number, or -1 if there is none.
Quote the inventory's own words in "inventory_says" ("" if the inventory doesn't mention it).

Then write "reply", a short, polite email from the tenant to the agency, listing only the
"missing_from_inventory" points (and asking to note them on the inventory). Plain text, no placeholders
except [Your name]."""

SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": STATUSES},
                    "room": {"type": "string"},
                    "item": {"type": "string"},
                    "inventory_says": {"type": "string"},
                    "video_shows": {"type": "string"},
                    "issue_number": {"type": "integer"},
                },
                "required": ["status", "room", "item", "inventory_says", "video_shows", "issue_number"],
                "additionalProperties": False,
            },
        },
        "reply": {"type": "string"},
    },
    "required": ["findings", "reply"],
    "additionalProperties": False,
}


def _text(value):
    """'' for missing values (the app's table uses NaN for empty cells)."""
    return "" if value is None or value != value else str(value)


def compare_inventory(pdf_path, issues, rooms_filmed):
    """Returns {"findings": [...], "reply": "..."}; findings sorted most important first.
    Each finding linked to a video issue also gets that issue's frame_time_s and frame_path."""
    with open(pdf_path, "rb") as f:
        pdf = base64.standard_b64encode(f.read()).decode("utf-8")
    listing = "\n".join(
        f"{n}: {_text(i.get('room'))} | {_text(i.get('item'))} | {_text(i.get('issue'))} | {_text(i.get('severity'))}"
        for n, i in enumerate(issues)
    ) or "(no issues found)"
    prompt = PROMPT.format(issues=listing, rooms=", ".join(rooms_filmed) or "(none)")

    response = anthropic.Anthropic().beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=16000,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf}},
            {"type": "text", "text": prompt},
        ]}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to compare this inventory.")
    result = json.loads(next(b.text for b in response.content if b.type == "text"))

    for finding in result["findings"]:
        n = finding.pop("issue_number")
        linked = issues[n] if 0 <= n < len(issues) else {}
        finding["frame_time_s"] = linked.get("frame_time_s")
        finding["frame_path"] = _text(linked.get("frame_path"))
    result["findings"].sort(key=lambda f: STATUSES.index(f["status"]))
    return result

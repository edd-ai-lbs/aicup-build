"""Extra voice note -> new issues, or comments on issues already in the list.

For "I forgot to film it" moments: the tenant records a short note after the videos.
"""

import json

import anthropic
from dotenv import load_dotenv

from pipeline.vision import RULES, RULES_BY_ID
from pipeline.voice import transcribe

load_dotenv()

PROMPT = """A tenant in the UK is making a move-in inventory report as evidence for their deposit.
After filming, they recorded this extra voice note:

"{note}"

The report already lists these issues (number: room | item | issue | current note):
{issues}

Turn the voice note into report entries:
- A problem that is not in the list yet becomes a new issue. Use one of these rooms: {rooms}.
  If the room is unclear, pick the closest one.
- A comment about a problem already in the list goes in "comments" with that issue's number,
  instead of a new issue.
- Put the tenant's own words for each point in "note". Ignore filler that is not about a problem.
- For each new issue, pick the "rule_id" that best says who deals with it under English renting rules:
{rules}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "new_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "room": {"type": "string"},
                    "item": {"type": "string"},
                    "issue": {"type": "string"},
                    "severity": {"type": "string", "enum": ["minor", "moderate", "major"]},
                    "note": {"type": "string"},
                    "rule_id": {"type": "string", "enum": list(RULES_BY_ID)},
                },
                "required": ["room", "item", "issue", "severity", "note", "rule_id"],
                "additionalProperties": False,
            },
        },
        "comments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"number": {"type": "integer"}, "note": {"type": "string"}},
                "required": ["number", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["new_issues", "comments"],
    "additionalProperties": False,
}


def _text(value):
    """'' for missing values (the app's table uses NaN for empty cells)."""
    return "" if value is None or value != value else str(value)


def add_voice_note(audio_path, issues, rooms):
    """Returns (updated issue list, what the tenant said). Doesn't change `issues` itself."""
    said = " ".join(s["text"] for s in transcribe(audio_path))
    if not said:
        return list(issues), ""

    listing = "\n".join(
        f"{n}: {_text(i.get('room'))} | {_text(i.get('item'))} | {_text(i.get('issue'))} | {_text(i.get('note'))}"
        for n, i in enumerate(issues)
    ) or "(none yet)"
    prompt = PROMPT.format(note=said, issues=listing, rooms=", ".join(rooms),
                           rules="\n".join(f'  - "{r["id"]}": {r["covers"]}' for r in RULES))

    response = anthropic.Anthropic().beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=16000,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to process this voice note.")
    result = json.loads(next(b.text for b in response.content if b.type == "text"))

    updated = [dict(i) for i in issues]
    for c in result["comments"]:
        if 0 <= c["number"] < len(updated):
            old = _text(updated[c["number"]].get("note"))
            updated[c["number"]]["note"] = (old + " " + c["note"]).strip()
    for new in result["new_issues"]:
        new.update(frame_time_s=None, frame_path="", confirmed=True)  # no video moment for these
        rule = RULES_BY_ID[new.pop("rule_id")]  # same sourced answer as video issues
        new.update(responsibility=rule["who"], responsibility_reason=rule["explanation"],
                   responsibility_source=rule["source"]["label"], responsibility_url=rule["source"]["url"])
        updated.append(new)
    return updated, said

"""Move-in admin checklist: loads content/checklist.json and picks the items for the user's answers."""

import json
from pathlib import Path

CHECKLIST = json.loads((Path(__file__).parent / "checklist.json").read_text())


def checklist_for(answers):
    """answers: {"all_students": True, "bills_included": False, ...} (question ids from checklist.json).
    Returns the items that apply. Unanswered questions show the item, to be safe."""
    return [
        item for item in CHECKLIST["items"]
        if not item["show_if"] or all(answers.get(q, v) == v for q, v in item["show_if"].items())
    ]

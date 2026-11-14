"""Confirmed issues -> a ready-to-send email to the landlord, citing the GOV.UK / Shelter source of each rule.

In app/move_in.py:  from pipeline.landlord_email import write_email
Same demo fallback as analyse.py: the same issues give the saved email instantly.
"""

import hashlib
import json

import anthropic
from dotenv import load_dotenv

from pipeline.analyse import CACHE_DIR

load_dotenv()

PROMPT = """Write an email from a tenant in England to their landlord or letting agent, sent on move-in day
together with a PDF inventory report (photos and timestamps for every issue).

Tenant: {tenant}
Property: {address}
Landlord / agent name: {landlord}
Issues in the report (room | item | issue | severity | who sorts it | why | source):
{issues}

Write it so that it:
- is polite, clear and firm; short paragraphs; British English; no legal threats.
- says the attached report records the property's condition at move-in, so these issues are not
  charged to the tenant from the deposit later.
- lists the issues grouped by room, briefly.
- asks the landlord to arrange repairs for the "Landlord to repair" issues, and to confirm a date.
- for each kind of responsibility, cites the source given (name + link) in a short "For reference" list.
- asks the landlord to confirm receipt in writing, and mentions the tenant will keep the report with
  their deposit protection paperwork.
- does not invent facts, laws, clauses or dates beyond what is given here. No placeholders like [date].
- signs off with the tenant's name."""

SCHEMA = {
    "type": "object",
    "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
    "required": ["subject", "body"],
    "additionalProperties": False,
}


def _text(value):
    """'' for missing values (the app's table uses NaN for empty cells)."""
    return "" if value is None or value != value else str(value)


def write_email(issues, tenant_name, property_address, landlord_name=""):
    """Returns {"subject": ..., "body": ...} for the issues that are kept in the report."""
    kept = [i for i in issues if i.get("confirmed") == True]  # noqa: E712 (numpy True too)
    listing = "\n".join(
        " | ".join(_text(i.get(k)) for k in
                   ["room", "item", "issue", "severity", "responsibility", "responsibility_reason"])
        + f" | {_text(i.get('responsibility_source'))} {_text(i.get('responsibility_url'))}".rstrip()
        for i in kept
    ) or "(no issues: the property is in good condition)"
    prompt = PROMPT.format(tenant=tenant_name or "the tenant", address=property_address or "the property",
                           landlord=landlord_name or "not given (use a neutral greeting)", issues=listing)

    cache = CACHE_DIR / f"email_{hashlib.sha256(prompt.encode()).hexdigest()[:16]}.json"
    if cache.exists():
        return json.loads(cache.read_text())

    response = anthropic.Anthropic().beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=4000,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to write this email.")
    email = json.loads(next(b.text for b in response.content if b.type == "text"))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(email, indent=2))
    return email

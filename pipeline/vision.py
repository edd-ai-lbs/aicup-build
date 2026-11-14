"""Pictures -> list of visible damage, using Claude. Returns issues in the team's shared format."""

import base64
import json
import sys

import anthropic
from dotenv import load_dotenv

load_dotenv()  # reads ANTHROPIC_API_KEY from .env

PROMPT = """You are helping a tenant in the UK record the condition of a rented flat at move-in,
as evidence for getting their deposit back. The pictures above are frames from one walk-through
video, each labelled with the second it was taken.

List every piece of visible damage, wear or dirt a landlord could later blame on the tenant:
scratches, scuffs, marks, stains, chips, cracks, holes, mould, broken or missing items.
- Name the room each issue is in (e.g. kitchen, living room, bathroom, bedroom, hallway).
- Report each physical issue once, even if it appears in several frames; use the frame where it is clearest.
- Only report what you can actually see. Do not guess about things out of view.
- Ignore the tenant's own belongings and mess; focus on the property and its fittings."""

VOICE_PROMPT = """

While filming, the tenant said the following (time in seconds, then their words):
{transcript}

Use what they said as well as what you see:
- Still report every visible issue, including the many the tenant did not mention.
- Their words can tell you which room they are in (e.g. "now we go to the bathroom").
- If they comment on a problem, put their comment in that issue's "note", close to their own words.
- If they report a problem a picture cannot show (e.g. "this doesn't work"), add it as an issue,
  using the time they said it.
- Ignore narration that is not about a problem. Use "" for "note" when they said nothing about an issue."""

SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "room": {"type": "string"},
                    "item": {"type": "string"},
                    "issue": {"type": "string"},
                    "severity": {"type": "string", "enum": ["minor", "moderate", "major"]},
                    "frame_time_s": {"type": "number"},
                    "note": {"type": "string"},
                },
                "required": ["room", "item", "issue", "severity", "frame_time_s", "note"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["issues"],
    "additionalProperties": False,
}


def find_issues(frames, sentences=None):
    """frames: output of extract_frames(). sentences: optional output of voice.transcribe().
    Returns a list of issue dicts (shared format)."""
    content = []
    for f in frames:
        with open(f["frame_path"], "rb") as img:
            data = base64.standard_b64encode(img.read()).decode("utf-8")
        content.append({"type": "text", "text": f"Frame at {f['frame_time_s']} s:"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
    prompt = PROMPT
    if sentences:
        transcript = "\n".join(f"{s['start_s']} s: {s['text']}" for s in sentences)
        prompt += VOICE_PROMPT.format(transcript=transcript)
    content.append({"type": "text", "text": prompt})

    response = anthropic.Anthropic().beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=16000,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # if Claude declines, the API retries on another model
        messages=[{"role": "user", "content": content}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to analyse these pictures.")

    text = next(b.text for b in response.content if b.type == "text")
    issues = json.loads(text)["issues"]

    # Fill in the rest of the shared format.
    for issue in issues:
        nearest = min(frames, key=lambda f: abs(f["frame_time_s"] - issue["frame_time_s"]))
        issue["frame_time_s"] = nearest["frame_time_s"]
        issue["frame_path"] = nearest["frame_path"]
        issue["confirmed"] = True  # ticked by default; the user unticks wrong ones in the app
    return issues


if __name__ == "__main__":
    # Try it: python pipeline/vision.py data/flat.mp4
    from frames import extract_frames
    from voice import transcribe

    print(json.dumps(find_issues(extract_frames(sys.argv[1]), transcribe(sys.argv[1])), indent=2))

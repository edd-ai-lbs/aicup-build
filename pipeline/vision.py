"""Pictures -> list of visible damage, using Claude. Returns issues in the team's shared format."""

import base64
import json
import sys
from pathlib import Path

import anthropic
import cv2
from dotenv import load_dotenv

load_dotenv()  # reads ANTHROPIC_API_KEY from .env

# Who is responsible for what, with the GOV.UK / Shelter source for each rule (Francesca's content file).
RULES = json.loads((Path(__file__).parent.parent / "content" / "responsibility.json").read_text())["rules"]
RULES_BY_ID = {r["id"]: r for r in RULES}

PROMPT = """You are helping a tenant in the UK record the condition of a rented flat at move-in,
as evidence for getting their deposit back. The pictures above are frames from one walk-through
video, each labelled with the second it was taken.

List the visible damage, wear or dirt a landlord could later blame on the tenant:
scratches, scuffs, marks, stains, chips, cracks, holes, mould, rust, broken or missing items.
- Name the room each issue is in (e.g. kitchen, living room, bathroom, bedroom, hallway).
- Report each physical issue once, even if it appears in several frames; use the frame where it is clearest.
- Ignore the tenant's own belongings and mess; focus on the property and its fittings.

Be accurate: a false alarm in a legal record is as unhelpful as a missed problem.
- Only report damage you can clearly see. Phone video often has blur, glare, shadows, reflections,
  low light and compression noise; none of these are damage.
- Normal features are not damage: grout lines and tile joints, sealant that is simply present,
  screws and fixings that are meant to be there, ordinary signs of a lived-in but clean home.
- Loose parts resting on a surface (a plug, a pop-up waste, a spare fitting) are not damage; they can
  usually be put back. Only report them if something is visibly broken or clearly missing from its place.
- "frame_time_s" must be the label of a frame where this exact problem is clearly visible, because
  that picture is printed next to it in the report. Never point at a frame that shows something else.
- For each issue, rate your confidence: "high" if it would be obvious to anyone looking at the
  picture, "medium" if it is visible but small, "low" if it might be lighting, blur or a normal feature.
- If several frames show the same spot and it only looks wrong in one, it is probably not damage.
- For "medium" issues, give a short "uncertainty_reason" telling the tenant what to double-check
  (e.g. "could be a reflection on the glaze"). Use "" for "high" issues.
- "note" is only for the tenant's own spoken words (see below if any). Do not write your own description there.

For each issue, pick the "rule_id" that best says who deals with it under English renting rules:
{rules}
Remember this is a move-in record: existing cosmetic marks are not the tenant's, while things that
need fixing (broken, leaking, rusted heating, mould) usually fall to the landlord."""

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
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "uncertainty_reason": {"type": "string"},
                    "box": {  # where the problem is in that frame, in pixels
                        "type": "object",
                        "properties": {"x0": {"type": "number"}, "y0": {"type": "number"},
                                       "x1": {"type": "number"}, "y1": {"type": "number"}},
                        "required": ["x0", "y0", "x1", "y1"],
                        "additionalProperties": False,
                    },
                    "rule_id": {"type": "string", "enum": list(RULES_BY_ID)},
                },
                "required": ["room", "item", "issue", "severity", "frame_time_s", "note", "box",
                             "confidence", "uncertainty_reason", "rule_id"],
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
    content, sizes = [], {}
    for f in frames:
        with open(f["frame_path"], "rb") as img:
            data = base64.standard_b64encode(img.read()).decode("utf-8")
        h, w = cv2.imread(f["frame_path"]).shape[:2]
        sizes[f["frame_time_s"]] = (w, h)
        content.append({"type": "text", "text": f"Frame at {f['frame_time_s']} s ({w}x{h} px):"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
    prompt = PROMPT.format(rules="\n".join(f'- "{r["id"]}": {r["covers"]}' for r in RULES))
    if sentences:
        transcript = "\n".join(f"{s['start_s']} s: {s['text']}" for s in sentences)
        prompt += VOICE_PROMPT.format(transcript=transcript)
    prompt += ('\n\nFor each issue, "box" is a rectangle around the problem in the frame given by "frame_time_s", '
               "in that frame's pixels (x0, y0 top-left; x1, y1 bottom-right). Keep it snug around the damage itself. "
               "For a problem no picture shows (e.g. only mentioned by the tenant), use 0, 0, 0, 0.")
    content.append({"type": "text", "text": prompt})

    response = anthropic.Anthropic().beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=16000,
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # if Claude declines, the API retries on another model
        messages=[{"role": "user", "content": content}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to analyse these pictures.")

    text = next(b.text for b in response.content if b.type == "text")
    # Drop the ones Claude itself isn't sure about (likely lighting, blur or normal features).
    issues = [i for i in json.loads(text)["issues"] if i["confidence"] != "low"]

    # Fill in the rest of the shared format.
    for issue in issues:
        rule = RULES_BY_ID[issue.pop("rule_id")]
        issue["responsibility"] = rule["who"]  # same options as the app's "Who sorts it?" column
        issue["responsibility_reason"] = rule["explanation"]
        issue["responsibility_source"] = rule["source"]["label"]
        issue["responsibility_url"] = rule["source"]["url"]
        if not sentences:
            issue["note"] = ""  # nothing was said, so there is no tenant comment
        nearest = min(frames, key=lambda f: abs(f["frame_time_s"] - issue["frame_time_s"]))
        issue["frame_time_s"] = nearest["frame_time_s"]
        issue["frame_path"] = nearest["frame_path"]
        # Box as fractions of the picture (0-1), so it fits any copy of the frame; None if there is none
        b, (w, h) = issue.pop("box"), sizes[nearest["frame_time_s"]]
        box = [max(0.0, min(1.0, v)) for v in (b["x0"] / w, b["y0"] / h, b["x1"] / w, b["y1"] / h)]
        issue["box"] = box if box[2] - box[0] > 0.01 and box[3] - box[1] > 0.01 else None
        issue["confirmed"] = True  # ticked by default; the user unticks wrong ones in the app
    return issues


if __name__ == "__main__":
    # Try it: python pipeline/vision.py data/flat.mp4
    from frames import extract_frames
    from voice import transcribe

    print(json.dumps(find_issues(extract_frames(sys.argv[1]), transcribe(sys.argv[1])), indent=2))

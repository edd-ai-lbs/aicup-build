"""Move-out check: compare a room's move-in video with its move-out video (before/after)."""

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic
import cv2
from dotenv import load_dotenv

from pipeline.analyse import CACHE_DIR, _fingerprint  # same demo fallback as the move-in report
from pipeline.frames import extract_frames
from pipeline.voice import transcribe

load_dotenv()

_content = json.loads((Path(__file__).parent.parent / "content" / "responsibility.json").read_text())
RULES = _content["rules"] + _content["move_out_rules"]
RULES_BY_ID = {r["id"]: r for r in RULES}
STATUSES = ["new_damage", "cleaning_needed", "already_recorded", "fixed"]

PROMPT = """A tenant in the UK is moving out and wants their deposit back. Above are frames from two
videos of the same room ({room}): MOVE-IN (when they arrived) and MOVE-OUT (now), each labelled with its second.
{issues}{voice}
Compare the same spots in both videos and report what matters for the deposit:
- "new_damage": damage visible at move-out that was NOT there at move-in (scratches, holes, stains, breakages).
- "cleaning_needed": dirt, mess or items left behind that weren't there at move-in. Belongings that will be
  packed (furniture, toiletries, towels on a rail) are not a problem; things left on floors or surfaces are.
- "already_recorded": damage that was already there at move-in, so the tenant should not be charged for it.
- "fixed": something damaged at move-in that now looks repaired or better.

Be accurate: a false alarm here could cost the tenant money or trust.
- The two videos are filmed from slightly different angles and light. Differences in blur, glare,
  reflections, shadows, colour or exposure are NOT changes. Only report a change you can clearly see.
- Fair wear and tear (small scuffs, fading, light wear from normal living) is not "new_damage".
- If you can't find the same spot in both videos, don't guess a change.
- Give "before_time_s" (the MOVE-IN frame label showing the spot, or -1 if not visible) and "after_time_s"
  (the MOVE-OUT frame label). These pictures are shown side by side, so point at frames showing the spot.
- Rate "confidence": "high" if obvious, "medium" if visible but small, "low" if it might be lighting or angle.
  For "medium", give "uncertainty_reason" (what to double-check); otherwise "".
- "fix_before_leaving": true if the tenant could reasonably sort it before handing back the keys.
- Pick the "rule_id" for who deals with it:
{rules}
Then write "summary": 2-3 plain sentences for the tenant about where they stand for this room."""

BOX = {
    "type": "object",
    "properties": {"x0": {"type": "number"}, "y0": {"type": "number"}, "x1": {"type": "number"}, "y1": {"type": "number"}},
    "required": ["x0", "y0", "x1", "y1"],
    "additionalProperties": False,
}

SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": STATUSES},
                    "item": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {"type": "string", "enum": ["minor", "moderate", "major"]},
                    "before_time_s": {"type": "number"},
                    "after_time_s": {"type": "number"},
                    "before_box": BOX, "after_box": BOX,  # where it is in each frame, in pixels
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "uncertainty_reason": {"type": "string"},
                    "fix_before_leaving": {"type": "boolean"},
                    "rule_id": {"type": "string", "enum": list(RULES_BY_ID)},
                },
                "required": ["status", "item", "description", "severity", "before_time_s", "after_time_s", "before_box", "after_box",
                             "confidence", "uncertainty_reason", "fix_before_leaving", "rule_id"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["findings", "summary"],
    "additionalProperties": False,
}


def _images(label, frames):
    content = [{"type": "text", "text": f"{label} VIDEO:"}]
    for f in frames:
        with open(f["frame_path"], "rb") as img:
            data = base64.standard_b64encode(img.read()).decode("utf-8")
        h, w = cv2.imread(f["frame_path"]).shape[:2]
        content.append({"type": "text", "text": f"{label} frame at {f['frame_time_s']} s ({w}x{h} px):"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
    return content


def _nearest(frames, t):
    if t is None or t < 0 or not frames:
        return None
    return min(frames, key=lambda f: abs(f["frame_time_s"] - t))


def compare_frames(room, before_frames, after_frames, before_issues=None, after_sentences=None):
    """Core comparison. Returns {"findings": [...], "summary": "..."}; findings most important first."""
    issues = ""
    if before_issues:
        issues = "\nThe move-in report recorded: " + "; ".join(
            f"{i.get('item')}: {i.get('issue')}" for i in before_issues) + ".\n"
    voice = ""
    if after_sentences:
        voice = "\nWhile filming the move-out, the tenant said: " + " ".join(s["text"] for s in after_sentences) + "\n"
    prompt = PROMPT.format(room=room, issues=issues, voice=voice,
                           rules="\n".join(f'  - "{r["id"]}": {r["covers"]}' for r in RULES))
    prompt += ('\n\n"before_box" and "after_box": a snug rectangle around the spot in the move-in and the move-out '
               "frame you picked, in that frame's pixels (x0, y0 top-left; x1, y1 bottom-right). "
               "Use 0, 0, 0, 0 when the spot isn't visible in that video.")

    response = anthropic.Anthropic().beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=16000,
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": _images("MOVE-IN", before_frames) + _images("MOVE-OUT", after_frames)
                   + [{"type": "text", "text": prompt}]}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to compare these videos.")
    result = json.loads(next(b.text for b in response.content if b.type == "text"))

    findings = [f for f in result["findings"] if f["confidence"] != "low"]
    for f in findings:
        before, after = _nearest(before_frames, f.pop("before_time_s")), _nearest(after_frames, f.pop("after_time_s"))
        f["room"] = room
        f["before_time_s"], f["before_path"] = (before["frame_time_s"], before["frame_path"]) if before else (None, "")
        f["after_time_s"], f["after_path"] = (after["frame_time_s"], after["frame_path"]) if after else (None, "")
        for side, frame in (("before", before), ("after", after)):  # box as 0-1 fractions, or None
            b = f.pop(f"{side}_box")
            f[f"{side}_box"] = None
            if frame:
                h, w = cv2.imread(frame["frame_path"]).shape[:2]
                box = [max(0.0, min(1.0, v)) for v in (b["x0"] / w, b["y0"] / h, b["x1"] / w, b["y1"] / h)]
                if box[2] - box[0] > 0.01 and box[3] - box[1] > 0.01:
                    f[f"{side}_box"] = box
        rule = RULES_BY_ID[f.pop("rule_id")]
        f.update(responsibility=rule["who"], responsibility_reason=rule["explanation"],
                 responsibility_source=rule["source"]["label"], responsibility_url=rule["source"]["url"])
    findings.sort(key=lambda f: STATUSES.index(f["status"]))
    return {"findings": findings, "summary": result["summary"]}


def compare_room_videos(move_in_video, move_out_video, room, move_in_issues=None):
    """For the app: two videos of the same room -> before/after findings. About 20 frames from each.
    Demo fallback: results are saved in data/demo_cache/moveout_<fingerprints>.json; the same pair of
    videos again returns them in seconds (pictures are still taken from the videos for the photos)."""
    name = room.lower().replace(" ", "_") or "room"
    cache = CACHE_DIR / f"moveout_{_fingerprint(move_in_video)}_{_fingerprint(move_out_video)}.json"
    with ThreadPoolExecutor(3) as pool:  # both videos' pictures and the voice, at the same time
        before = pool.submit(extract_frames, move_in_video, name=f"{name}_in", max_frames=20)
        after = pool.submit(extract_frames, move_out_video, name=f"{name}_out", max_frames=20)
        sentences = None if cache.exists() else pool.submit(transcribe, move_out_video)
        before, after = before.result(), after.result()
        sentences = sentences.result() if sentences else None

    if cache.exists():
        print(f"Using saved AI results for these videos: {cache.name}")
        result = json.loads(cache.read_text())
        for f in result["findings"]:  # point each finding at this run's pictures
            for side, frames in (("before", before), ("after", after)):
                pick = _nearest(frames, f.get(f"{side}_time_s"))
                if pick:
                    f[f"{side}_time_s"], f[f"{side}_path"] = pick["frame_time_s"], pick["frame_path"]
        return result

    result = compare_frames(room, before, after, move_in_issues, sentences)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result, indent=2))
    return result

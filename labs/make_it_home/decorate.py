"""Make it home (prototype): Claude plans a renter-friendly makeover, Gemini draws the 'after' picture.

plan_makeover()   -> Claude looks at the room photo (+ inspiration pictures) and the tenant's wishes,
                     returns a palette, 5 ideas pinned to spots in the photo, costs and a step-by-step plan.
render_makeover() -> Gemini edits the same photo to show the result. Needs GEMINI_API_KEY in .env and
                     billing turned on in Google AI Studio (the free tier allows no image generation).
"""

import base64
import json
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

GEMINI_MODEL = "gemini-3.1-flash-image"  # fast; "gemini-3-pro-image" is higher quality but slower

PROMPT = """This is the {room} of a rented flat in the UK, from the tenant's video.{inspiration}

What the tenant wants:
- Style: {style}
- How they want to feel when they walk in: {feeling}
- Tone: {tone}, with {colour} as the main colour
- Budget: about £{budget}
- {renter_rule}

Design a makeover for THIS room:
- "vibe_name": 2-3 evocative words.
- "summary": one sentence on how the room will feel.
- "palette": 5 colours (name + hex) built around the main colour, suiting the existing floor and furniture.
- "ideas": exactly 5 changes, ordered as a step-by-step plan (biggest impact first). Each has a short "title"
  (max 4 words), one-line "detail" (max 14 words), a realistic UK "cost_gbp", and "x", "y" (fractions 0-1
  from the top-left) pointing at the real spot in the photo where it goes. Keep the total within budget.
- "render_prompt": an instruction for an image-editing AI to redraw this exact photo with these changes:
  keep the same room, camera angle, walls, windows, doors, floor and existing furniture; apply only the
  changes listed; photorealistic, same phone-photo look."""

SCHEMA = {
    "type": "object",
    "properties": {
        "vibe_name": {"type": "string"},
        "summary": {"type": "string"},
        "palette": {"type": "array", "items": {
            "type": "object", "properties": {"name": {"type": "string"}, "hex": {"type": "string"}},
            "required": ["name", "hex"], "additionalProperties": False}},
        "ideas": {"type": "array", "items": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "detail": {"type": "string"}, "cost_gbp": {"type": "integer"},
                           "x": {"type": "number"}, "y": {"type": "number"}},
            "required": ["title", "detail", "cost_gbp", "x", "y"], "additionalProperties": False}},
        "render_prompt": {"type": "string"},
    },
    "required": ["vibe_name", "summary", "palette", "ideas", "render_prompt"],
    "additionalProperties": False,
}


def _image_block(data, media_type):
    return {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                        "data": base64.standard_b64encode(data).decode("utf-8")}}


def plan_makeover(room_jpg, room, style, feeling, tone, colour, budget, inspirations=(), renter_friendly=True):
    """room_jpg: bytes of the room photo. inspirations: list of (bytes, media_type). Returns the plan dict."""
    content = [{"type": "text", "text": "The room now:"}, _image_block(room_jpg, "image/jpeg")]
    for n, (data, media_type) in enumerate(inspirations, 1):
        content += [{"type": "text", "text": f"Inspiration picture {n} from the tenant:"}, _image_block(data, media_type)]
    prompt = PROMPT.format(
        room=room.lower(), style=style, feeling=feeling, tone=tone, colour=colour, budget=budget,
        inspiration=(" The tenant also shared inspiration pictures: take the look, materials and colours they like "
                     "from them and adapt them to this room.") if inspirations else "",
        renter_rule=("Renter-friendly only: no paint, drilling, nails or landlord permission (use adhesive strips, "
                     "leaning art, freestanding lamps, textiles, plants, rugs, removable wallpaper).")
        if renter_friendly else "The tenant has the landlord's permission for paint and small fixings.")
    content.append({"type": "text", "text": prompt})

    response = anthropic.Anthropic().messages.create(
        model="claude-opus-5-5", max_tokens=8000,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": content}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to design this room.")
    return json.loads(next(b.text for b in response.content if b.type == "text"))


def render_makeover(room_jpg, plan, inspirations=()):
    """Returns PNG/JPEG bytes of the 'after' picture. Raises if Gemini isn't set up or has no quota."""
    from google import genai  # only needed for the render, so the planner works without it
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    contents = [plan["render_prompt"],
                types.Part.from_bytes(data=room_jpg, mime_type="image/jpeg")]
    if inspirations:
        contents.append("Inspiration pictures for the look (don't copy their rooms, only the style):")
        contents += [types.Part.from_bytes(data=data, mime_type=media_type) for data, media_type in inspirations]
    response = client.models.generate_content(
        model=GEMINI_MODEL, contents=contents,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            return part.inline_data.data
    raise RuntimeError("Gemini didn't return a picture.")

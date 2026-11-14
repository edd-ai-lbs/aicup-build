"""Voice -> text. Transcribes what the tenant says while filming (vision.py then uses it)."""

import json
import os
import sys

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

from pipeline.media import sound_only

load_dotenv()  # reads ELEVENLABS_API_KEY from .env


def transcribe(video_path):
    """Returns spoken sentences with their start time: [{"start_s": 12.3, "text": "..."}, ...]."""
    sound = sound_only(video_path)  # a few hundred KB instead of the whole video (if ffmpeg is available)
    try:
        with open(sound or video_path, "rb") as f:
            client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
            result = client.speech_to_text.convert(file=f, model_id="scribe_v3", tag_audio_events=False)
    finally:
        if sound:
            os.remove(sound)

    sentences, current = [], None
    for w in result.words:
        if w.type != "word":
            if current and w.type == "spacing":
                current["text"] += w.text
            continue
        if current is None:
            current = {"start_s": round(w.start, 1), "text": ""}
        current["text"] += w.text
        if w.text.rstrip().endswith((".", "?", "!")):
            sentences.append(current)
            current = None
    if current:
        sentences.append(current)
    for s in sentences:
        s["text"] = s["text"].strip()
    return sentences


if __name__ == "__main__":
    # Try it: python pipeline/voice.py data/flat.mp4
    print(json.dumps(transcribe(sys.argv[1]), indent=2))

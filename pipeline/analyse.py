"""One call for the app: room video -> issues in the shared format.

In app/main.py:  from pipeline.analyse import analyse_room

Demo fallback: the AI's results for each video are saved in data/demo_cache/, named after a
fingerprint of the video file. Uploading the exact same video again skips the AI and returns
the saved results in seconds. To prepare a demo video, run it once (live in the app, or locally:
python -m pipeline.analyse data/kitchen.mp4 Kitchen) and commit the new data/demo_cache/*.json.
Delete a JSON file to make that video go through the AI again (e.g. after changing the prompt).
"""

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline.frames import extract_frames
from pipeline.vision import find_issues
from pipeline.voice import transcribe

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "demo_cache"


def _fingerprint(video_path):
    """Same video file -> same short id, whatever it's called."""
    h = hashlib.sha256()
    with open(video_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def analyse_room(video_path, room):
    # Name the pictures after the room so each room's photos are kept apart.
    name = room.lower().replace(" ", "_") or "frame"
    with ThreadPoolExecutor(2) as pool:
        # Pictures are picked in the background while we check the cache and transcribe the voice.
        frames_job = pool.submit(extract_frames, video_path, name=name)  # always: the report needs the pictures
        cache = CACHE_DIR / f"{_fingerprint(video_path)}.json"
        sentences = None if cache.exists() else transcribe(video_path)
        frames = frames_job.result()

    if cache.exists():
        print(f"Using saved AI results for this video: {cache.name}")
        issues = json.loads(cache.read_text())
        for issue in issues:  # point each issue at this run's picture
            nearest = min(frames, key=lambda f: abs(f["frame_time_s"] - issue["frame_time_s"]))
            issue["frame_path"] = nearest["frame_path"]
        return issues

    issues = find_issues(frames, sentences)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(issues, indent=2))
    return issues


if __name__ == "__main__":
    # Prepare a demo video: python -m pipeline.analyse data/kitchen.mp4 Kitchen
    print(json.dumps(analyse_room(sys.argv[1], sys.argv[2]), indent=2))

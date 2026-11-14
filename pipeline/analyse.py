"""One call for the app: room video -> issues in the shared format.

In app/main.py:  from pipeline.analyse import analyse_room
"""

from pipeline.frames import extract_frames
from pipeline.vision import find_issues
from pipeline.voice import transcribe


def analyse_room(video_path, room):
    # Name the pictures after the room so each room's photos are kept apart.
    name = room.lower().replace(" ", "_") or "frame"
    frames = extract_frames(video_path, name=name)
    return find_issues(frames, transcribe(video_path))

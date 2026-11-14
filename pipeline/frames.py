"""Video -> still pictures. Looks at the video every second and keeps the useful moments:
sharp (not blurred by camera movement), not too dark, and not a repeat of the previous view.
At most 30 pictures per clip, spread across the whole video."""

import os
import sys

import cv2
import numpy as np

MAX_SIDE = 1280      # long side in pixels: enough detail for damage, about 1/3 cheaper than 1568
DARK = 25            # average brightness (0-255) below this = too dark to see anything
BLURRY = 0.4         # sharpness below 40% of the clip's typical sharpness = motion blur
REPEAT = 8.0         # average pixel difference below this = same view as the last picture kept


def _measure(image):
    """Brightness, sharpness and a tiny thumbnail used to spot repeated views."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (320, int(320 * gray.shape[0] / gray.shape[1])))
    return float(small.mean()), float(cv2.Laplacian(small, cv2.CV_64F).var()), cv2.resize(small, (32, 32)).astype(np.float32)


def _read_moments(video, times):
    """Read the frames at these times, shrunk, with their measurements."""
    found = []
    for t in times:
        video.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, image = video.read()
        if not ok:
            break
        h, w = image.shape[:2]
        scale = MAX_SIDE / max(h, w)
        if scale < 1:
            image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        brightness, sharpness, thumb = _measure(image)
        found.append({"t": round(t, 1), "jpg": cv2.imencode(".jpg", image)[1], "bright": brightness,
                      "sharp": sharpness, "thumb": thumb})
    return found


def extract_frames(video_path, name="frame", out_dir="data/frames", every_s=1.5, max_frames=30, spare=10):
    """Save the useful frames as JPGs and return [{"frame_time_s": 12.0, "frame_path": "..."}, ...]."""
    video = cv2.VideoCapture(video_path)
    if not video.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    fps = video.get(cv2.CAP_PROP_FPS) or 30
    duration_s = video.get(cv2.CAP_PROP_FRAME_COUNT) / fps

    # 1. Look at a few more moments than we keep (spares replace blurry or repeated ones).
    #    Each moment is kept as a small JPG in memory.
    step_s = max(every_s, duration_s / (max_frames + spare))
    times = [i * step_s for i in range(int(duration_s / step_s) + 1) if i * step_s < duration_s]
    candidates = _read_moments(video, times)
    video.release()
    if not candidates:
        return []

    # 2. Drop dark and blurry moments, and repeats of the view just kept (keeping the sharper one).
    typical = float(np.median([c["sharp"] for c in candidates]))
    useful = [c for c in candidates if c["bright"] >= DARK and c["sharp"] >= BLURRY * typical] or candidates
    kept = []
    for c in useful:
        if kept and np.abs(c["thumb"] - kept[-1]["thumb"]).mean() < REPEAT:
            if c["sharp"] > kept[-1]["sharp"]:
                kept[-1] = c
            continue
        kept.append(c)

    # 3. Too many? Pick evenly across the clip so every part of the room is covered.
    if len(kept) > max_frames:
        kept = [kept[round(i * (len(kept) - 1) / (max_frames - 1))] for i in range(max_frames)]

    os.makedirs(out_dir, exist_ok=True)
    frames = []
    for c in kept:
        path = os.path.join(out_dir, f"{name}_{int(c['t']):03d}.jpg")
        with open(path, "wb") as f:
            f.write(c["jpg"].tobytes())
        frames.append({"frame_time_s": c["t"], "frame_path": path})
    return frames


if __name__ == "__main__":
    # Try it: python pipeline/frames.py data/flat.mp4
    for f in extract_frames(sys.argv[1]):
        print(f)

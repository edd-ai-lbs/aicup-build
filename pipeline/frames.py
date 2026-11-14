"""Video -> still pictures. Takes one frame every ~2 seconds (max 30 per clip)."""

import os
import sys

import cv2


def extract_frames(video_path, name="frame", out_dir="data/frames", every_s=2.0, max_frames=30):
    """Save frames as JPGs and return [{"frame_time_s": 12.0, "frame_path": "..."}, ...]."""
    video = cv2.VideoCapture(video_path)
    if not video.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    fps = video.get(cv2.CAP_PROP_FPS) or 30
    duration_s = video.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    # Long clips: spread the 30 frames evenly instead of stopping early.
    step_s = max(every_s, duration_s / max_frames)

    os.makedirs(out_dir, exist_ok=True)
    frames = []
    t = 0.0
    while t < duration_s and len(frames) < max_frames:
        video.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, image = video.read()
        if not ok:
            break
        # Shrink big phone frames: smaller files, cheaper for the vision model.
        h, w = image.shape[:2]
        scale = 1568 / max(h, w)  # Claude shrinks anything bigger anyway
        if scale < 1:
            image = cv2.resize(image, (int(w * scale), int(h * scale)))
        path = os.path.join(out_dir, f"{name}_{int(t):03d}.jpg")
        cv2.imwrite(path, image)
        frames.append({"frame_time_s": round(t, 1), "frame_path": path})
        t += step_s

    video.release()
    return frames


if __name__ == "__main__":
    # Try it: python pipeline/frames.py data/flat.mp4
    for f in extract_frames(sys.argv[1]):
        print(f)

"""Shrink phone videos before the AI steps, using ffmpeg (bundled by the imageio-ffmpeg package).

- sound_only(): the voice step only needs the sound: a few hundred KB instead of the whole video.
- keyframes(): phone videos store a complete picture about every second ("keyframes");
  reading only those is ~5x faster than decoding every frame of a 4K video.
Both return None if ffmpeg isn't available, so the callers fall back to the slower way.
"""

import os
import re
import subprocess
import tempfile

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:  # not installed, or no binary for this computer
    FFMPEG = None


def sound_only(video_path):
    """Write the video's sound as a small mono speech-quality file; return its path (caller deletes it)."""
    if not FFMPEG:
        return None
    out = tempfile.NamedTemporaryFile(suffix=".m4a", delete=False).name
    result = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", video_path, "-vn",
                             "-ac", "1", "-ar", "16000", "-b:a", "48k", out], capture_output=True)
    if result.returncode != 0 or os.path.getsize(out) == 0:  # e.g. a video with no sound track
        os.remove(out)
        return None
    return out


def keyframes(video_path, max_side=1280, per_second=1):
    """Save at most `per_second` keyframes per second as JPGs in a temp folder.
    Returns [(time_s, jpg_path), ...] or None."""
    if not FFMPEG:
        return None
    folder = tempfile.mkdtemp(prefix="keyframes_")
    result = subprocess.run(
        [FFMPEG, "-loglevel", "info", "-skip_frame", "nokey", "-i", video_path, "-an", "-fps_mode", "vfr",
         "-vf", f"fps={per_second},scale=-2:'min({max_side},ih)':force_original_aspect_ratio=decrease,showinfo",
         "-q:v", "3", os.path.join(folder, "k_%04d.jpg")],
        capture_output=True, text=True)
    if result.returncode != 0:
        return None
    times = [float(t) for t in re.findall(r"pts_time:([\d.]+)", result.stderr)]
    paths = sorted(os.listdir(folder))
    return [(round(t, 1), os.path.join(folder, p)) for t, p in zip(times, paths)]

"""What Matkon takes out of a reel's video: frames to read, what's said, and a photo of the dish.

Frames: one every 1.5 s (fewer on a long reel, 32 at most), 432 px wide, four to a sheet (2×2), so
Claude can read the words on screen without being sent dozens of pictures.
"""
import json
import subprocess

from . import config

TILE_W = 432
PER_SHEET = 4


def duration(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)],
                       capture_output=True, text=True, timeout=60)
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except (ValueError, KeyError):
        return 0.0


def sheets(video, folder):
    """Writes sheets/s01.jpg… and returns [{"file", "times"}]: the times of its frames, in reading order."""
    out = folder / "sheets"
    out.mkdir(exist_ok=True)
    for f in out.glob("*.jpg"):
        f.unlink()
    dur = duration(video) or 60.0
    step = max(1.5, dur / 32)
    r = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(video),
                        "-vf", f"fps=1/{step:.3f},scale={TILE_W}:-2,tile=2x2", "-q:v", "4", str(out / "s%02d.jpg")],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr.strip()[-200:])
    files = sorted(out.glob("s*.jpg"))
    frames = int(dur / step) + 1
    result = []
    # ffmpeg's fps filter gives each slot the last frame before its middle, so frame k is really
    # from k·step + step/2, less one frame (measured: 0.73 s for a 1.5 s step at 30 fps)
    for i, f in enumerate(files):
        times = [round(k * step + step / 2 - 0.03, 2) for k in range(i * PER_SHEET, min((i + 1) * PER_SHEET, frames))]
        result.append({"file": f.name, "times": times})
    (folder / "sheets.json").write_text(json.dumps(result))
    return result


def transcript(video):
    r = subprocess.run(config.WHISPER + [str(video)], capture_output=True, text=True, timeout=3600)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError((r.stderr or "whisper failed").strip()[-300:])
    if out.get("error"):
        raise RuntimeError(out["error"])
    return out


def photo(video, at, dest):
    """A full-size still at `at` seconds (the dish), as the recipe's photo."""
    dur = duration(video)
    at = max(0.0, min(float(at), max(0.0, dur - 0.2)))
    tmp = dest.with_suffix(".tmp.jpg")
    r = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", f"{at:.2f}", "-i", str(video),
                        "-frames:v", "1", "-vf", "scale='min(1080,iw)':-2", "-q:v", "3", str(tmp)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(dest)
    return True

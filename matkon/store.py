"""The reels Matkon knows about, one folder each (STATE/reels/<code>/), and where each one stands.

A reel comes in as its post (post.json: who made it, the caption) and then its video, both sent by the
browser extension, and the stages (run.py) take it from there. A post with no video yet is "wanted":
the extension brings its video the next time it's on Instagram.

A recipe page or photos of a recipe (sources.py) live here too, with post.json's "source" saying which
("web", "photo"; a reel has none): they have no video, so they skip the stages a video needs and are
never "wanted".
"""
import json
import time

from . import config, instagram

STAGES = ["video", "transcript", "frames", "link", "recipe", "note", "translate"]
FILES = {"video": "video.mp4", "transcript": "transcript.json", "frames": "sheets.json", "link": "linked.json",
         "recipe": "recipe.json", "note": "note.json", "translate": "translated.json"}
# the stages of a recipe that isn't a reel: a page is read ("link" writes linked.json), photos are already in
SOURCES = {"web": ["link", "recipe", "note", "translate"], "photo": ["recipe", "note", "translate"]}
MAX_TRIES = 3


def read(p, default=None):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default


def write(p, data):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    tmp.replace(p)


def folder(code):
    f = config.REELS / code
    f.mkdir(parents=True, exist_ok=True)
    return f


def status_of(f):
    return read(f / "status.json", {"error": None, "tries": 0})


def set_status(f, **kw):
    s = status_of(f)
    s.update(kw, updated=int(time.time()))
    write(f / "status.json", s)


def keep_post(p, rank=None, by=None):
    """Saves what's known about a reel; a new one is marked with when it was found, and who added it.
    True when it's new."""
    f = folder(p["code"])
    old = read(f / "post.json", {})
    p = {**old, **{k: v for k, v in p.items() if v not in (None, "") or k not in old}}
    p.setdefault("found", time.time() - (rank or 0))
    if by and not p.get("added_by"):
        p["added_by"] = by
    write(f / "post.json", p)
    return not old


def has(code):
    """Whether the reel's video is in (so the browser needn't bring it)."""
    return (config.REELS / code / "video.mp4").exists()


def source(post):
    """"reel", "web" or "photo"."""
    return (post or {}).get("source") or "reel"


def stages(post):
    """The stages this one goes through, in order."""
    return SOURCES.get(source(post), STAGES)


def finished(f, post=None):
    return all((f / FILES[s]).exists() for s in stages(post if post is not None else read(f / "post.json", {})))


def pending():
    """Reels with their video in (and pages and photos), not finished yet and not given up on, oldest
    found first."""
    out = []
    for f in config.REELS.iterdir() if config.REELS.exists() else []:
        p = read(f / "post.json")
        if not p or (source(p) == "reel" and not (f / "video.mp4").exists()) or finished(f, p):
            continue
        if status_of(f).get("tries", 0) >= MAX_TRIES:
            continue
        out.append((p.get("found", 0), f.name))
    return [c for _, c in sorted(out)]


def wanted(limit=20):
    """Reels whose video the browser should bring: in the queue ("Add a reel", a redo from the video),
    not a photo post, not given up on. Oldest first."""
    out = []
    for f in config.REELS.iterdir() if config.REELS.exists() else []:
        p = read(f / "post.json")
        if not p or source(p) != "reel" or (f / "video.mp4").exists() or p.get("media_type") not in (2, None):
            continue
        if status_of(f).get("tries", 0) >= MAX_TRIES:
            continue
        out.append((p.get("found", 0), f.name))
    return [c for _, c in sorted(out)][:limit]


def give_up(code, why):
    """The browser says Instagram can't give this one (gone, private, or not a video)."""
    f = config.REELS / code
    if (f / "post.json").exists():
        set_status(f, error=f"video: {why}", tries=MAX_TRIES, stage="video")


def queue(what, by):
    """Puts a reel in the queue ("Add a reel"); the browser brings its video the next time it's on
    Instagram. Its code, or None when that isn't a reel link."""
    code = instagram.code_in(what)
    if not instagram.CODE.match(code):
        return None
    f = folder(code)
    if not (f / "post.json").exists():
        keep_post({"code": code, "user": "", "caption": "", "media_type": None,
                   "url": f"https://www.instagram.com/reel/{code}/"}, by=by)
    elif status_of(f).get("tries", 0) >= MAX_TRIES and not (f / "video.mp4").exists():
        set_status(f, error=None, tries=0, stage="waiting")       # asked for again: worth another try
    return code

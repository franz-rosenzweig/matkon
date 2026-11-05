"""What the browser extension sends about a saved post, made into what Matkon keeps.

Matkon's server never talks to Instagram. The extension (extension/) does that part from your own
browser, signed in as you, while you're on instagram.com: it reads the newest saves, sends the ones in
your recipe collection here (the post, then its video), and that's all Instagram ever sees of Matkon.
Your Instagram sign-in never leaves the browser.
"""
import re

CODE = re.compile(r"^[\w-]{5,40}$")


def code_in(s):
    """A reel's code from its link (or the code itself)."""
    m = re.search(r"instagram\.com/(?:[\w.]+/)?(?:reels?|p|tv)/([\w-]+)", s or "")
    return m.group(1) if m else (s or "").strip().strip("/")


def _s(v, n):
    return str(v or "").strip()[:n]


def post(media):
    """What Matkon keeps of a saved post: who made it, the caption, what kind of post it is."""
    user = media.get("user") or {}
    cap = media.get("caption")
    cap = cap.get("text") if isinstance(cap, dict) else cap
    try:
        dur = float(media.get("video_duration")) if media.get("video_duration") is not None else None
    except (TypeError, ValueError):
        dur = None
    try:
        kind = int(media.get("media_type")) if media.get("media_type") is not None else None
    except (TypeError, ValueError):
        kind = None
    code = _s(media.get("code"), 40)
    return {
        "code": code,
        "pk": _s(media.get("pk"), 40),
        "user": _s(user.get("username"), 60),
        "name": _s(user.get("full_name"), 120),
        "caption": _s(cap, 8000),
        "taken_at": media.get("taken_at") if isinstance(media.get("taken_at"), int) else None,
        "duration": dur,
        "media_type": kind,                     # 2 = video, 8 = carousel, 1 = photo
        "product": _s(media.get("product_type"), 30),
        "url": f"https://www.instagram.com/reel/{code}/",
    }

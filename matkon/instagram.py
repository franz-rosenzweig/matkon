"""A saved post as Instagram gives it, made into what Matkon keeps, and the bits both ways of reaching
Instagram share. No requests here: the browser extension (extension/) or the server's own look with a
pasted sign-in (igserver.py) does the asking.
"""
import json
import re

CODE = re.compile(r"^[\w-]{5,40}$")


def code_in(s):
    """A reel's code from its link (or the code itself)."""
    m = re.search(r"instagram\.com/(?:[\w.]+/)?(?:reels?|p|tv)/([\w-]+)", s or "")
    return m.group(1) if m else (s or "").strip().strip("/")


ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def pk_of(code):
    """A reel's number, which its code spells in base 64 (the API asks by number)."""
    s = code[:-28] if len(code) > 28 else code
    n = 0
    for ch in s:
        i = ALPHABET.find(ch)
        if i < 0:
            return None
        n = n * 64 + i
    return str(n)


def video_of(media):
    """The reel's video: the biggest one up to 1080 wide."""
    v = sorted((x for x in media.get("video_versions") or [] if x and x.get("url")), key=lambda x: -(x.get("width") or 0))
    pick = next((x for x in v if (x.get("width") or 0) <= 1080), v[-1] if v else None)
    return pick["url"] if pick else None


def parse_cookies(text):
    """{name: value} for instagram.com from what a person pastes: a Cookie header ("a=b; c=d"), a
    Netscape cookies.txt, or the JSON list cookie-export extensions make."""
    jar = {}
    text = (text or "").strip()
    if text.lower().startswith("cookie:"):
        text = text[7:].strip()
    if text.startswith(("[", "{")):
        try:
            data = json.loads(text)
        except ValueError:
            data = []
        for c in data if isinstance(data, list) else data.get("cookies", []):
            if isinstance(c, dict) and "instagram.com" in str(c.get("domain", ".instagram.com")) and c.get("name"):
                jar[str(c["name"])] = str(c.get("value", ""))
    elif "\t" in text:
        for line in text.splitlines():
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            p = line.split("\t")
            if not line.startswith("#") and len(p) == 7 and "instagram.com" in p[0]:
                jar[p[5]] = p[6].strip()
    else:
        for part in text.replace("\n", ";").split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                if re.fullmatch(r"[\w.-]{1,64}", k.strip()):
                    jar[k.strip()] = v.strip()
    return {k: v for k, v in jar.items() if len(v) < 4096}


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

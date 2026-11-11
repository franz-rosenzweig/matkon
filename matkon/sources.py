"""Recipes that don't come from a reel: a recipe page on the web, added by its link, or photos of a
recipe (a cookbook page, a handwritten card). Each gets a folder in reels/ like a reel's, with a
post.json whose "source" says which ("web", "photo"), and goes through the same stages less the ones a
video needs (store.SOURCES): a page is read first (the "link" stage, linked.py), then recipe, note and
translate; photos go straight to the recipe. What comes out is an ordinary recipe.

Codes: web-<10 hex>, from the page's tidied address (so the same page again is the same recipe), and
pic-<10 hex>, from the pictures themselves.

Matkon's server never asks Instagram, Facebook, Threads or any other part of Meta for anything: their
links are turned away here, before anything is fetched, and linked.py turns away redirects to them.
Nor does it read pages on this machine or a private network.
"""
import base64
import binascii
import hashlib
import json
import re
import shutil
import subprocess
import time
import urllib.parse

from . import config, linked, recipe, store

MAX_PHOTOS = 4
MAX_BODY = 30_000_000           # the request that brings them (server.py); everything else stays at 2 MB
MAX_SIDE = 2000                 # photos are kept at most this long on their long side
REEL = re.compile(r"instagram\.com/(?:[\w.]+/)?(?:reels?|p|tv)/[\w-]{5,}")     # the same as Settings' "Add a reel"
TRACKING = re.compile(r"^(?:utm_\w+|fbclid|gclid|gbraid|wbraid|dclid|msclkid|yclid|twclid|mc_cid|mc_eid|igshid|igsh|_ga|_gl|"
                      r"mkt_tok|ref_src)$", re.I)
SHIMS = ("l.facebook.com", "lm.facebook.com", "l.instagram.com", "l.threads.net", "l.threads.com")
DATA = re.compile(r"^data:image/(?:jpeg|jpg|png|webp);base64,", re.I)
MISSING = {"reel": {"en": "Not in the reel", "he": "חסר בסרטון"},
           "web": {"en": "Not on the page", "he": "חסר בדף"},
           "photo": {"en": "Not in the photos", "he": "חסר בתמונות"},
           "photo1": {"en": "Not in the photo", "he": "חסר בתמונה"}}


# ---- what a note or Cookbook calls them --------------------------------------------------------------

def author(post):
    """Whose recipe it is: @creator for a reel, the site (its own name, else its address) for a page,
    nobody for photos."""
    src = store.source(post)
    if src == "reel":
        return "@" + post["user"] if post.get("user") else ""
    return (post.get("name") or post.get("user") or "") if src == "web" else ""


def missing_label(post, lang):
    """The heading over what a cook would still need: "Not in the reel", "Not on the page"…"""
    src = store.source(post)
    if src == "photo" and (post or {}).get("photos") == 1:
        src = "photo1"
    return MISSING[src].get(lang) or MISSING[src]["en"]


# ---- a page, by its link ------------------------------------------------------------------------

def is_reel_link(text):
    """Whether what was sent holds an Instagram reel or post link (those go to "Add a reel")."""
    return bool(REEL.search(str(text or "")))


def _unwrap(u):
    """The page behind Facebook's and Instagram's link redirects (l.facebook.com/l.php?u=…), read from
    the link itself: nothing is asked of them."""
    for _ in range(3):
        try:
            s = urllib.parse.urlsplit(u)
        except ValueError:
            return u
        inner = urllib.parse.parse_qs(s.query).get("u", [""])[0]
        if (s.hostname or "").lower() not in SHIMS or not re.match(r"https?://", inner, re.I):
            return u
        u = inner
    return u


def address(text):
    """(the page's address, tidied; the key its code comes from), from a link or from text with a link
    in it (a share brings the page's title along). Raises ValueError."""
    t = str(text or "").strip()[:4000]
    m = re.search(r"https?://[^\s<>\"']+", t, re.I)
    if m:
        u = m.group(0).rstrip(".,;:!?'\"")
    elif re.match(r"[a-z][\w+.-]*:(?!\d)", t, re.I):
        raise ValueError("Matkon reads web pages only: links that start with http or https.")
    elif re.fullmatch(r"(?:[\w-]+\.)+[a-z][\w-]*(?::\d+)?(?:[/?#]\S*)?", t, re.I):
        u = "https://" + t                                    # a bare address, the way a browser takes it
    else:
        raise ValueError("That isn't a web link.")
    u = _unwrap(u)
    try:
        s = urllib.parse.urlsplit(u)
        port = s.port
    except ValueError:
        raise ValueError("That isn't a web link.")
    scheme, host = s.scheme.lower(), (s.hostname or "").rstrip(".").lower()
    if scheme not in ("http", "https"):
        raise ValueError("Matkon reads web pages only: links that start with http or https.")
    if not host:
        raise ValueError("That isn't a web link.")
    if not host.isascii():
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            raise ValueError("That isn't a web link.")
    netloc = (f"[{host}]" if ":" in host else host) + (f":{port}" if port and port != {"http": 80, "https": 443}[scheme] else "")
    path = urllib.parse.quote(s.path or "/", safe="/%:@!$&'()*+,;=-._~")
    query = "&".join(urllib.parse.quote(q, safe="=%/:@!$'()*+,;?-._~") for q in s.query.split("&")
                     if q and not TRACKING.match(urllib.parse.unquote_plus(q.split("=", 1)[0])))
    url = f"{scheme}://{netloc}{path}" + (f"?{query}" if query else "")
    key = re.sub(r"^www\.", "", netloc) + (path.rstrip("/") or "/") + (f"?{query}" if query else "")
    return url, key


def domain(url):
    """The site, as a person says it: smittenkitchen.com."""
    try:
        host = (urllib.parse.urlsplit(url or "").hostname or "").rstrip(".").lower()
    except ValueError:
        return ""
    if "xn--" in host:
        try:
            host = host.encode("ascii").decode("idna")       # מתכונים.co.il, not xn--9dbiekbo1e.co.il
        except UnicodeError:
            pass
    return re.sub(r"^www\.", "", host)


def add_link(text, by):
    """A recipe page, from "Add from a link": its code, and whether it's new or already made. It's read
    in the background (run.py sync). Raises ValueError for a link Matkon doesn't read."""
    url, key = address(text)
    if linked.is_meta(url):
        raise ValueError("Matkon doesn't read Instagram, Facebook or Threads pages. For a reel, send the reel's own link.")
    if not linked.public(url):
        raise ValueError("That address is on a private network. Matkon reads public pages only.")
    code = "web-" + hashlib.sha256(key.encode()).hexdigest()[:10]
    f = store.folder(code)
    known = store.read(f / "post.json")
    if not known:
        store.keep_post({"code": code, "source": "web", "url": url, "user": domain(url), "name": "", "caption": ""}, by=by)
    elif store.status_of(f).get("tries", 0) >= store.MAX_TRIES and not store.finished(f, known):
        store.set_status(f, error=None, tries=0, stage="waiting")       # asked for again: worth another try
    return {"ok": True, "code": code, "new": not known, "done": store.finished(f)}


def stage_page(f, post):
    """A page's "link" stage: reads it (linked.py: its recipe data and its text), and keeps what it says
    about itself in post.json (the site's name, when it was published) and its photo as photo.jpg."""
    lk = linked.fetch(post["url"], keep_text=True)
    if lk.get("kind") == "error":
        raise RuntimeError("the page couldn't be read (" + str(lk.get("error") or "")[:160] + ")")
    page = lk.get("page") or {}
    final = lk.get("final") or post["url"]
    try:
        final = address(final)[0]
    except ValueError:
        pass
    news = {"code": post["code"], "name": page.get("site") or "", "taken_at": page.get("published")}
    if final != post["url"]:                                  # a short link, or the site's own redirect
        news.update(url=final, user=domain(final) or post.get("user"), sent=post["url"])
    store.keep_post(news)
    post.update(store.read(f / "post.json", {}))
    if not _page_photo(f, page.get("images") or []):
        (f / "photo.jpg").unlink(missing_ok=True)
    store.write(f / "linked.json", lk)


def _page_photo(f, urls):
    """The page's photo, as photo.jpg: the recipe's own, else the one it gives for shares. Skips what
    can't be read and anything too small to be a photo of the dish (a logo, a tracking pixel)."""
    for u in urls[:4]:
        try:
            data = linked.download(u)
        except Exception:  # noqa: BLE001 - a photo we can't get just means the next one, or none
            continue
        kind = _kind(data, web=True)
        if not kind:
            continue
        src = f / f".download.{kind}"
        src.write_bytes(data)
        try:
            if to_jpeg(src, f / ".photo.jpg") and min(_size(f / ".photo.jpg")) >= 200:
                (f / ".photo.jpg").replace(f / "photo.jpg")
                return True
        finally:
            src.unlink(missing_ok=True)
            (f / ".photo.jpg").unlink(missing_ok=True)
    return False


def page_text(lk):
    """The page as Claude reads it: its recipe data (when there is some) and its text."""
    out = linked.as_prompt(lk)
    if lk.get("kind") == "recipe" and lk.get("text"):
        out += "\n\nThe page's text (the writer's notes and tips are here; it may be cut short):\n" + lk["text"]
    return out


# ---- photos of a recipe ---------------------------------------------------------------------------

def _kind(data, web=False):
    """The picture's type, from its first bytes: jpg, png or webp (and on a page, gif or avif too)."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if web and data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if web and data[4:12] in (b"ftypavif", b"ftypavis"):
        return "avif"
    return None


def to_jpeg(src, dest, side=MAX_SIDE):
    """A picture as a JPEG at most `side` on its long side, turned upright (ffmpeg follows a phone's
    EXIF orientation). False when ffmpeg can't read it."""
    tmp = dest.with_name(dest.stem + ".tmp.jpg")
    scale = f"scale='if(gte(iw,ih),min({side},iw),-2)':'if(gte(iw,ih),-2,min({side},ih))'"
    try:
        r = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src), "-frames:v", "1",
                            "-vf", scale, "-q:v", "3", str(tmp)], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        r = None
    if not r or r.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(dest)
    return True


def _size(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json",
                        str(path)], capture_output=True, text=True, timeout=60)
    try:
        s = json.loads(r.stdout)["streams"][0]
        return int(s["width"]), int(s["height"])
    except (ValueError, KeyError, IndexError):
        return 0, 0


def photos(f):
    """The photos' files, in order (image1.jpg…)."""
    return sorted(f.glob("image*.jpg"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))


def add_photos(images, by):
    """Photos of a recipe, as data: URLs (one to four; JPEG, PNG or WebP): kept as image1.jpg… and read
    in the background (run.py sync). The same photos again are the same recipe. Raises ValueError."""
    if not isinstance(images, list) or not 1 <= len(images) <= MAX_PHOTOS:
        raise ValueError(f"Send one to {MAX_PHOTOS} photos.")
    raw = []
    for n, x in enumerate(images, 1):
        m = DATA.match(x) if isinstance(x, str) else None
        if not m:
            raise ValueError(f"Photo {n} isn't a JPEG, PNG or WebP picture.")
        try:
            data = base64.b64decode(re.sub(r"\s+", "", x[m.end():]), validate=True)
        except (binascii.Error, ValueError):
            raise ValueError(f"Photo {n} didn't come through whole.")
        kind = _kind(data)
        if not kind:
            raise ValueError(f"Photo {n} isn't a JPEG, PNG or WebP picture.")
        raw.append((data, kind))
    code = "pic-" + hashlib.sha256(b"".join(hashlib.sha256(d).digest() for d, _ in raw)).hexdigest()[:10]
    f = config.REELS / code
    known = store.read(f / "post.json")
    if known:
        if store.status_of(f).get("tries", 0) >= store.MAX_TRIES and not store.finished(f, known):
            store.set_status(f, error=None, tries=0, stage="waiting")
        return {"ok": True, "code": code, "new": False, "done": store.finished(f, known)}
    f = store.folder(code)
    try:
        for n, (data, kind) in enumerate(raw, 1):
            src = f / f".upload-{n}.{kind}"
            src.write_bytes(data)
            done = to_jpeg(src, f / f"image{n}.jpg")
            src.unlink(missing_ok=True)
            if not done:
                raise ValueError(f"Photo {n} couldn't be read.")
    except BaseException:
        shutil.rmtree(f, ignore_errors=True)
        raise
    store.keep_post({"code": code, "source": "photo", "user": "", "name": "", "caption": "", "photos": len(raw)}, by=by)
    return {"ok": True, "code": code, "new": True, "done": False}


# ---- the recipe -----------------------------------------------------------------------------------

def stage_recipe(f, post):
    """The recipe stage for a page or photos: the same call and the same answer as a reel's, with the
    source's own prompt (recipe.py). The photo: the page's (stage_page kept it), or the first photo."""
    src = store.source(post)
    if src == "web":
        msg = recipe.build_web_message(post, page_text(store.read(f / "linked.json", {}) or {}))
    else:
        pics = photos(f)
        if not pics:
            raise RuntimeError("the photos aren't there")
        msg = recipe.build_photo_message(pics)
    model = config.model()
    answer = recipe.ask_claude(msg, model)
    (f / "answer.txt").write_text(answer)            # Claude's own words, for when a recipe looks wrong
    r = recipe.parse(answer)
    r["made"] = int(time.time())
    r["model"] = model
    if src == "photo":
        shutil.copyfile(pics[0], f / "photo.jpg")
    if (f / "photo.jpg").exists():
        r["photo"] = "photo.jpg"
    store.write(f / "recipe.json", r)

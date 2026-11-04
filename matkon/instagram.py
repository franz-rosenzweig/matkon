"""Reading the saved collection and downloading its reels, with a signed-in cookies file.

Instagram's web app lists every saved post at /api/v1/feed/saved/posts/ (newest save first, 21 a
page), and each post says which collections it's in (saved_collection_ids). The per-collection
address the website used to have answers with a page now, so Matkon pages through the saved posts
and keeps the ones in the recipe collection. A normal run looks at the newest few pages only.

The cookies are never printed or logged. yt-dlp gets a copy of the jar, since it writes it back.
"""
import json
import os
import random
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import config

APP_ID = "936619743392459"   # the website's own app id, which its API calls send
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/26.0 Safari/605.1.15")


class SignedOut(Exception):
    """Instagram sent us to its sign-in page: the session in the cookies file has lapsed."""


def parse_cookies(text):
    """{name: value} from a Netscape cookies.txt, or from the JSON cookie lists browser extensions export."""
    jar = {}
    text = (text or "").strip()
    if text.startswith("[") or text.startswith("{"):
        try:
            data = json.loads(text)
        except ValueError:
            data = []
        for c in data if isinstance(data, list) else data.get("cookies", []):
            if isinstance(c, dict) and "instagram.com" in str(c.get("domain", ".instagram.com")) and c.get("name"):
                jar[c["name"]] = str(c.get("value", ""))
        return jar
    for line in text.splitlines():
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        p = line.split("\t")
        if not line.startswith("#") and len(p) == 7 and "instagram.com" in p[0]:
            jar[p[5]] = p[6]
    return jar


def netscape(jar):
    """A cookies.txt yt-dlp can read."""
    lines = ["# Netscape HTTP Cookie File"]
    for k, v in jar.items():
        lines.append("\t".join([".instagram.com", "TRUE", "/", "TRUE", str(int(time.time()) + 365 * 86400), k, v]))
    return "\n".join(lines) + "\n"


def _jar(cookies=None):
    path = cookies or config.COOKIES
    try:
        jar = parse_cookies(path.read_text())
    except OSError:
        raise SignedOut(f"no cookies file at {path}")
    if not jar.get("sessionid"):
        raise SignedOut("the cookies file has no Instagram sign-in (sessionid)")
    return jar


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _get(path, params=None, cookies=None):
    jar = _jar(cookies)
    url = "https://www.instagram.com" + path + (("?" + urllib.parse.urlencode(params)) if params else "")
    req = urllib.request.Request(url, headers={
        "Cookie": "; ".join(f"{k}={v}" for k, v in jar.items()), "User-Agent": UA,
        "X-IG-App-ID": APP_ID, "X-CSRFToken": jar.get("csrftoken", ""),
        "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.instagram.com/", "Accept": "*/*"})
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=30) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 401, 403):
            raise SignedOut(f"Instagram answered {e.code}")
        raise RuntimeError(f"Instagram answered {e.code}")
    try:
        return json.loads(body)
    except ValueError:
        raise SignedOut("Instagram sent a page instead of data")


def saved_posts(pages, cookies=None):
    """The newest saved posts, up to `pages` pages of them, gently (a few seconds between pages)."""
    max_id = None
    for n in range(pages):
        d = _get("/api/v1/feed/saved/posts/", {"max_id": max_id} if max_id else None, cookies)
        for x in d.get("items", []):
            if x.get("media"):
                yield x["media"]
        if not d.get("more_available") or not d.get("next_max_id"):
            return
        max_id = d["next_max_id"]
        if n + 1 < pages:
            time.sleep(2 + random.random() * 2)


def collections_of(media):
    return [str(c) for c in (media.get("saved_collection_ids") or [])]


def post(media):
    """What Matkon keeps of a saved post: who made it, the caption, the cover picture."""
    user = media.get("user") or {}
    covers = ((media.get("image_versions2") or {}).get("candidates") or [])
    covers = sorted(covers, key=lambda c: c.get("width") or 0, reverse=True)
    return {
        "code": media.get("code"),
        "pk": str(media.get("pk") or ""),
        "user": user.get("username") or "",
        "name": user.get("full_name") or "",
        "caption": ((media.get("caption") or {}).get("text") or "").strip(),
        "taken_at": media.get("taken_at"),
        "duration": media.get("video_duration"),
        "media_type": media.get("media_type"),          # 2 = video, 8 = carousel, 1 = photo
        "product": media.get("product_type") or "",
        "cover_url": covers[0]["url"] if covers else None,
        "url": f"https://www.instagram.com/reel/{media.get('code')}/",
    }


def download_cover(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(dest)


def signed_in(cookies=None):
    """Whether Instagram still takes this sign-in: one small request."""
    try:
        _get("/api/v1/feed/saved/posts/", None, cookies)
        return True
    except SignedOut:
        return False


def download_video(code, dest, cookies=None):
    """The reel's video, with yt-dlp and a copy of the sign-in. Raises SignedOut or RuntimeError."""
    with tempfile.TemporaryDirectory(dir=config.STATE, prefix=".dl-") as tmp:   # on disk: /tmp is RAM
        jar = Path(tmp) / "cookies.txt"
        jar.write_text((cookies or config.COOKIES).read_text())
        os.chmod(jar, 0o600)
        r = subprocess.run(config.YTDLP + [
            "--cookies", str(jar), "--no-playlist", "--no-progress",
            "-f", "bv*[height<=1920]+ba/b[height<=1920]/bv*+ba/b", "--merge-output-format", "mp4",
            "--max-filesize", "300M", "-o", f"{tmp}/v.%(ext)s", f"https://www.instagram.com/reel/{code}/"],
            capture_output=True, text=True, timeout=900)
        vids = [f for f in Path(tmp).iterdir() if f.suffix in (".mp4", ".mov", ".webm", ".mkv") and f.stat().st_size > 0]
        if not vids:
            err = (r.stderr or "").strip().splitlines()
            err = err[-1] if err else "yt-dlp failed"
            if re.search(r"log ?in|checkpoint|cookies|parse JSON|HTTP Error (401|403)", err, re.I):
                raise SignedOut(err[:200])
            raise RuntimeError(re.sub(r"^ERROR:\s*", "", err)[:200])
        vids[0].replace(dest)

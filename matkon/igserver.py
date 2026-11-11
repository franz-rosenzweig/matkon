"""Matkon's own look at Instagram, with a sign-in an account pasted into Settings (its cookies).

This is the other way to the browser extension, and the riskier one: the server uses the sign-in by
itself, so Instagram sees a second place using it. It's kept as close to the browser it came from as
it can be, and as gentle as the extension:

- curl_cffi makes each request look like that browser's (its TLS and HTTP/2, not Python's), with the
  same User-Agent and languages, and the website's own headers. Cookies Instagram changes are kept.
- The newest saves, a page or two, every `check_hours`; it stops at the first reel Matkon has.
- A few videos an hour at most (`per_hour`), seconds apart. Reels from "Add a reel" come the same way.
- The first refusal stops it. A lapsed sign-in waits for a new one; "slow down" waits a day.
- Only from run.py's runs (cron: the daytime hours), and never while the kitchen is paused.

Needs curl_cffi (config.IG_PY). Without it, it doesn't go at all.
"""
import random
import re
import time
import urllib.parse

from . import accounts, config, instagram, kitchen, reel, store

APP_ID = "936619743392459"          # the website's own app id, which its requests send


def _domain():
    """Where the cookies belong: Instagram's, or the pretend Instagram's host in a test."""
    host = urllib.parse.urlsplit(config.IG_ORIGIN).hostname or ""
    return ".instagram.com" if host.endswith("instagram.com") else host


def _mine(c):
    return (c.domain or "").lstrip(".").endswith(_domain().lstrip("."))


class Stop(Exception):
    """Instagram said no: signed-out, busy, gone or instagram (something else)."""


def _wait(lo, hi):
    if not config.env("MATKON_IG_FAST"):            # tools/test_igserver.py: no waiting
        time.sleep(lo + random.random() * (hi - lo))


def target(ua):
    """The curl_cffi browser closest to the one the sign-in came from."""
    from curl_cffi.requests import BrowserType
    names = [b.value for b in BrowserType]

    def best(pattern, ver):
        have = sorted((int(m.group(1)), n) for n in names if (m := re.fullmatch(pattern, n)))
        under = [n for v, n in have if v <= ver]
        return (under or [n for _, n in have] or ["chrome"])[-1]
    ua = ua or ""
    if m := re.search(r"Firefox/(\d+)", ua):
        return best(r"firefox(\d+)", int(m.group(1)))
    if "Chrome/" not in ua and re.search(r"iPhone|iPad", ua) and (m := re.search(r"Version/(\d+)(?:\.(\d))?", ua)):
        return best(r"safari(\d{3})_ios", int(m.group(1)) * 10 + int(m.group(2) or 0))
    if "Chrome/" not in ua and (m := re.search(r"Version/(\d+)(?:\.(\d))?.*Safari", ua)):
        return best(r"safari(\d{3})", int(m.group(1)) * 10 + int(m.group(2) or 0))
    m = re.search(r"Chrome/(\d+)", ua)
    v = int(m.group(1)) if m else 999
    if "Android" in ua:
        return best(r"chrome(\d+)_android", v)
    return best(r"chrome(\d+)_macos", v) if "Macintosh" in ua else best(r"chrome(\d+)", v)


def accept_language(langs, ua):
    """navigator.languages as that browser's Accept-Language ("en-US,en;q=0.5" in Firefox, 0.9 elsewhere)."""
    xs = [x.strip() for x in (langs or "").split(",") if re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*", x.strip())][:6]
    if not xs:
        return None
    ff = "Firefox/" in (ua or "")
    return ",".join(x if i == 0 else f"{x};q={(round(1 - i / len(xs), 1) if ff else round(1 - i / 10, 1))}" for i, x in enumerate(xs))


class Instagram:
    def __init__(self, info):
        from curl_cffi import requests
        self.info = info
        self.ua = info.get("ua") or ""
        self.s = requests.Session(impersonate=target(self.ua))
        for k, v in (info.get("jar") or {}).items():
            self.s.cookies.set(k, v, domain=_domain())
        self.claim = info.get("claim") or "0"

    def _cookie(self, name):
        for c in self.s.cookies.jar:
            if c.name == name and _mine(c):
                return c.value
        return (self.info.get("jar") or {}).get(name, "")

    def jar(self):
        """The cookies as they are now (Instagram changes some as it goes)."""
        jar = dict(self.info.get("jar") or {})
        jar.update({c.name: c.value for c in self.s.cookies.jar if _mine(c)})
        return jar

    def get(self, path):
        h = {"Accept": "*/*", "X-IG-App-ID": APP_ID, "X-IG-WWW-Claim": self.claim, "X-CSRFToken": self._cookie("csrftoken"),
             "X-Requested-With": "XMLHttpRequest", "Referer": config.IG_ORIGIN + "/",
             "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin"}
        if self.ua:
            h["User-Agent"] = self.ua
        if accept_language(self.info.get("langs"), self.ua):
            h["Accept-Language"] = accept_language(self.info.get("langs"), self.ua)
        try:
            r = self.s.get(config.IG_ORIGIN + path, headers=h, allow_redirects=False, timeout=30)
        except Exception as e:  # noqa: BLE001 - curl's errors: no answer
            raise Stop("instagram") from e
        if r.headers.get("x-ig-set-www-claim"):
            self.claim = r.headers["x-ig-set-www-claim"]
        text = r.text or ""
        if r.status_code in (301, 302, 303, 307, 308):
            raise Stop("signed-out" if re.search(r"/accounts/login|/challenge|/checkpoint", r.headers.get("location", "")) else "instagram")
        if r.status_code == 429 or re.search(r'"(feedback_required|rate_limit_error)"|Please wait a few minutes', text):
            raise Stop("busy")
        if r.status_code in (401, 403) or re.search(r'"(login_required|checkpoint_required|challenge_required)"', text):
            raise Stop("signed-out")
        if r.status_code in (400, 404):
            raise Stop("gone")
        if r.status_code != 200:
            raise Stop("instagram")
        try:
            return r.json()
        except ValueError:
            raise Stop("signed-out")                 # a page instead of data: the sign-in page

    def video(self, url, dest):
        h = {"Accept": "*/*", "Referer": config.IG_ORIGIN + "/"}
        if self.ua:
            h["User-Agent"] = self.ua
        r = self.s.get(url, headers=h, timeout=180)
        if r.status_code not in (200, 206) or not r.content:
            raise RuntimeError(f"the video didn't come ({r.status_code})")
        dest.write_bytes(r.content)


def _in(media, cid):
    return str(cid) in [str(c) for c in media.get("saved_collection_ids") or []]


def _keep_video(ig, media, by):
    """The post, then its video. True when a video came in."""
    p = instagram.post(media)
    store.keep_post(p, by=by)
    if p["media_type"] != 2:
        store.give_up(p["code"], "not a video post")
        return False
    url = instagram.video_of(media)
    if not url:
        store.give_up(p["code"], "no video")
        return False
    f = config.REELS / p["code"]
    if (f / "video.mp4").exists():
        return False
    tmp = f / ".download.mp4"
    try:
        ig.video(url, tmp)
        if reel.duration(tmp) <= 0:
            raise RuntimeError("that isn't a whole video")
        tmp.replace(f / "video.mp4")
    except RuntimeError as e:
        st = store.status_of(f)
        store.set_status(f, error=f"video: {e}", tries=st.get("tries", 0) + 1, stage="video")
        return False
    finally:
        tmp.unlink(missing_ok=True)
    return True


def run(aid, wanted, say=print):
    """One account's look, if it's time: the newest saves (every check_hours), then the videos it lacks
    (the new ones and `wanted`, a few an hour). Returns how many videos came in."""
    info = kitchen.signin(aid)
    if not info.get("jar"):
        return 0
    st = config.settings()
    now = time.time()
    if info.get("error") == "signed-out":
        return 0                                     # waits for a new sign-in
    if info.get("wait_until", 0) > now:
        return 0
    cid = kitchen.of(aid)["collection_id"]
    due = bool(cid) and now - (info.get("checked") or 0) > st["check_hours"] * 3600
    brought = [t for t in info.get("brought") or [] if t > now - 3600]
    left = st["per_hour"] - len(brought)
    if not due and (not wanted or left <= 0):
        return 0
    ig = Instagram(info)
    queue = {}
    came, error = 0, None
    try:
        if due:
            max_id, wanted_now = None, set(store.wanted(10000))
            for n in range(max(1, min(5, st["scan_pages"]))):
                if n:
                    _wait(4, 9)
                d = ig.get("/api/v1/feed/saved/posts/" + (f"?max_id={urllib.parse.quote(max_id)}" if max_id else ""))
                mine = [x["media"] for x in d.get("items") or [] if (x.get("media") or {}).get("code") and _in(x["media"], cid)]
                known = [m["code"] for m in mine if (config.REELS / m["code"] / "post.json").exists()]
                for m in mine:
                    if m["code"] not in known or m["code"] in wanted_now:
                        queue[m["code"]] = m
                if known or not d.get("more_available") or not d.get("next_max_id"):
                    break                            # what's further down is older and in already
                max_id = d["next_max_id"]
            info["checked"] = int(time.time())
            say(aid, "instagram: looked,", len(queue), "new")
        for code in wanted:
            queue.setdefault(code, None)
        for code, media in queue.items():
            if left <= 0:
                break
            if media is None:
                _wait(3, 8)
                pk = instagram.pk_of(code)
                try:
                    media = (ig.get(f"/api/v1/media/{pk}/info/").get("items") or [None])[0] if pk else None
                except Stop as e:
                    if str(e) != "gone":
                        raise
                    media = None
                if not media or not media.get("code"):
                    store.give_up(code, "not on Instagram")
                    continue
            elif came:
                _wait(12, 30)
            if _keep_video(ig, media, by=aid):
                came += 1
                left -= 1
                brought.append(int(time.time()))
                say(code, "instagram: video in")
    except Stop as e:
        error = str(e)
        say(aid, "instagram:", error)
    finally:
        now = kitchen.signin(aid)
        if now.get("jar") and now.get("added") == info.get("added"):     # not forgotten or replaced meanwhile
            now.update(jar=ig.jar(), claim=ig.claim, brought=brought[-20:], error=error, checked=info.get("checked"),
                       wait_until=int(time.time()) + (86400 if error == "busy" else 3 * 3600 if error == "instagram" else 0))
            if came:
                now["brought_at"] = int(time.time())
            kitchen.save_signin(aid, now)
    return came


def run_all(say=print):
    """Every account with a pasted sign-in. A reel from "Add a reel" goes with the sign-in of whoever
    added it, or the owner's."""
    who = kitchen.with_signin()
    if not who or config.paused():
        return 0
    owner = accounts.owner()
    mine = {a: [] for a in who}
    for code in store.wanted(100):
        by = (store.read(config.REELS / code / "post.json", {}) or {}).get("added_by") or owner
        a = by if by in mine else (owner if owner in mine else who[0])
        mine[a].append(code)
    return sum(run(a, mine[a], say) for a in who)

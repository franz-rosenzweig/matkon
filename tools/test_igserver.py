#!/usr/bin/env python3
"""The server's own look at Instagram (igserver.py), against a pretend Instagram on this machine: the
headers it sends, the pace, the hourly limit, stopping at the first refusal, the pause, and that the
pasted cookies never reach the app. Nothing here talks to the real Instagram.

  python3 tools/test_igserver.py          (needs .venv-ig, or MATKON_IG_PY, with curl_cffi)
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILS = []


def ok(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        FAILS.append(what)


STATE = Path(tempfile.mkdtemp(prefix="matkon-ig-test-"))
IG_PORT, APP_PORT, COLL = 8536, 8537, "17800000000000001"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:144.0) Gecko/20100101 Firefox/144.0"
ENV = STATE / "test.env"
ENV.write_text("\n".join([f"MATKON_STATE={STATE}", f"MATKON_SETTINGS={STATE}/settings.json", "MATKON_OWNER=tester",
                          f"MATKON_IG_ORIGIN=http://127.0.0.1:{IG_PORT}", "MATKON_IG_FAST=1", "MATKON_PY=/bin/false",
                          "MATKON_HOSTS=127.0.0.1", f"MATKON_PORT={APP_PORT}", "MATKON_VAULT=", "MATKON_NOTIFY="]) + "\n")
os.environ["MATKON_ENV"] = str(ENV)
sys.path.insert(0, str(ROOT))
from matkon import accounts, config, instagram, kitchen, store  # noqa: E402

VIDEO = STATE / "clip.mp4"
subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x568:rate=24:duration=1",
                "-pix_fmt", "yuv420p", str(VIDEO)], check=True)


# ---- a pretend Instagram ----

def media(code, video=True, coll=True):
    return {"code": code, "pk": instagram.pk_of(code), "media_type": 2 if video else 1, "product_type": "clips",
            "user": {"username": "cook.example", "full_name": "A Cook"}, "caption": {"text": f"recipe {code}"},
            "taken_at": 1700000000, "video_duration": 1.0, "saved_collection_ids": [COLL] if coll else ["999"],
            "video_versions": [{"width": 1440, "url": f"http://127.0.0.1:{IG_PORT}/cdn/{code}-big.mp4"},
                               {"width": 720, "url": f"http://127.0.0.1:{IG_PORT}/cdn/{code}.mp4"}] if video else []}


IG = {"mode": "ok", "log": [], "page1": [], "info": {}}


class FakeIG(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        IG["log"].append({"path": self.path, "headers": dict(self.headers)})
        if self.path.startswith("/cdn/"):
            if "-big" in self.path:
                return self.reply(500, b"wrong size")
            return self.reply(200, VIDEO.read_bytes(), "video/mp4")
        if IG["mode"] == "login":
            self.send_response(302)
            self.send_header("Location", "/accounts/login/?next=/api/v1/feed/saved/posts/")
            self.end_headers()
            return
        if IG["mode"] == "busy":
            return self.reply(429, b'{"message":"Please wait a few minutes before you try again.","status":"fail"}')
        if self.path.startswith("/api/v1/feed/saved/posts/"):
            body = {"items": [{"media": m} for m in IG["page1"]], "more_available": True, "next_max_id": "NEXT"}
            if "max_id=NEXT" in self.path:
                body = {"items": [], "more_available": False}
            return self.reply(200, json.dumps(body).encode(), cookies=True)
        if self.path.startswith("/api/v1/media/"):
            pk = self.path.split("/")[4]
            if pk in IG["info"]:
                return self.reply(200, json.dumps({"items": [IG["info"][pk]]}).encode())
            return self.reply(404, b'{"message":"Media not found or unavailable","status":"fail"}')
        self.reply(404, b"no")

    def reply(self, code, body, ctype="application/json", cookies=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if cookies:
            self.send_header("Set-Cookie", "csrftoken=CSRF2; Domain=.instagram.com; Path=/; Secure")
            self.send_header("Set-Cookie", "csrftoken=CSRF2; Path=/")
            self.send_header("x-ig-set-www-claim", "hmac.CLAIM1")
        self.end_headers()
        self.wfile.write(body)


ig_server = ThreadingHTTPServer(("127.0.0.1", IG_PORT), FakeIG)
threading.Thread(target=ig_server.serve_forever, daemon=True).start()


def look():
    """run.py instagram, the way sync starts it (in IG_PY). How many requests it made."""
    n = len(IG["log"])
    r = subprocess.run([config.IG_PY, "-I", str(ROOT / "run.py"), "instagram"], capture_output=True, text=True, timeout=120)
    if r.returncode:
        print(r.stdout, r.stderr)
    return len(IG["log"]) - n


def info():
    return kitchen.signin("tester")


def edit(**kw):
    kitchen.save_signin("tester", {**info(), **kw})


# ---- setup: an owner with a collection and a pasted sign-in ----
config.STATE.mkdir(parents=True, exist_ok=True)
config.REELS.mkdir(exist_ok=True)
accounts.ensure()
accounts.update("tester", password="ig-test-password")
kitchen.set_collection("tester", COLL, "Recipes")
st = config.settings(); st.update(per_hour=2, scan_pages=2, check_hours=6); config.save_settings(st)

try:
    kitchen.set_signin("tester", instagram.parse_cookies("csrftoken=C; ds_user_id=1"), UA, "en-US,en")
    ok(False, "a sign-in without sessionid is refused")
except ValueError:
    ok(True, "a sign-in without sessionid is refused")
kitchen.set_signin("tester", instagram.parse_cookies("Cookie: csrftoken=CSRF1; sessionid=1%3ASECRETSESSION; ds_user_id=1; rur=\"CCO\\0541\""), UA, "en-US,en")
ok(oct(os.stat(config.STATE / "users" / "tester" / "sign-in.json").st_mode & 0o777) == "0o600", "the sign-in file is readable only by its owner")

# a reel Matkon already has, below three new saves (one not in the collection, one a photo)
store.keep_post(instagram.post(media("OLDREEL01")), by="tester")
(config.REELS / "OLDREEL01" / "video.mp4").write_bytes(VIDEO.read_bytes())
IG["page1"] = [media("NEWREEL01"), media("OTHERCOLL1", coll=False), media("NEWPHOTO1", video=False), media("NEWREEL02"),
               media("NEWREEL03"), media("OLDREEL01")]

# ---- 1. the first look ----
n = look()
api = [x for x in IG["log"] if x["path"].startswith("/api/")]
first = api[0]["headers"] if api else {}
ok(n > 0 and api[0]["path"] == "/api/v1/feed/saved/posts/", "it reads the newest saves")
ok(not any("max_id" in x["path"] for x in IG["log"]), "it stops at the first reel Matkon has (no second page)")
ok(first.get("User-Agent") == UA, "it sends the User-Agent of the browser the sign-in came from")
ok(first.get("Accept-Language") == "en-US,en;q=0.5", "and that browser's languages, the way Firefox sends them")
ok(first.get("X-IG-App-ID") == "936619743392459" and first.get("X-CSRFToken") == "CSRF1" and first.get("X-Requested-With") == "XMLHttpRequest",
   "the website's own headers")
ok(first.get("Sec-Fetch-Mode") == "cors" and first.get("Sec-Fetch-Site") == "same-origin", "the fetch headers of a page's own request")
ok("sessionid=1%3ASECRETSESSION" in first.get("Cookie", ""), "the pasted sign-in goes with it")
ok(store.has("NEWREEL01") and store.has("NEWREEL02") and not store.has("NEWREEL03"), "two videos come in (Reels an hour: 2), the third waits")
ok(not (config.REELS / "OTHERCOLL1").exists(), "a save from another collection stays out")
ok((store.read(config.REELS / "NEWPHOTO1" / "status.json", {}) or {}).get("error", "").startswith("video: not a video"), "a photo post is noted and skipped")
ok(not any("-big" in x["path"] for x in IG["log"]), "it takes the video up to 1080 wide")
i = info()
ok(i.get("checked") and not i.get("error") and len(i.get("brought") or []) == 2, "the look is recorded: checked, no error, two brought")
ok(i["jar"].get("csrftoken") == "CSRF2" and i.get("claim") == "hmac.CLAIM1", "cookies and the claim Instagram changes are kept")
ok((store.read(config.REELS / "NEWREEL01" / "post.json", {}) or {}).get("added_by") == "tester", "the reels are the account's")

# ---- 2. not due, nothing wanted, the hour used up: no requests at all ----
ok(look() == 0, "a run that isn't due asks Instagram nothing")

# ---- 3. an hour later: "Add a reel" and a gone one come through media info ----
IG["info"][instagram.pk_of("ADDEDREEL1")] = media("ADDEDREEL1")
store.queue("https://www.instagram.com/reel/ADDEDREEL1/?igsh=x", "tester")
store.queue("https://www.instagram.com/reel/GONEREEL01/", "tester")
edit(brought=[])
look()
ok(store.has("ADDEDREEL1"), "a reel from Add a reel comes in (media info by its number)")
last = [x for x in IG["log"] if "/media/" in x["path"]]
ok(last and last[0]["headers"].get("X-CSRFToken") == "CSRF2", "the next request uses Instagram's new csrftoken")
ok((store.read(config.REELS / "GONEREEL01" / "status.json", {}) or {}).get("error") == "video: not on Instagram", "a reel Instagram doesn't have is given up on")
ok("GONEREEL01" not in store.wanted(), "and isn't asked for again")

# ---- 4. signed out: stop, and wait for a new sign-in ----
IG["mode"] = "login"
edit(checked=0, brought=[])
look()
ok(info().get("error") == "signed-out", "a sign-in page stops it: signed-out")
ok(look() == 0, "after that it asks nothing until there's a new sign-in")
kitchen.set_signin("tester", instagram.parse_cookies("csrftoken=CSRF9; sessionid=NEWSESSION; ds_user_id=1"), UA, "en-US,en")
ok(not info().get("error"), "a new sign-in starts over")

# ---- 5. busy: a day's rest ----
IG["mode"] = "busy"
look()
i = info()
ok(i.get("error") == "busy" and i.get("wait_until", 0) > time.time() + 23 * 3600, "\"slow down\" stops it for a day")
ok(look() == 0, "and it waits it out")

# ---- 6. paused ----
IG["mode"] = "ok"
edit(checked=0, wait_until=0, error=None, brought=[])
config.PAUSED.write_text("test\n")
ok(look() == 0, "paused: nothing")
config.PAUSED.unlink()

# ---- 7. the app: the sign-in's status, never its cookies ----
app = subprocess.Popen([sys.executable, "-I", str(ROOT / "run.py"), "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    M = f"http://127.0.0.1:{APP_PORT}"
    for _ in range(50):
        try:
            urllib.request.urlopen(M + "/", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

    def call(path, body=None, headers=None):
        req = urllib.request.Request(M + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", "X-Matkon": "1", **(headers or {})})
        try:
            with opener.open(req, timeout=10) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
    call("/api/signin", {"username": "tester", "password": "ig-test-password"})
    code, body = call("/api/settings", {"op": "signin", "cookies": "sessionid=PASTEDSECRET; csrftoken=PC; ds_user_id=1",
                                        "ua": UA, "langs": "en-US,en"})
    ok(code == 200, "Settings takes a pasted sign-in")
    _, s = call("/api/settings")
    _, me = call("/api/me")
    ok('"signin": {"added"' in s.replace(" ", "").replace('"signin":{"added"', '"signin": {"added"') or '"added"' in s, "Settings shows when it was added")
    ok("PASTEDSECRET" not in s + me and "jar" not in s + me, "the cookies never go to the app")
    code, body = call("/api/settings", {"op": "signin", "cookies": "hello"})
    ok(code == 400, "a paste that isn't a sign-in is refused")
    call("/api/settings", {"op": "collection", "value": "https://www.instagram.com/someone/saved/my-recipes/17900000000000009/"})
    i = kitchen.of("tester")
    ok(i["collection_id"] == "17900000000000009" and i["collection_name"] == "My recipes", "Collection takes a collection's address")
    code, _ = call("/api/settings", {"op": "collection", "value": "https://www.instagram.com/reel/ABCDE12345/"})
    ok(code == 400, "and refuses anything else")
    key = kitchen.new_key("tester")
    _, h = call("/api/ext/hello", {"version": "test"}, {"X-Matkon-Key": key})
    ok(json.loads(h).get("paused") is True, "a connected browser leaves Instagram alone while the server looks")
    call("/api/settings", {"op": "signin-forget"})
    ok(not (config.STATE / "users" / "tester" / "sign-in.json").exists(), "Forget deletes the sign-in")
    _, h = call("/api/ext/hello", {"version": "test"}, {"X-Matkon-Key": key})
    ok(json.loads(h).get("paused") is False, "and the browser takes over again")
finally:
    app.terminate()

ig_server.shutdown()
import shutil  # noqa: E402
shutil.rmtree(STATE, ignore_errors=True)
print(f"{len(FAILS)} FAILED" if FAILS else "all good")
sys.exit(1 if FAILS else 0)

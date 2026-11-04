"""Matkon's app: the pages in app/, the recipes and each account's memory as JSON, and the reels.

Listens where MATKON_HOSTS says (localhost by default; add a private address, like a tailnet one, to
reach it from a phone, or put a tunnel in front of it) on MATKON_PORT (8510).

Everyone signs in (accounts.py); only the app's own files and the sign-in answer without it. Every
change is a POST with JSON and an X-Matkon header, which a page on another site can't send. Videos
are served with byte ranges, which Safari needs to play them.

MATKON_DEMO_ACCOUNT=<id> skips signing in and makes every visitor that account: for tools/demo.py.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import urllib.parse

from . import accounts, config, kitchen, mail, memory, vault

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
HOSTS = [h.strip() for h in os.environ.get("MATKON_HOSTS", "127.0.0.1").split(",") if h.strip()]
PORT = int(os.environ.get("MATKON_PORT", "8510"))
DEMO = os.environ.get("MATKON_DEMO_ACCOUNT")
CODE = re.compile(r"^[\w-]{5,40}$")
MEDIA = {"video.mp4": "video/mp4", "photo.jpg": "image/jpeg", "cover.jpg": "image/jpeg"}
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".svg": "image/svg+xml", ".png": "image/png", ".webmanifest": "application/manifest+json", ".json": "application/json"}
KITCHEN_KEYS = {"notes_dir": str, "photos_dir": str, "note_tag": str, "app_url": str, "scan_pages": int,
                "full_every_hours": int, "per_run": int}


def _read(p):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _photo(code, r):
    f = config.REELS / code
    name = (r or {}).get("photo") or ("photo.jpg" if (f / "photo.jpg").exists() else "cover.jpg")
    if not (f / name).exists():
        return None
    return f"m/{code}/{name}?v={int((f / name).stat().st_mtime)}"


def recipe_full(code, lang=None):
    """The recipe, in `lang` when there's a version in it (recipe.<lang>.json), else as it was written."""
    f = config.REELS / code
    r, p = _read(f / "recipe.json"), _read(f / "post.json")
    if not r or not p:
        return None
    orig = r.get("lang", "en")
    langs = [orig] + [x for x in ("en", "he") if x != orig and (f / f"recipe.{x}.json").exists()]
    if lang and lang != orig and lang in langs:
        r = {**r, **(_read(f / f"recipe.{lang}.json") or {})}
    return {**r, "code": code, "langs": langs, "original_lang": orig, "user": p.get("user", ""), "name": p.get("name", ""), "reel": p.get("url"),
            "found": p.get("found", 0), "added_by": p.get("added_by") or accounts.owner(), "photo": _photo(code, r),
            "video": f"m/{code}/video.mp4" if (f / "video.mp4").exists() else None}


def index():
    out, waiting = [], 0
    for f in config.REELS.iterdir() if config.REELS.exists() else []:
        if not CODE.match(f.name):
            continue
        r = recipe_full(f.name)
        if not r:
            waiting += (f / "post.json").exists()
            continue
        en = _read(f / "recipe.en.json") if r.get("lang") != "en" else None
        out.append({k: r.get(k) for k in ("code", "title", "summary", "kind", "lang", "user", "tags", "cuisine", "complete",
                                          "is_recipe", "found", "photo", "time", "servings", "main_ingredients", "added_by")}
                   | {"items": [i["item"] for g in r.get("ingredient_groups", []) for i in g["items"]]}
                   | ({"title_en": en.get("title"), "items_en": [i["item"] for g in en.get("ingredient_groups", []) for i in g["items"]]} if en else {}))
    out.sort(key=lambda x: -(x.get("found") or 0))
    return {"recipes": out, "waiting": waiting}


def job(args, name):
    """A run.py command in the background (its own session, so it outlives this request)."""
    logs = config.STATE / "logs"
    logs.mkdir(exist_ok=True)
    with open(logs / f"{name}.log", "a") as out:
        subprocess.Popen([sys.executable, "-I", str(ROOT / "run.py")] + args, stdout=out, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True, cwd=str(ROOT))


def instagram_status(aid):
    i = kitchen.of(aid)
    return {"connected": bool(i["cookies"]), "shared": i["shared"], "signed_out": i["signed_out"],
            "collection_id": i["collection_id"], "collection_name": i["collection_name"],
            "scan": _read(kitchen.collections_file(aid))}


class Handler(BaseHTTPRequestHandler):
    server_version = "Matkon"
    protocol_version = "HTTP/1.1"          # keep-alive, which Safari's video player expects

    def log_message(self, fmt, *a):
        pass

    # ---- sending ----

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", cache="private, no-cache", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Robots-Tag", "noindex")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data, code=200, extra=None):
        self._send(code, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", "private, no-store", extra)

    def _error(self, code, msg):
        self._json({"error": msg}, code)

    def _file(self, path, ctype, cache):
        size = path.stat().st_size
        rng = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
        partial = bool(rng and (rng.group(1) or rng.group(2)))
        start, end = 0, size - 1
        if partial:
            if rng.group(1):
                start = int(rng.group(1))
                end = min(int(rng.group(2)), size - 1) if rng.group(2) else size - 1
            else:
                start = max(0, size - int(rng.group(2)))
            if start > end or start >= size:
                return self._send(416, extra={"Content-Range": f"bytes */{size}"})
        length = end - start + 1
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", cache)
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as fh:
            fh.seek(start)
            left = length
            try:
                while left > 0:
                    chunk = fh.read(min(256 * 1024, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    # ---- who's asking ----

    def addr(self):
        return (self.headers.get("Cf-Connecting-Ip") or (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
                or self.client_address[0])

    def https(self):
        return self.headers.get("X-Forwarded-Proto") == "https" or "https" in (self.headers.get("Cf-Visitor") or "")

    def account(self):
        if DEMO:
            return DEMO
        c = SimpleCookie()
        try:
            c.load(self.headers.get("Cookie") or "")
        except Exception:  # noqa: BLE001 - a broken cookie header is no cookie
            return None
        m = c.get(accounts.COOKIE)
        return accounts.who(m.value) if m else None

    def set_cookie(self, value, age):
        secure = "; Secure" if self.https() else ""
        return f"{accounts.COOKIE}={value}; Path=/; Max-Age={age}; HttpOnly; SameSite=Lax{secure}"

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 2_000_000:
            raise ValueError("too big")
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            raise ValueError("not JSON")

    # ---- GET ----

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if not path.startswith(("/api/", "/m/")):
            name = "index.html" if path in ("/", "") else path.lstrip("/")
            f = (APP / name).resolve()
            if f.is_file() and APP in f.parents and f.suffix in TYPES:
                return self._file(f, TYPES[f.suffix], "private, no-cache")
            return self._send(404, b"not here")
        aid = self.account()
        if not aid:
            return self._error(401, "signed out")
        if path == "/api/me":
            return self._json({"account": accounts.get(aid) or {"id": aid, "name": aid, "admin": False},
                               "owner": accounts.owner(), "memory": memory.view(aid),
                               "names": {x["id"]: x["name"] for x in accounts.all_accounts()},
                               "instagram": instagram_status(aid)})
        if path == "/api/recipes":
            return self._json(index())
        if path == "/api/suggest":
            return self._json({"suggest": memory.suggest(aid, index()["recipes"])})
        if path == "/api/history":
            m = memory.view(aid)
            return self._json({"cooked": sorted(m["cooked"], key=lambda e: -e["at"]), "viewed": m["viewed"], "runs": memory.runs()})
        if path == "/api/settings":
            a = accounts.get(aid) or {}
            out = {"account": a, "instagram": instagram_status(aid), "settings": memory.view(aid)["settings"]}
            if a.get("admin"):
                st = config.settings()
                out["kitchen"] = {k: st.get(k) for k in KITCHEN_KEYS}
                out["accounts"] = accounts.all_accounts()
                out["initial_password"] = (config.STATE / "initial-password.txt").exists()
                out["invites"] = accounts.invites()
                out["mail"] = mail.available()
            return self._json(out)
        m = re.match(r"^/api/r/([\w-]+)$", path)
        if m:
            settings = memory.view(aid)["settings"]
            want = (urllib.parse.parse_qs(self.path.split("?", 1)[1]).get("lang", [None])[0] if "?" in self.path else None)
            r = recipe_full(m.group(1), want or ("en" if settings.get("english") else None)) if CODE.match(m.group(1)) else None
            if not r:
                return self._error(404, "not here")
            if not settings.get("nutrition", True):
                r["nutrition"] = {}                       # this account doesn't see the numbers
            return self._json(r)
        m = re.match(r"^/m/([\w-]+)/([\w.]+)$", path)
        if m and CODE.match(m.group(1)) and m.group(2) in MEDIA:
            f = config.REELS / m.group(1) / m.group(2)
            if f.exists():
                return self._file(f, MEDIA[m.group(2)], "private, max-age=604800")
        return self._error(404, "not here")

    # ---- POST ----

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if self.headers.get("X-Matkon") != "1":
            return self._error(403, "not from Matkon")
        try:
            b = self.body()
        except ValueError as e:
            return self._error(400, str(e))
        if path == "/api/signin":
            who = self.addr()
            if accounts.held(who):
                return self._error(429, "Too many tries. Wait a little and try again.")
            aid = accounts.check(b.get("username"), b.get("password"))
            if not aid:
                accounts.failed(who)
                time.sleep(0.5)
                return self._error(401, "That username and password don't match.")
            accounts.passed(who)
            return self._json({"ok": True}, extra={"Set-Cookie": self.set_cookie(accounts.cookie(aid), accounts.YEAR)})
        if path == "/api/signout":
            return self._json({"ok": True}, extra={"Set-Cookie": self.set_cookie("", 0)})
        if path in ("/api/join", "/api/forgot", "/api/reset"):
            return self.codes(path, b)
        aid = self.account()
        if not aid:
            return self._error(401, "signed out")
        try:
            if path == "/api/me":
                code = memory.apply(aid, b.get("op"), b)
                if code and aid == accounts.owner():
                    threading.Thread(target=self._remember, args=(code,), daemon=True).start()
                return self._json({"memory": memory.view(aid)})
            if path == "/api/settings":
                op = b.get("op")
                out = self.settings_op(aid, op, b)
                if op == "password":                      # the old cookie stopped working: a new one
                    return self._json({"ok": True}, extra={"Set-Cookie": self.set_cookie(accounts.cookie(aid), accounts.YEAR)})
                return self._json(out or {"ok": True})
        except ValueError as e:
            return self._error(400, str(e))
        return self._error(404, "not here")

    def codes(self, path, b):
        """Joining with an invite, and setting a new password with an emailed code. Signed out."""
        who = self.addr()
        if accounts.held(who):
            return self._error(429, "Too many tries. Wait a little and try again.")
        email = str(b.get("email") or "").strip().lower()
        try:
            if path == "/api/forgot":
                if accounts.by_email(email) and not accounts.recent_code("reset", email):
                    code = accounts.make_code("reset", email)
                    mail.send(email, "Your Matkon code", f"Your code for a new Matkon password is {code}.\n\n"
                              "It works for 15 minutes. If you didn't ask for it, you can ignore this email.\n")
                return self._json({"ok": True})             # the same answer whether or not there's an account
            if path == "/api/join":
                rec = accounts.use_code("invite", email, b.get("code"), keep=True)
                accounts.add(b.get("username"), b.get("name") or rec.get("name"), b.get("password"), email=email)
                accounts.drop_code("invite", email)
                aid = str(b.get("username")).strip().lower()
            else:
                accounts.use_code("reset", email, b.get("code"), keep=True)
                a = accounts.by_email(email)
                if not a:
                    raise ValueError("That code doesn't match.")
                accounts.update(a["id"], password=b.get("password"))
                accounts.drop_code("reset", email)
                aid = a["id"]
        except ValueError as e:
            if "code" in str(e):
                accounts.failed(who)
            return self._error(400, str(e))
        accounts.passed(who)
        return self._json({"ok": True}, extra={"Set-Cookie": self.set_cookie(accounts.cookie(aid), accounts.YEAR)})

    def invite(self, aid, email, name):
        email = accounts.clean_email(email)
        if accounts.by_email(email):
            raise ValueError("That email already has an account.")
        code = accounts.make_code("invite", email, name=(name or "").strip()[:60], by=aid)
        me = (accounts.get(aid) or {}).get("name") or aid
        url = (config.settings().get("app_url") or "").rstrip("/")
        link = f"{url}/#/join/{urllib.parse.quote(email)}/{code}"
        hello = f"Hi {name.strip()},\n\n" if (name or "").strip() else ""
        sent = mail.send(email, f"{me} invited you to Matkon", f"""{hello}{me} invited you to Matkon, a kitchen of recipes from saved cooking reels.

Your code is: {code}

To join, open this link and pick a username and a password:
{link}

Or go to {url}, tap "I have a code", and enter this email address and the code.

The code works for 7 days.
""")
        return {"ok": True, "sent": sent, **({} if sent else {"code": code, "link": link})}

    @staticmethod
    def _remember(code):
        try:
            vault.remember(code)
        except Exception as e:  # noqa: BLE001 - the note is a copy; the app's memory is already saved
            print("vault note for", code, "not updated:", e, flush=True)

    def settings_op(self, aid, op, b):
        admin = (accounts.get(aid) or {}).get("admin")
        if op == "name":
            accounts.update(aid, name=b.get("name"))
        elif op == "email-code":
            email = accounts.clean_email(b.get("email"))
            other = accounts.by_email(email)
            if other and other["id"] != aid:
                raise ValueError("That email already has an account.")
            if not mail.available():                      # no way to check it: just take it
                accounts.set_email(aid, email)
                return {"ok": True, "set": True}
            if accounts.recent_code("email", email):
                raise ValueError("A code just went there. Wait a minute.")
            code = accounts.make_code("email", email, aid=aid)
            if not mail.send(email, "Your Matkon code", f"Your code to use this email for Matkon is {code}.\n\nIt works for 15 minutes.\n"):
                raise ValueError("The email didn't go out. Try again in a little while.")
            return {"ok": True, "sent": True}
        elif op == "email-set":
            rec = accounts.use_code("email", b.get("email"), b.get("code"), keep=True)
            if rec.get("aid") != aid:
                raise ValueError("That code doesn't match.")
            accounts.set_email(aid, b.get("email"))
            accounts.drop_code("email", b.get("email"))
        elif op == "invite" and admin:
            return self.invite(aid, b.get("email"), b.get("name"))
        elif op == "invite-cancel" and admin:
            accounts.drop_code("invite", str(b.get("email") or ""))
        elif op == "password":
            if not accounts.check(aid, b.get("old")):
                raise ValueError("The current password isn't right.")
            accounts.update(aid, password=b.get("new"))
        elif op in ("nutrition", "english"):
            memory.apply(aid, "setting", {"key": op, "value": b.get("value")})
        elif op == "instagram-cookies":
            kitchen.set_cookies(aid, b.get("text") or "")
        elif op == "instagram-disconnect":
            kitchen.disconnect(aid)
        elif op == "instagram-scan":
            if not kitchen.of(aid)["cookies"]:
                raise ValueError("Connect Instagram first.")
            kitchen.collections_file(aid).write_text(json.dumps({"running": int(time.time())}))
            job(["collections", "--account", aid, "--out", str(kitchen.collections_file(aid))], f"collections-{aid}")
        elif op == "instagram-collection":
            if not re.match(r"^\d{5,30}$", str(b.get("id") or "")):
                raise ValueError("Pick a collection.")
            kitchen.set_collection(aid, b["id"], b.get("name") or "")
        elif op == "add-reel":
            url = str(b.get("url") or "").strip()
            if not re.search(r"instagram\.com/(?:[\w.]+/)?(?:reels?|p|tv)/[\w-]{5,}", url):
                raise ValueError("That isn't an Instagram reel link.")
            job(["add", url, "--by", aid], "add")
        elif op == "sync" and admin:
            job(["sync"], "sync-now")
        elif op == "kitchen" and admin:
            st = config.settings()
            for k, typ in KITCHEN_KEYS.items():
                if k not in b:
                    continue
                if typ is int:
                    try:
                        v = int(b[k])
                    except (TypeError, ValueError):
                        raise ValueError(f"{k} should be a number.")
                    if not 0 <= v <= 10000:
                        raise ValueError(f"{k} is out of range.")
                else:
                    v = str(b[k] or "").strip()[:200]
                st[k] = v
            config.save_settings(st)
        elif op == "account-add" and admin:
            accounts.add(b.get("id"), b.get("name"), b.get("password"))
        elif op == "account-remove" and admin:
            if b.get("id") == aid:
                raise ValueError("You can't remove your own account.")
            accounts.remove(b.get("id"))
        elif op == "account-password" and admin:
            accounts.update(b.get("id"), password=b.get("password"))
        else:
            raise ValueError("no such change")


def main():
    if not DEMO:
        accounts.ensure()
    servers = []
    for h in HOSTS:
        try:
            servers.append(ThreadingHTTPServer((h, PORT), Handler))
        except OSError as e:
            print(f"can't listen on {h}:{PORT}: {e}", flush=True)
    if not servers:
        return 1
    for s in servers[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    print("Matkon on " + ", ".join(f"http://{h}:{PORT}" for h in HOSTS), flush=True)
    servers[0].serve_forever()

"""Matkon's app: the pages in app/, the recipes as JSON, and each reel's video and photo.

Listens where MATKON_HOSTS says (localhost by default; add a private address, like a tailnet one, to
reach it from a phone) on MATKON_PORT (8510). Read-only: nothing
here changes a recipe. Videos are served with byte ranges, which Safari needs to play them.
"""
import json
import os
import re
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config

APP = Path(__file__).resolve().parent.parent / "app"
HOSTS = [h.strip() for h in os.environ.get("MATKON_HOSTS", "127.0.0.1").split(",") if h.strip()]
PORT = int(os.environ.get("MATKON_PORT", "8510"))
CODE = re.compile(r"^[\w-]{5,40}$")
MEDIA = {"video.mp4": "video/mp4", "photo.jpg": "image/jpeg", "cover.jpg": "image/jpeg"}
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".svg": "image/svg+xml", ".png": "image/png", ".webmanifest": "application/manifest+json", ".json": "application/json"}


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


def recipe_full(code):
    f = config.REELS / code
    r, p = _read(f / "recipe.json"), _read(f / "post.json")
    if not r or not p:
        return None
    return {**r, "code": code, "user": p.get("user", ""), "name": p.get("name", ""), "reel": p.get("url"),
            "found": p.get("found", 0), "photo": _photo(code, r),
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
        out.append({k: r.get(k) for k in ("code", "title", "summary", "kind", "lang", "user", "tags", "cuisine", "complete",
                                          "is_recipe", "found", "photo", "time", "servings", "main_ingredients")}
                   | {"items": [i["item"] for g in r.get("ingredient_groups", []) for i in g["items"]]})
    out.sort(key=lambda x: -(x.get("found") or 0))
    return {"recipes": out, "waiting": waiting, "signed_out": (config.STATE / "signed-out").exists()}


class Handler(BaseHTTPRequestHandler):
    server_version = "Matkon"
    protocol_version = "HTTP/1.1"          # keep-alive, which Safari's video player expects

    def log_message(self, fmt, *a):
        pass

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", cache="private, no-cache", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Robots-Tag", "noindex")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data):
        self._send(200, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _file(self, path, ctype, cache):
        size = path.stat().st_size
        rng = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
        start, end = 0, size - 1
        if rng and (rng.group(1) or rng.group(2)):
            if rng.group(1):
                start = int(rng.group(1))
                end = min(int(rng.group(2)), size - 1) if rng.group(2) else size - 1
            else:
                start = max(0, size - int(rng.group(2)))
            if start > end or start >= size:
                return self._send(416, extra={"Content-Range": f"bytes */{size}"})
        length = end - start + 1
        self.send_response(206 if rng and (rng.group(1) or rng.group(2)) else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", cache)
        if rng and (rng.group(1) or rng.group(2)):
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

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/recipes":
            return self._json(index())
        m = re.match(r"^/api/r/([\w-]+)$", path)
        if m:
            r = recipe_full(m.group(1)) if CODE.match(m.group(1)) else None
            return self._json(r) if r else self._send(404, b"not here")
        m = re.match(r"^/m/([\w-]+)/([\w.]+)$", path)
        if m and CODE.match(m.group(1)) and m.group(2) in MEDIA:
            f = config.REELS / m.group(1) / m.group(2)
            if f.exists():
                return self._file(f, MEDIA[m.group(2)], "private, max-age=604800")
            return self._send(404, b"not here")
        name = "index.html" if path in ("/", "") else path.lstrip("/")
        f = (APP / name).resolve()
        if f.is_file() and APP in f.parents and f.suffix in TYPES:
            return self._file(f, TYPES[f.suffix], "private, no-cache")
        return self._send(404, b"not here")


def main():
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

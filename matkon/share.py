"""A recipe shared by its link: <app_url>/s/<token>, a page anyone can open without signing in.

The page is the recipe and nothing of anyone's: the photo, the title, the creator and a link to the
post, the times, the ingredients, the steps, the tips and what's not in the reel. No video, no notes,
no ratings, no account names. It's made on the server, all in one file (inline CSS, the photo at
/s/<token>/photo), so it prints and opens anywhere. Search engines are asked to leave it alone.

STATE/shares.json: {token: {"code", "by", "at"}}, one token for a recipe however often it's shared,
for the whole kitchen. Unsharing takes the token away, and the link stops working.
"""
import html
import re
import secrets
import threading
import time

from . import config, sources
from .store import read as _read, write as _write
from .vault import HEAD

TOKEN = re.compile(r"^[\w-]{16,64}$")
_lock = threading.Lock()


def _path():
    return config.STATE / "shares.json"


def _all():
    d = _read(_path(), {})
    return d if isinstance(d, dict) else {}


def url(token):
    return (config.settings().get("app_url") or "").rstrip("/") + "/s/" + token


def token_of(code):
    return next((t for t, s in _all().items() if s.get("code") == code), None)


def url_of(code):
    t = token_of(code)
    return url(t) if t else None


def code_of(token):
    s = _all().get(token) if TOKEN.match(token or "") else None
    return s.get("code") if s else None


def share(code, by):
    """The recipe's token: the one it has, or a new one."""
    with _lock:
        d = _all()
        t = next((t for t, s in d.items() if s.get("code") == code), None)
        if not t:
            t = secrets.token_urlsafe(16)
            d[t] = {"code": code, "by": by, "at": int(time.time())}
            _write(_path(), d)
    return t


def unshare(code):
    with _lock:
        d = _all()
        left = {t: s for t, s in d.items() if s.get("code") != code}
        if len(left) != len(d):
            _write(_path(), left)


# ---- the page ------------------------------------------------------------------------------------

CSS = """
:root{--bg:#F5F2EC;--card:#FFFFFF;--ink:#1E1C19;--muted:#6E685F;--line:#E5DFD4;--accent:#B8441A;--accent-soft:#F6E3D9;
--font:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,"Noto Sans","Noto Sans Hebrew","Helvetica Neue",Arial,sans-serif;
--display:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",Roboto,"Noto Sans Hebrew","Helvetica Neue",Arial,sans-serif;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#141312;--card:#1E1C1A;--ink:#EDE9E3;--muted:#A49D93;--line:#2F2C29;--accent:#F0804A;
--accent-soft:#3A2419;color-scheme:dark}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 var(--font);-webkit-font-smoothing:antialiased}
a{color:var(--accent);font-weight:600;text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1040px;margin:0 auto;padding:16px 16px 56px}
.langs{display:flex;justify-content:flex-end;margin:0 0 10px;font-size:15px}
.langs a{display:inline-flex;align-items:center;min-height:36px;padding:0 14px;border-radius:999px;background:var(--card);border:1px solid var(--line)}
.top{display:grid;gap:18px}
.pic{margin:0;border-radius:14px;overflow:hidden;background:#000}
.pic img{display:block;width:100%;aspect-ratio:4/3;max-height:52svh;object-fit:cover}
h1{margin:0 0 6px;font:700 30px/1.15 var(--display);letter-spacing:-.02em}
[dir=rtl] h1{letter-spacing:0}
.sum{margin:0 0 10px;color:var(--muted)}
.by{margin:0;font-size:15px}
.facts{display:flex;flex-wrap:wrap;gap:6px 18px;margin:12px 0 0;padding:0;list-style:none;font-size:15px;color:var(--muted)}
.facts b{color:var(--ink);font-weight:600}
.two{display:grid;gap:0;align-items:start}
.sec{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:6px 18px 14px;margin-top:16px;break-inside:avoid-page}
.sec h2{font:700 19px/1.3 var(--display);margin:14px 0 6px}
.sec h3{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:16px 0 2px;font-weight:700}
[dir=rtl] .sec h3{text-transform:none;letter-spacing:0;font-size:15px}
.ings,.steps{list-style:none;margin:0;padding:0}
.ings li{padding:9px 0;border-bottom:1px solid var(--line)}
.ings li:last-child,.steps li:last-child{border-bottom:0}
.ings .nt{color:var(--muted)}
.steps li{display:flex;gap:14px;padding:12px 0;border-bottom:1px solid var(--line)}
.steps .n{flex:none;width:30px;height:30px;border-radius:50%;background:var(--accent-soft);color:var(--accent);font-weight:700;
display:grid;place-items:center;font-size:15px;margin-top:1px}
.steps p{margin:2px 0 0}
.list{margin:4px 0 0;padding-inline-start:22px}
.list li{margin:6px 0}
.miss{background:transparent;border-style:dashed}
.miss .list{color:var(--muted)}
@media (min-width:760px){
.top{grid-template-columns:minmax(240px,38%) minmax(0,1fr);gap:28px;align-items:center}
.pic img{aspect-ratio:4/5;max-height:none}
h1{font-size:36px}
.two{grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:16px}
}
@media print{
:root{--bg:#fff;--card:#fff;--ink:#000;--muted:#444;--line:#ccc;--accent:#000;--accent-soft:#eee;color-scheme:light}
body{font-size:12pt}
.wrap{max-width:none;padding:0}
.langs{display:none}
.top{grid-template-columns:5cm minmax(0,1fr);gap:.8cm;align-items:start}
.pic{border-radius:6px}
.pic img{aspect-ratio:4/5;max-height:none}
h1{font-size:22pt}
.two{grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:.6cm}
.sec{border:0;padding:0;margin-top:.5cm}
.ings li,.steps li{break-inside:avoid}
a{color:inherit;font-weight:inherit}
.by a::after{content:" (" attr(href) ")";font-size:9pt;color:var(--muted);word-break:break-all}
}
"""


def _e(s):
    return html.escape(str(s or ""), quote=True)


def _doc(title, body, lang="en", rtl=False, head=""):
    return (f'<!doctype html>\n<html lang="{lang}" dir="{"rtl" if rtl else "ltr"}">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<meta name="robots" content="noindex, nofollow">\n<meta name="color-scheme" content="light dark">\n'
            f"<title>{_e(title)}</title>\n{head}<style>{CSS}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n")


def page(r, token, post):
    """The shared page for a recipe as recipe_full() gives it (in the language asked for, edits laid over),
    and its post.json (for who made it: @creator for a reel, the site for a page, nobody for photos)."""
    he = r.get("lang") == "he"
    h = HEAD["he" if he else "en"]
    links = []
    for x in r.get("langs") or []:
        if x != r.get("lang"):
            links.append(f'<a href="?lang={x}" lang="{x}" dir="{"rtl" if x == "he" else "ltr"}">'
                         f'{"English" if x == "en" else "עברית"}</a>')
    out = ['<main class="wrap">']
    if links:
        out.append('<nav class="langs">' + " ".join(links) + "</nav>")
    out.append('<article>\n<div class="top">')
    if r.get("photo"):
        out.append(f'<figure class="pic"><img src="{_e(token)}/photo" alt=""></figure>')
    head = [f"<h1>{_e(r.get('title'))}</h1>"]
    if r.get("summary"):
        head.append(f'<p class="sum">{_e(r["summary"])}</p>')
    who = sources.author(post)
    if who:
        link = f'<a href="{_e(post["url"])}" rel="noopener noreferrer">{_e(who)}</a>' if post.get("url") else _e(who)
        on = " " + _e(h["on"]) if (post.get("source") or "reel") == "reel" else ""
        head.append(f'<p class="by"><bdi>{link}</bdi>{on}</p>')
    facts = []
    servings = (r.get("servings") or "").strip()
    if servings:
        plain = re.match(r"^\d+([–-]\d+)?( |$)(as\b|people|servings?\b|$)", servings)
        facts.append((h["serves"] if plain else h["makes"], servings))
    for k in ("prep", "cook", "total"):
        if (r.get("time") or {}).get(k):
            facts.append((h[k], r["time"][k]))
    if r.get("oven"):
        facts.append((h["oven"], r["oven"]))
    if facts:
        head.append('<ul class="facts">' + "".join(f"<li>{_e(k)} <b>{_e(v)}</b></li>" for k, v in facts) + "</ul>")
    out.append('<header class="head">' + "\n".join(head) + "</header>\n</div>")
    out.append('<div class="two">')
    if r.get("ingredient_groups"):
        ing = [f'<section class="sec"><h2>{_e(h["ing"])}</h2>']
        for g in r["ingredient_groups"]:
            if g.get("name"):
                ing.append(f"<h3>{_e(g['name'])}</h3>")
            ing.append('<ul class="ings">')
            for i in g.get("items") or []:
                amt = f"<b>{_e(i['amount'])}</b> " if i.get("amount") else ""
                note = f'<span class="nt">, {_e(i["note"])}</span>' if i.get("note") else ""
                ing.append(f"<li>{amt}{_e(i.get('item'))}{note}</li>")
            ing.append("</ul>")
        out.append("".join(ing) + "</section>")
    if r.get("steps"):
        out.append(f'<section class="sec"><h2>{_e(h["dir"])}</h2><ol class="steps">' +
                   "".join(f'<li><span class="n">{n}</span><p>{_e(s.get("text"))}</p></li>' for n, s in enumerate(r["steps"], 1)) +
                   "</ol></section>")
    out.append("</div>")
    if r.get("tips"):
        out.append(f'<section class="sec"><h2>{_e(h["tips"])}</h2><ul class="list">' +
                   "".join(f"<li>{_e(t)}</li>" for t in r["tips"]) + "</ul></section>")
    if r.get("missing"):
        out.append(f'<section class="sec miss"><h2>{_e(sources.missing_label(post, r.get("lang")))}</h2><ul class="list">' +
                   "".join(f"<li>{_e(t)}</li>" for t in r["missing"]) + "</ul></section>")
    out.append("</article>\n</main>")
    base = (config.settings().get("app_url") or "").rstrip("/")
    og = (f'<meta property="og:type" content="article">\n<meta property="og:title" content="{_e(r.get("title"))}">\n' +
          (f'<meta property="og:description" content="{_e(r.get("summary"))}">\n' if r.get("summary") else "") +
          (f'<meta property="og:image" content="{_e(base)}/s/{_e(token)}/photo">\n' if r.get("photo") and base.startswith("http") else ""))
    return _doc(r.get("title") or "Recipe", "\n".join(out), "he" if he else "en", he, og)


def missing():
    """The page for a link that doesn't work (never was, or was unshared)."""
    return _doc("Not here", '<main class="wrap"><article class="sec"><h2>This link doesn\'t work anymore.</h2></article></main>')

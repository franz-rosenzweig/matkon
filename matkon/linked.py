"""The creator's own recipe page, when the caption links one ("full recipe: https://…").

That page is usually where the amounts are. Matkon fetches it once, as itself (no disguise), and
keeps either the page's schema.org Recipe (what recipe sites publish for search engines: exact
ingredients and steps) or, failing that, its plain text. A site that turns it away is noted and
skipped; the reel's own recipe still gets made.
"""
import html
import json
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (compatible; Matkon/0.1; a personal recipe app)"
SKIP = re.compile(r"instagram\.com|facebook\.com|tiktok\.com|youtube\.com|youtu\.be|linktr\.ee|beacons\.ai|stan\.store|amzn\.|amazon\.", re.I)
MAX_BYTES = 3_000_000
MAX_TEXT = 14000


def link_in(caption):
    for u in re.findall(r"https?://[^\s<>\"')\]]+", caption or ""):
        u = u.rstrip(".,;:!?")
        if not SKIP.search(u):
            return u
    return None


def _recipes(node):
    if isinstance(node, list):
        for x in node:
            yield from _recipes(x)
    elif isinstance(node, dict):
        t = node.get("@type")
        if t == "Recipe" or (isinstance(t, list) and "Recipe" in t):
            yield node
        for k in ("@graph", "mainEntity", "itemListElement"):
            if k in node:
                yield from _recipes(node[k])


def _steps(ins):
    out = []
    for x in ins if isinstance(ins, list) else [ins]:
        if isinstance(x, str):
            out.append(html.unescape(re.sub(r"<[^>]+>", " ", x)).strip())
        elif isinstance(x, dict):
            if x.get("@type") == "HowToSection":
                out.append(f"[{x.get('name', '')}]")
                out += _steps(x.get("itemListElement") or [])
            elif x.get("text"):
                out.append(html.unescape(re.sub(r"<[^>]+>", " ", x["text"])).strip())
    return [s for s in out if s]


def _text(page):
    page = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|form)\b.*?</\1>", " ", page)
    page = re.sub(r"(?i)<br\s*/?>|</(p|li|h\d|div|tr)>", "\n", page)
    page = html.unescape(re.sub(r"<[^>]+>", " ", page))
    lines = [re.sub(r"[ \t\xa0]+", " ", l).strip() for l in page.splitlines()]
    return "\n".join(l for l in lines if l)[:MAX_TEXT]


def substack_post(home, caption):
    """A link to a Substack's front page ("full recipe in my newsletter"): its archive search, for the
    dish named at the start of the caption. Returns the post's address, or None."""
    m = re.match(r"(https://[\w-]+\.substack\.com)/?$", home or "")
    if not m:
        return None
    first = re.split(r"[.\n!|:—-]", (caption or "").strip(), 1)[0]
    words = re.findall(r"[^\W_]+", first)[:6]
    if not words:
        return None
    url = m.group(1) + "/api/v1/archive?" + urllib.parse.urlencode({"sort": "new", "search": " ".join(words), "limit": 5})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20) as r:
            posts = json.loads(r.read(1_000_000))
    except Exception:  # noqa: BLE001
        return None
    want = {w.lower() for w in words}
    for post in posts if isinstance(posts, list) else []:
        title = {w.lower() for w in re.findall(r"[^\W_]+", post.get("title") or "")}
        if post.get("canonical_url") and len(want & title) >= max(1, len(want) // 2):
            return post["canonical_url"]
    return None


def fetch(url, caption=None):
    """{"url", "final", "kind": "recipe"|"text"|"error", ...}"""
    first = _fetch(url)
    post = substack_post(first.get("final") or url, caption) if first.get("kind") != "recipe" else None
    if post:
        second = _fetch(post)
        if second.get("kind") != "error":
            return second | {"url": url, "via": first.get("final")}
    return first


def _fetch(url):
    out = {"url": url}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8"})
        with urllib.request.urlopen(req, timeout=25) as r:
            out["final"] = r.geturl()
            page = r.read(MAX_BYTES).decode(r.headers.get_content_charset() or "utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - a page we can't get is only a missing extra
        return out | {"kind": "error", "error": str(e)[:200]}
    for block in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for rec in _recipes(data):
            ing = rec.get("recipeIngredient") or rec.get("ingredients") or []
            if not ing:
                continue
            nut = {k: v for k, v in (rec.get("nutrition") or {}).items() if not k.startswith("@")} if isinstance(rec.get("nutrition"), dict) else {}
            return out | {"kind": "recipe", "recipe": {
                "name": rec.get("name"), "yield": rec.get("recipeYield"), "prep": rec.get("prepTime"),
                "cook": rec.get("cookTime"), "total": rec.get("totalTime"),
                "ingredients": [html.unescape(str(i)).strip() for i in ing],
                "steps": _steps(rec.get("recipeInstructions") or []), "nutrition": nut}}
    text = _text(page)
    return out | ({"kind": "text", "text": text} if len(text) > 200 else {"kind": "error", "error": "no readable text"})


def as_prompt(linked):
    if not linked or linked.get("kind") == "error":
        return "(none)" if not linked else f"{linked['url']}: couldn't be read ({linked.get('error', '')})"
    if linked["kind"] == "recipe":
        return f"{linked.get('final') or linked['url']} (the page's own recipe data):\n" + json.dumps(linked["recipe"], ensure_ascii=False, indent=1)
    return f"{linked.get('final') or linked['url']} (the page's text; it may be cut short by a paywall):\n" + linked["text"]

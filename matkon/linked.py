"""A recipe page on the web: the creator's own, when a reel's caption links one ("full recipe:
https://…"), or one added by its link ("Add from a link", sources.py).

That page is usually where the amounts are. Matkon fetches it once, as itself (no disguise), and
keeps either the page's schema.org Recipe (what recipe sites publish for search engines: exact
ingredients and steps) or, failing that, its plain text, and the page's name, photo and date. A site
that turns it away is noted and skipped; the reel's own recipe still gets made.

Never Instagram or the rest of Meta (not even through a short link), and never an address on this
machine or a private network (a tailnet, a LAN): MATKON_PRIVATE_LINKS=1 allows those, for tests.
"""
import html
import ipaddress
import json
import os
import re
import socket
import urllib.parse
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; Matkon/0.1; a personal recipe app)"
SKIP = re.compile(r"instagram\.com|instagr\.am|cdninstagram\.com|fbcdn\.net|facebook\.com|fb\.me|threads\.(?:net|com)|tiktok\.com|youtube\.com|"
                  r"youtu\.be|linktr\.ee|beacons\.ai|stan\.store|amzn\.|amazon\.", re.I)
META_DOMAINS = ("instagram.com", "instagr.am", "ig.me", "cdninstagram.com", "facebook.com", "facebook.net", "fb.com", "fb.me",
                "fb.watch", "fb.gg", "fbcdn.net", "fbsbx.com", "threads.net", "threads.com", "meta.com", "meta.ai",
                "messenger.com", "m.me", "whatsapp.com", "whatsapp.net", "wa.me", "oculus.com", "workplace.com")
META = re.compile(r"^https?://(?:[^/?#@]*@)?(?:[^/?#]*\.)?(?:" + "|".join(re.escape(d) for d in META_DOMAINS) + r")\.?(?:[:/?#]|$)", re.I)


def _host(url):
    try:
        return (urllib.parse.urlsplit(url or "").hostname or "").rstrip(".").lower()
    except ValueError:
        return ""


def is_meta(url):
    """Whether the address is Instagram's, Facebook's, Threads' or another of Meta's."""
    host = _host(url)
    return bool(META.match(url or "")) or any(host == d or host.endswith("." + d) for d in META_DOMAINS)


def public(url):
    """False when the address is this machine or a private network. An address that doesn't resolve
    counts as public: asking for it just fails."""
    if os.environ.get("MATKON_PRIVATE_LINKS") == "1":
        return True
    host = _host(url)
    if not host:
        return False
    try:
        found = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError):
        return True
    return all(ipaddress.ip_address(a[4][0].split("%")[0]).is_global for a in found)


class _NotMeta(urllib.request.HTTPRedirectHandler):
    """Matkon's server never asks Instagram (or the rest of Meta) for anything, not even through a short link."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if is_meta(newurl):
            raise urllib.error.URLError("the link leads to Instagram")
        if not public(newurl):
            raise urllib.error.URLError("the link leads to a private address")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPEN = urllib.request.build_opener(_NotMeta())
MAX_BYTES = 3_000_000
MAX_TEXT = 14000
MAX_IMAGE = 15_000_000


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
        with _OPEN.open(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20) as r:
            posts = json.loads(r.read(1_000_000))
    except Exception:  # noqa: BLE001
        return None
    want = {w.lower() for w in words}
    for post in posts if isinstance(posts, list) else []:
        title = {w.lower() for w in re.findall(r"[^\W_]+", post.get("title") or "")}
        if post.get("canonical_url") and len(want & title) >= max(1, len(want) // 2):
            return post["canonical_url"]
    return None


def fetch(url, caption=None, keep_text=False):
    """{"url", "final", "kind": "recipe"|"text"|"error", "page": {...}, ...}"""
    first = _fetch(url, keep_text)
    post = substack_post(first.get("final") or url, caption) if first.get("kind") != "recipe" else None
    if post:
        second = _fetch(post, keep_text)
        if second.get("kind") != "error":
            return second | {"url": url, "via": first.get("final")}
    return first


def _fetch(url, keep_text=False):
    """keep_text: the page's text too, beside its recipe data (for a page added by its link, where the
    writer's notes around the recipe are all there is besides it)."""
    out = {"url": url}
    if is_meta(url):
        return out | {"kind": "error", "error": "the link leads to Instagram"}
    if not public(url):
        return out | {"kind": "error", "error": "the link leads to a private address"}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8"})
        with _OPEN.open(req, timeout=25) as r:
            out["final"] = r.geturl()
            page = r.read(MAX_BYTES).decode(r.headers.get_content_charset() or "utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - a page we can't get is only a missing extra
        return out | {"kind": "error", "error": str(e)[:200]}
    blocks, found = [], None
    for block in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page):
        try:
            blocks.append(json.loads(block.strip(), strict=False))
        except ValueError:
            continue
        for rec in _recipes(blocks[-1]):
            if rec.get("recipeIngredient") or rec.get("ingredients"):
                found = rec
                break
        if found:
            break
    out["page"] = facts(page, blocks, found, out.get("final") or url)
    text = _text(page)
    if found:
        rec, ing = found, found.get("recipeIngredient") or found.get("ingredients")
        nut = {k: v for k, v in (rec.get("nutrition") or {}).items() if not k.startswith("@")} if isinstance(rec.get("nutrition"), dict) else {}
        return out | {"kind": "recipe", "recipe": {
            "name": rec.get("name"), "yield": rec.get("recipeYield"), "prep": rec.get("prepTime"),
            "cook": rec.get("cookTime"), "total": rec.get("totalTime"),
            "ingredients": [html.unescape(str(i)).strip() for i in (ing if isinstance(ing, list) else [ing])],
            "steps": _steps(rec.get("recipeInstructions") or []), "nutrition": nut}} | ({"text": text} if keep_text and text else {})
    return out | ({"kind": "text", "text": text} if len(text) > 200 else {"kind": "error", "error": "no readable text"})


# ---- what the page says about itself: its site's name, its photo, its date ----

def _nodes(data, into):
    if isinstance(data, list):
        for x in data:
            _nodes(x, into)
    elif isinstance(data, dict):
        into.append(data)
        for v in data.values():
            if isinstance(v, (list, dict)):
                _nodes(v, into)


def _types(node):
    t = node.get("@type")
    return set(t) if isinstance(t, list) else {t}


def _metas(page):
    """{property or name: content} of the page's <meta> tags (the first of each)."""
    out = {}
    for tag in re.findall(r"(?is)<meta\b[^>]*>", page[:600_000]):
        attrs = {k.lower(): html.unescape(v.strip("\"'")) for k, v in re.findall(r"""([\w:-]+)\s*=\s*("[^"]*"|'[^']*'|[^\s"'>]+)""", tag)}
        key = (attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or "").strip().lower()
        if key and (attrs.get("content") or "").strip() and key not in out:
            out[key] = attrs["content"].strip()
    return out


def _images(v, ids, depth=0):
    """Addresses from a schema.org image: an address, an ImageObject, a reference to one, or a list of them."""
    if depth > 3:
        return []
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [u for x in v for u in _images(x, ids, depth + 1)]
    if isinstance(v, dict):
        u = v.get("url") or v.get("contentUrl")
        if isinstance(u, str):
            return [u]
        if isinstance(v.get("@id"), str) and v["@id"] in ids:
            return _images(ids[v["@id"]], {}, depth + 1)
    return []


def _date(s):
    """Seconds since 1970 from an ISO date ("2024-03-01", "2024-03-01T09:00:00+02:00"), or None."""
    from datetime import datetime, timezone
    s = str(s or "").strip()
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        m = re.match(r"\d{4}-\d{2}-\d{2}", s)
        if not m:
            return None
        d = datetime.fromisoformat(m.group(0))
    return int((d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp())


def facts(page, blocks, rec, base):
    """{"site", "title", "images", "published"}: the site's own name for itself, the page's title, the
    recipe's photos (else the one the page gives for shares) and when it was published, as far as the
    page says."""
    nodes = []
    _nodes(blocks, nodes)
    ids = {n["@id"]: n for n in nodes if isinstance(n.get("@id"), str)}
    meta = _metas(page)
    site = meta.get("og:site_name")
    if not site and rec:
        pub = rec.get("publisher")
        pub = ids.get(pub.get("@id"), pub) if isinstance(pub, dict) and isinstance(pub.get("@id"), str) else pub
        site = pub.get("name") if isinstance(pub, dict) else None
    site = site or next((n["name"] for n in nodes if "WebSite" in _types(n) and isinstance(n.get("name"), str)), None) \
        or meta.get("application-name")
    title = meta.get("og:title")
    if not title:
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
        title = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""
    images = []
    for u in (_images(rec.get("image"), ids) if rec else []) + [meta.get(k) for k in (
            "og:image", "og:image:secure_url", "og:image:url", "twitter:image", "twitter:image:src")]:
        u = urllib.parse.urljoin(base, html.unescape(u.strip())) if isinstance(u, str) and u.strip() else None
        if u and u.startswith(("http://", "https://")) and u not in images:
            images.append(u)
    published = _date(rec.get("datePublished")) if rec else None
    published = published or _date(meta.get("article:published_time"))
    for n in nodes:
        if published:
            break
        published = _date(n.get("datePublished")) if n.get("datePublished") else None
    return {"site": html.unescape(str(site or "")).strip()[:120], "title": str(title or "")[:200], "images": images[:6],
            "published": published}


def download(url, limit=MAX_IMAGE):
    """A file from a page (its photo), as bytes. Never from Meta or a private address. Raises when it can't."""
    if is_meta(url) or not public(url):
        raise ValueError("not an address Matkon asks")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/avif,image/webp,image/*,*/*;q=0.5"})
    with _OPEN.open(req, timeout=30) as r:
        data = r.read(limit + 1)
    if len(data) > limit or not data:
        raise ValueError("too big" if data else "empty")
    return data


def as_prompt(linked):
    if not linked or linked.get("kind") == "error":
        return "(none)" if not linked else f"{linked['url']}: couldn't be read ({linked.get('error', '')})"
    if linked["kind"] == "recipe":
        return f"{linked.get('final') or linked['url']} (the page's own recipe data):\n" + json.dumps(linked["recipe"], ensure_ascii=False, indent=1)
    return f"{linked.get('final') or linked['url']} (the page's text; it may be cut short by a paywall):\n" + linked["text"]

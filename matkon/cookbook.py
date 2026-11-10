"""A copy of every recipe in Nextcloud Cookbook, so the Cookbook apps on phones (Android, iPhone) have
them too, offline. Optional: MATKON_COOKBOOK is the WebDAV address of Cookbook's folder
(https://your-cloud/remote.php/dav/files/<user>/Recipes) and MATKON_COOKBOOK_LOGIN a file holding
user:app-password (an app password from Nextcloud's Settings › Security).

Each recipe is a folder named after it, holding recipe.json (a schema.org Recipe, which is how Cookbook
keeps them) and full.jpg. Matkon only sends. It keeps a list of what it sent (STATE/cookbook.json) and
sends a recipe again only when Matkon's own copy changes, so a recipe deleted in Cookbook stays deleted,
and an edit made there lasts until Matkon redoes that recipe.
"""
import base64
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import accounts, config, memory
from .store import read as _read

SENT = config.STATE / "cookbook.json"
BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
LABELS = {"en": {"tips": "Tips", "miss": "Not in the reel", "oven": "Oven"},
          "he": {"tips": "טיפים", "miss": "חסר בסרטון", "oven": "תנור"}}


def enabled():
    return bool(config.COOKBOOK and config.COOKBOOK_LOGIN)


def _sent():
    return _read(SENT, {}) or {}


def _save(s):
    tmp = SENT.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, ensure_ascii=False, indent=1))
    tmp.replace(SENT)


def _url(*parts):
    return config.COOKBOOK.rstrip("/") + "".join("/" + urllib.parse.quote(p, safe="") for p in parts)


def _call(method, url, data=None, headers=None):
    login = Path(config.COOKBOOK_LOGIN).read_text(encoding="utf-8").strip()
    h = {"Authorization": "Basic " + base64.b64encode(login.encode()).decode(), "OCS-APIRequest": "true", **(headers or {})}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=h), timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


# ---- Matkon's recipe as a schema.org Recipe -------------------------------------------------------

def _minutes(s):
    """"10 to 12 min" → 12, "about 2 hours" → 120, "1.5 hours" → 90; None when there's no time in it."""
    s = (s or "").lower().replace(",", ".")
    for a, b in (("half an hour", "30 min"), ("an hour", "1 hour"), ("שעה וחצי", "90 דק"), ("חצי שעה", "30 דק"),
                 ("שעתיים", "2 שעות"), ("שעה", "1 שעות")):
        s = s.replace(a, b)
    h = re.findall(r"(\d+(?:\.\d+)?)\s*(?:h\b|hrs?\b|hours?\b|שעות\b)", s)
    m = re.findall(r"(\d+)\s*(?:m\b|mins?\b|minutes?\b|דק)", s)
    total = round(float(h[-1]) * 60 if h else 0) + (int(m[-1]) if m else 0)
    return total or None


def _duration(s):
    n = _minutes(s)
    return f"PT{n // 60}H{n % 60}M" if n else None


def _when(t):
    return datetime.fromtimestamp(int(t), timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000") if t else None


def chosen(f):
    """The recipe as it goes to Cookbook: in English when the owner reads Hebrew recipes in English."""
    r = _read(f / "recipe.json", {}) or {}
    en = f / "recipe.en.json"
    owner = accounts.owner()
    if r.get("lang") == "he" and en.exists() and owner and memory.load(owner).get("settings", {}).get("english"):
        r = {**r, **(_read(en, {}) or {}), "lang": "en"}
    return r


def schema(f, r, post, name):
    l = LABELS.get(r.get("lang"), LABELS["en"])
    ing = []
    for g in r.get("ingredient_groups") or []:
        if g.get("name"):
            ing.append("## " + g["name"])              # Cookbook shows "## " lines as headings
        for i in g.get("items") or []:
            t = " ".join(x for x in (i.get("amount"), i.get("item")) if x)
            ing.append(t + (", " + i["note"] if i.get("note") else ""))
    about = [r.get("summary") or ""]
    if r.get("oven"):
        about.append(f"{l['oven']}: {r['oven']}")
    for key, items in (("tips", r.get("tips")), ("miss", r.get("missing"))):
        if items:
            about.append(l[key] + "\n" + "\n".join("- " + x for x in items))
    n = r.get("nutrition") or {}
    nutrition = {k: n[m] for k, m in (("calories", "calories"), ("proteinContent", "protein"), ("carbohydrateContent", "carbs"),
                                      ("fatContent", "fat"), ("servingSize", "per")) if n.get(m)}
    servings = re.search(r"\d+", r.get("servings") or "")
    t = r.get("time") or {}
    return {
        "@context": "http://schema.org", "@type": "Recipe",
        "name": name,
        "description": "\n\n".join(x for x in about if x),
        "url": post.get("url") or "",
        "author": {"@type": "Person", "name": "@" + post["user"]} if post.get("user") else None,
        "image": "",
        "prepTime": _duration(t.get("prep")), "cookTime": _duration(t.get("cook")), "totalTime": _duration(t.get("total")),
        "recipeCategory": r.get("kind") or "",
        "keywords": ",".join(x.replace(",", " ") for x in (r.get("tags") or []) + ([r["cuisine"]] if r.get("cuisine") else [])),
        "recipeYield": int(servings.group(0)) if servings else None,
        "tool": [],
        "recipeIngredient": ing,
        "recipeInstructions": [s.get("text", "") for s in r.get("steps") or [] if s.get("text")],
        "nutrition": {"@type": "NutritionInformation", **nutrition} if nutrition else {},
        "dateCreated": _when(post.get("found")),
        "dateModified": _when(r.get("made")),
    }


def _photo(f, r):
    for name in (r.get("photo"), "photo.jpg", "cover.jpg"):
        if name and (f / name).exists():
            return f / name
    return None


def _sig(f, r):
    files = [f / "recipe.json", f / "recipe.en.json", _photo(f, r)]
    return "|".join(str(int(p.stat().st_mtime)) if p and p.exists() else "-" for p in files) + "|" + (r.get("lang") or "")


def _name(title):
    return re.sub(r"\s+", " ", BAD.sub(" ", title or "")).strip().strip(".")[:100] or "Recipe"


# ---- sending -----------------------------------------------------------------------------------

def send(code, sent):
    """Puts one recipe in Cookbook (or brings its copy up to date). Raises when Nextcloud says no."""
    f = config.REELS / code
    r = chosen(f)
    post = _read(f / "post.json", {}) or {}
    was = (sent.get(code) or {}).get("folder")
    taken = {v.get("folder") for k, v in sent.items() if k != code}
    base, n = _name(r.get("title")), 1
    while True:
        name = base if n == 1 else f"{base} ({n})"
        n += 1
        if name in taken:
            continue
        if was and was != name:                      # renamed: move the old folder rather than leave it behind
            st = _call("MOVE", _url(was), headers={"Destination": _url(name), "Overwrite": "F"})
            if st in (201, 204):
                break
            if st == 412:                            # a folder of that name that isn't ours
                continue
        st = _call("MKCOL", _url(name))
        if st == 201 or (st == 405 and name == was):
            break
        if st != 405:
            raise RuntimeError(f"Nextcloud said {st} to making the folder")
    body = json.dumps(schema(f, r, post, name), ensure_ascii=False, indent=1).encode()
    st = _call("PUT", _url(name, "recipe.json"), body, {"Content-Type": "application/json"})
    if st not in (201, 204):
        raise RuntimeError(f"Nextcloud said {st} to recipe.json")
    photo = _photo(f, r)
    if photo:
        st = _call("PUT", _url(name, "full.jpg"), photo.read_bytes(), {"Content-Type": "image/jpeg"})
        if st not in (201, 204):
            raise RuntimeError(f"Nextcloud said {st} to the photo")
        for thumb in ("thumb.jpg", "thumb16.jpg"):   # Cookbook makes them again from the new photo
            _call("DELETE", _url(name, thumb))
    sent[code] = {"folder": name, "sig": _sig(f, r), "at": int(time.time())}
    return name


def catch_up(say=print):
    """Sends whatever changed since the last time, and takes out what's no longer a recipe. Returns how
    many it sent; Nextcloud being away just leaves the rest for the next run."""
    if not enabled():
        return 0
    sent = _sent()
    count, changed = 0, False
    codes = sorted(p.name for p in config.REELS.iterdir()) if config.REELS.exists() else []
    for code in codes:
        f = config.REELS / code
        if not (f / "recipe.json").exists():
            continue
        r = chosen(f)
        if not r.get("is_recipe"):
            continue
        if (sent.get(code) or {}).get("sig") == _sig(f, r):
            continue
        try:
            name = send(code, sent)
        except (OSError, RuntimeError) as e:
            say(code, "cookbook:", e)
            break                                    # Nextcloud is away or unhappy: next run
        _save(sent)
        count, changed = count + 1, True
        say(code, "cookbook:", name)
    try:
        for code in [c for c in sent if not (config.REELS / c / "recipe.json").exists() or not chosen(config.REELS / c).get("is_recipe")]:
            if _call("DELETE", _url(sent[code]["folder"])) in (204, 404):
                say(code, "cookbook: taken out", sent[code]["folder"])
                sent.pop(code)
                _save(sent)
                changed = True
        if changed:                                  # Cookbook's list picks up the new folders now, not next time it looks
            _call("POST", config.COOKBOOK.split("/remote.php/")[0] + "/index.php/apps/cookbook/api/v1/reindex", b"")
    except OSError as e:
        say("cookbook:", e)
    return count

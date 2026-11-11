"""Fixing a recipe by hand. Claude sometimes gets one wrong, and most reels leave the amounts out.

An edit is the whole recipe as the person wrote it, kept next to Claude's, one per language
(reels/<code>/edits.<lang>.json: {"by", "at", "recipe"}). It's laid over what Claude wrote wherever
the recipe shows up: the app and the list (server.py), the vault note, the English copy of a Hebrew
recipe, the Cookbook copy and the export. A redo of the reel makes a new recipe.json and leaves the
edit where it is, so the edit still wins.

Only an admin or the account that added the reel may edit it.
"""
import time

from . import accounts
from .store import read as _read, write as _write

LANGS = ("en", "he")
FIELDS = ("title", "summary", "servings", "time", "oven", "ingredient_groups", "steps", "tips", "missing")
# the most a recipe holds; past these an edit is refused (strings are cut to theirs)
MAX = {"groups": 30, "items": 300, "steps": 100, "timers": 6, "tips": 50, "missing": 50}
CHARS = {"title": 200, "summary": 1000, "servings": 100, "time": 60, "oven": 100, "group": 100, "amount": 100, "item": 200,
         "note": 200, "step": 2000, "tip": 1000, "missing": 300}


def path(f, lang):
    return f / f"edits.{lang}.json"


def load(f, lang):
    e = _read(path(f, lang)) if lang in LANGS else None
    return e if isinstance(e, dict) and isinstance(e.get("recipe"), dict) else None


def stamp(f):
    """Which edits there are and when they changed (0: none), so a refresh started for an older edit can
    step aside."""
    out = []
    for lang in LANGS:
        try:
            out.append(str(path(f, lang).stat().st_mtime_ns))
        except OSError:
            out.append("0")
    return ",".join(out)


def can_edit(aid, added_by):
    return bool(aid) and (aid == (added_by or accounts.owner()) or bool((accounts.get(aid) or {}).get("admin")))


def complete(r, was):
    """True when every ingredient has an amount and nothing is missing; else what Claude said, unless
    the edit lists something missing."""
    items = [i for g in r.get("ingredient_groups") or [] for i in g.get("items") or []]
    if items and all(i.get("amount") for i in items) and not r.get("missing"):
        return True
    return bool(was) and not r.get("missing")


def lay(f, r, lang, orig):
    """r (recipe.json, or it with recipe.<lang>.json over it) with the edits laid over it.
    Returns (recipe, {"by", "at"} of this language's edit, or None)."""
    eo = load(f, orig)
    if lang != orig and eo:              # the English copy of an edited Hebrew recipe: its amounts are the edit's
        r = {**r, "complete": complete(eo["recipe"], r.get("complete", True))}
    e = load(f, lang)
    if not e:
        return r, None
    rec = e["recipe"]
    r = {**r, **{k: rec[k] for k in FIELDS if k in rec}, "complete": complete(rec, r.get("complete", True))}
    return r, {"by": e.get("by"), "at": e.get("at")}


def effective(f, r=None):
    """The recipe in its own language with its edit, as the note, the translation and Cookbook want it."""
    r = r if r is not None else _read(f / "recipe.json")
    if not r:
        return r
    orig = r.get("lang", "en")
    return lay(f, r, orig, orig)[0]


def save(f, lang, rec, by):
    _write(path(f, lang), {"by": by, "at": int(time.time()), "recipe": rec})


def revert(f, lang):
    """True when there was an edit to take away."""
    p = path(f, lang)
    had = p.exists()
    p.unlink(missing_ok=True)
    return had


# ---- what a person sends -------------------------------------------------------------------------

def _text(v, n):
    if v is None:
        return ""
    if isinstance(v, bool) or not isinstance(v, (str, int, float)):
        raise ValueError("That recipe isn't in the right shape.")
    return str(v).strip()[:n]


def _list(v):
    if v is None:
        return []
    if not isinstance(v, list):
        raise ValueError("That recipe isn't in the right shape.")
    return v


def _cap(xs, key, what):
    if len(xs) > MAX[key]:
        raise ValueError(f"A recipe holds {MAX[key]} {what} at most.")
    return xs


def clean(d):
    """The edit as it's kept, or ValueError with what's wrong. Empty lines (an ingredient with no name,
    a step with no words) are dropped."""
    if not isinstance(d, dict):
        raise ValueError("That recipe isn't in the right shape.")
    out = {"title": _text(d.get("title"), CHARS["title"])}
    if not out["title"]:
        raise ValueError("A recipe needs a title.")
    out["summary"] = _text(d.get("summary"), CHARS["summary"])
    out["servings"] = _text(d.get("servings"), CHARS["servings"])
    t = d.get("time") or {}
    if not isinstance(t, dict):
        raise ValueError("That recipe isn't in the right shape.")
    out["time"] = {k: _text(t.get(k), CHARS["time"]) for k in ("prep", "cook", "total")}
    out["oven"] = _text(d.get("oven"), CHARS["oven"])
    groups, count = [], 0
    for g in _list(d.get("ingredient_groups")):
        if not isinstance(g, dict):
            raise ValueError("That recipe isn't in the right shape.")
        items = []
        for i in _list(g.get("items")):
            if not isinstance(i, dict):
                raise ValueError("That recipe isn't in the right shape.")
            item = {"amount": _text(i.get("amount"), CHARS["amount"]), "item": _text(i.get("item"), CHARS["item"]),
                    "note": _text(i.get("note"), CHARS["note"])}
            if item["item"]:
                items.append(item)
        count += len(items)
        if items:
            groups.append({"name": _text(g.get("name"), CHARS["group"]), "items": items})
    _cap(groups, "groups", "ingredient groups")
    if count > MAX["items"]:
        raise ValueError(f"A recipe holds {MAX['items']} ingredients at most.")
    out["ingredient_groups"] = groups
    steps = []
    for s in _list(d.get("steps")):
        if isinstance(s, str):
            s = {"text": s}
        if not isinstance(s, dict):
            raise ValueError("That recipe isn't in the right shape.")
        timers = []
        for t in _list(s.get("timers")):
            if isinstance(t, bool) or not isinstance(t, (int, float)) or t != int(t) or not 1 <= t <= 1440:
                raise ValueError("A timer is a whole number of minutes, from 1 to 1440.")
            timers.append(int(t))
        if len(timers) > MAX["timers"]:
            raise ValueError(f"A step has {MAX['timers']} timers at most.")
        text = _text(s.get("text"), CHARS["step"])
        if text:
            steps.append({"text": text, "timers": timers})
    out["steps"] = _cap(steps, "steps", "steps")
    out["tips"] = _cap([x for x in (_text(t, CHARS["tip"]) for t in _list(d.get("tips"))) if x], "tips", "tips")
    out["missing"] = _cap([x for x in (_text(t, CHARS["missing"]) for t in _list(d.get("missing"))) if x], "missing",
                          "\"Not in the reel\" lines")
    return out

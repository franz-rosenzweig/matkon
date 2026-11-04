"""What Matkon remembers for each account, on the server so every device sees the same thing:
saved recipes, ticked ingredients and the cooking step (both forgotten after 12 hours), notes,
ratings (1-10), what was opened lately, what was cooked when, and the account's own settings.
STATE/users/<account>/memory.json.

`suggest` is the "learns your taste" part: it ranks the kitchen for one account from what that
account has saved, cooked, rated and opened.
"""
import json
import re
import secrets
import threading
import time

from . import config

FRESH = 12 * 3600          # ticks and the cooking step last this long
VIEWED = 60
_lock = threading.Lock()
DEFAULT_SETTINGS = {"nutrition": True, "english": False}


def folder(aid):
    f = config.STATE / "users" / aid
    f.mkdir(parents=True, exist_ok=True)
    return f


def _empty():
    return {"saved": {}, "ticks": {}, "steps": {}, "notes": {}, "ratings": {}, "viewed": [], "cooked": [], "settings": {}}


def load(aid):
    try:
        m = json.loads((folder(aid) / "memory.json").read_text())
    except (OSError, ValueError):
        m = {}
    return {**_empty(), **m}


def _save(aid, m):
    p = folder(aid) / "memory.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, ensure_ascii=False))
    tmp.replace(p)


def view(aid):
    """The memory as the app needs it: stale ticks and steps dropped, settings filled in."""
    m = load(aid)
    now = time.time()
    m["ticks"] = {c: t["keys"] for c, t in m["ticks"].items() if now - t.get("at", 0) < FRESH}
    m["steps"] = {c: s["n"] for c, s in m["steps"].items() if now - s.get("at", 0) < FRESH}
    m["notes"] = {c: n["text"] for c, n in m["notes"].items() if n.get("text")}
    m["settings"] = {**DEFAULT_SETTINGS, **m["settings"]}
    m["cooked_count"], m["cooked_last"] = {}, {}
    for e in m["cooked"]:
        m["cooked_count"][e["code"]] = m["cooked_count"].get(e["code"], 0) + 1
        m["cooked_last"][e["code"]] = max(m["cooked_last"].get(e["code"], 0), e["at"])
    return m


CODE = re.compile(r"^[\w-]{5,40}$")


def apply(aid, op, a):
    """One change. Returns the code it touched (for the vault), or None."""
    code = a.get("code")
    if code is not None and not CODE.match(str(code)):
        raise ValueError("bad recipe")
    now = int(time.time())
    with _lock:
        m = load(aid)
        if op == "save":
            if a.get("on"):
                m["saved"][code] = now
            else:
                m["saved"].pop(code, None)
        elif op == "ticks":
            m["ticks"][code] = {"keys": [str(k)[:12] for k in (a.get("keys") or [])][:200], "at": now}
        elif op == "step":
            n = a.get("n")
            if n is None:
                m["steps"].pop(code, None)
            else:
                m["steps"][code] = {"n": int(n), "at": now}
        elif op == "view":
            m["viewed"] = [[code, now]] + [v for v in m["viewed"] if v[0] != code][: VIEWED - 1]
        elif op == "cooked":
            m["cooked"].append({"id": secrets.token_hex(4), "code": code, "at": int(a.get("at") or now)})
            m["steps"].pop(code, None)
            m["ticks"].pop(code, None)
        elif op == "uncook":
            m["cooked"] = [e for e in m["cooked"] if e["id"] != a.get("id")]
        elif op == "note":
            text = str(a.get("text") or "")[:5000]
            if text.strip():
                m["notes"][code] = {"text": text, "at": now}
            else:
                m["notes"].pop(code, None)
        elif op == "rate":
            r = a.get("rating")
            if r in (None, 0, ""):
                m["ratings"].pop(code, None)
            else:
                m["ratings"][code] = max(1, min(10, int(r)))
        elif op == "setting":
            key = a.get("key")
            if key not in DEFAULT_SETTINGS:
                raise ValueError("no such setting")
            m["settings"][key] = bool(a.get("value"))
        else:
            raise ValueError("no such change")
        _save(aid, m)
    return code if op in ("cooked", "uncook", "note", "rate") else None


# ---- what to make next ---------------------------------------------------------------------------

def _words(r):
    return {w for w in [r.get("kind"), r.get("cuisine")] + list(r.get("tags") or []) + list(r.get("main_ingredients") or []) if w}


def suggest(aid, recipes, limit=8):
    """[{code, why}] for this account. Saved and never made, liked and not made for a while, like the
    ones it rates highly or cooks again, and new ones it hasn't opened. Nothing it rated 4 or less,
    nothing made in the last 5 days."""
    m = view(aid)
    now = time.time()
    by = {r["code"]: r for r in recipes if r.get("is_recipe") is not False}
    liked = [c for c, n in m["ratings"].items() if n >= 8 and c in by]
    liked += [c for c, k in m["cooked_count"].items() if k >= 2 and c in by and c not in liked]
    taste = {}
    for c in liked:
        for w in _words(by[c]):
            taste[w] = taste.get(w, 0) + 1
    seen = {v[0] for v in m["viewed"]}
    out = []
    for c, r in by.items():
        rating = m["ratings"].get(c)
        last = m["cooked_last"].get(c)
        if (rating is not None and rating <= 4) or (last and now - last < 5 * 86400):
            continue
        score, why = 0.0, None
        if c in m["saved"] and not last:
            score, why = 6, ("saved", None)
        if rating and rating >= 8 and last and now - last > 14 * 86400:
            s = 4 + rating - 8 + min(4, (now - last) / (14 * 86400))
            if s > score:
                score, why = s, ("again", last)
        overlap = len(_words(r) & set(taste))
        if overlap and c not in liked:
            best = max(liked, key=lambda x: len(_words(by[x]) & _words(r)))
            s = 2 + overlap * 0.8
            if s > score:
                score, why = s, ("like", by[best]["title"])
        if c not in seen and not last and now - (r.get("found") or 0) < 10 * 86400:
            s = 3.5
            if s > score:
                score, why = s, ("new", None)
        if not why:
            continue
        if not r.get("complete", True):
            score -= 1
        out.append((score, r.get("found") or 0, c, why))
    out.sort(key=lambda x: (-x[0], -x[1]))
    return [{"code": c, "why": w[0], "about": w[1]} for _, _, c, w in out[:limit]]


# ---- history -------------------------------------------------------------------------------------

def runs(limit=60):
    """The import log (STATE/runs.jsonl), newest first."""
    try:
        lines = (config.STATE / "runs.jsonl").read_text().splitlines()[-400:]
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out[:limit]


def log_run(entry):
    entry = {"at": int(time.time()), **entry}
    with open(config.STATE / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

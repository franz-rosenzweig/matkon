"""What Matkon remembers for each account, on the server so every device sees the same thing:
saved recipes, ticked ingredients and the cooking step (both forgotten after 12 hours), notes,
ratings (1-10), what was opened lately, what was cooked when (with how much and a note), the week
plan, the shopping list, its own collections of recipes, what's in its kitchen (the pantry), which
aisle each thing on the list is in, and the account's own settings.
STATE/users/<account>/memory.json.

A household is two or more accounts with one week plan and one shopping list between them
(STATE/households.json: {id: {"members": [...]}}, and the lists in STATE/households/<id>.json). The
plan and list ops work on the household's lists then, and view() shows them in place of the
account's own, so the apps don't need to know.

`suggest` is the "learns your taste" part: it ranks the kitchen for one account from what that
account has saved, cooked, rated and opened.
"""
import json
import re
import secrets
import threading
import time

from . import accounts, config

FRESH = 12 * 3600          # ticks and the cooking step last this long
VIEWED = 60
PLAN_KEEP = 14             # days a planned meal stays after its day
SHOP_MAX = 600
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID = re.compile(r"^[0-9a-f]{8}$")


def _id(x):
    """The id an app made up (so it can work offline), or a new one."""
    return x if isinstance(x, str) and ID.match(x) else secrets.token_hex(4)
_lock = threading.Lock()
DEFAULT_SETTINGS = {"nutrition": True, "english": False, "units": ""}
UNITS = ("", "metric", "us")        # as written, or shown in metric or US units
AISLES = ("produce", "dairy", "meat", "bakery", "pantry", "spices", "frozen", "drinks", "household", "other")
COLLECTIONS_MAX, COLLECTION_SIZE = 100, 2000
PANTRY_MAX, AISLES_MAX = 400, 2000


def folder(aid):
    f = config.STATE / "users" / aid
    f.mkdir(parents=True, exist_ok=True)
    return f


def _empty():
    return {"saved": {}, "ticks": {}, "steps": {}, "notes": {}, "ratings": {}, "viewed": [], "cooked": [], "settings": {},
            "plan": [], "shop": [], "collections": [], "pantry": [], "aisles": {}}


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
    hid, h = _household(aid)
    if hid:                                   # the household's plan and list, in place of the account's own
        lists = _lists(hid)
        m["plan"], m["shop"] = lists["plan"], lists["shop"]
    m["household"] = [x for x in h["members"] if x != aid] if hid else []
    since = time.strftime("%Y-%m-%d", time.localtime(now - PLAN_KEEP * 86400))
    m["plan"] = sorted((p for p in m["plan"] if p["day"] >= since), key=lambda p: (p["day"], p["at"]))
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
    op = str(op or "")
    with _lock:
        m = load(aid)
        hid = _household(aid)[0] if op.startswith(("plan-", "shop-")) else None
        if hid:
            lists = _lists(hid)
            m["plan"], m["shop"] = lists["plan"], lists["shop"]
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
            e = {"id": _id(a.get("id")), "code": code, "at": int(a.get("at") or now)}
            if a.get("factor") is not None:
                e["factor"] = _factor(a["factor"])
            if _note(a.get("note")):
                e["note"] = _note(a.get("note"))
            m["cooked"].append(e)
            m["steps"].pop(code, None)
            m["ticks"].pop(code, None)
        elif op == "cook-note":
            e = next((e for e in m["cooked"] if e["id"] == a.get("id")), None)
            if not e:
                raise ValueError("That isn't in the cooking log.")
            if _note(a.get("note")):
                e["note"] = _note(a.get("note"))
            else:
                e.pop("note", None)
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
        elif op == "plan-add":
            day = str(a.get("day") or "")
            if not DAY.match(day):
                raise ValueError("bad day")
            m["plan"].append({"id": _id(a.get("id")), "code": code, "day": day, "at": now})
            m["plan"] = m["plan"][-400:]
        elif op == "plan-move":
            day = str(a.get("day") or "")
            if not DAY.match(day):
                raise ValueError("bad day")
            for p in m["plan"]:
                if p["id"] == a.get("id"):
                    p["day"] = day
        elif op == "plan-remove":
            m["plan"] = [p for p in m["plan"] if p["id"] != a.get("id")]
        elif op == "shop-add":
            # a recipe's ingredients (as scaled on the phone), or one thing typed in (no code)
            for i in (a.get("items") or [])[:200]:
                item = str(i.get("item") or "").strip()[:200]
                if item:
                    m["shop"].append({"id": _id(i.get("id")), "item": item, "amount": str(i.get("amount") or "")[:60],
                                      "code": code, "done": False, "at": now})
            m["shop"] = m["shop"][-SHOP_MAX:]
        elif op == "shop-tick":
            ids = {str(x) for x in a.get("ids") or []}
            for i in m["shop"]:
                if i["id"] in ids:
                    i["done"] = bool(a.get("done"))
        elif op == "shop-remove":
            ids = {str(x) for x in a.get("ids") or []}
            m["shop"] = [i for i in m["shop"] if i["id"] not in ids]
        elif op == "shop-clear":
            m["shop"] = [i for i in m["shop"] if not i["done"]] if a.get("done") else []
        elif op == "coll-new":
            name, cid = _name(a.get("name")), _id(a.get("id"))
            if not any(c["id"] == cid for c in m["collections"]):     # the same one again (an app catching up): nothing new
                if len(m["collections"]) >= COLLECTIONS_MAX:
                    raise ValueError(f"That's {COLLECTIONS_MAX} collections already.")
                m["collections"].append({"id": cid, "name": name, "codes": []})
        elif op == "coll-rename":
            _collection(m, a.get("id"))["name"] = _name(a.get("name"))
        elif op == "coll-delete":
            m["collections"] = [c for c in m["collections"] if c["id"] != a.get("id")]
        elif op == "coll-add":
            if code is None:
                raise ValueError("bad recipe")
            c = _collection(m, a.get("id"))
            if code not in c["codes"]:
                if len(c["codes"]) >= COLLECTION_SIZE:
                    raise ValueError("That collection is full.")
                c["codes"].append(code)
        elif op == "coll-remove":
            for c in m["collections"]:
                if c["id"] == a.get("id"):
                    c["codes"] = [x for x in c["codes"] if x != code]
        elif op == "pantry":
            items = a.get("items")
            if not isinstance(items, list):
                raise ValueError("The pantry is a list.")
            out, seen = [], set()
            for x in items:
                x = str(x).strip()[:60].strip() if isinstance(x, (str, int, float)) and not isinstance(x, bool) else ""
                if x and x.casefold() not in seen:
                    seen.add(x.casefold())
                    out.append(x)
            m["pantry"] = out[:PANTRY_MAX]
        elif op == "aisle":
            key, aisle = a.get("key"), a.get("aisle") or ""
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Which item?")
            if len(key) > 80:
                raise ValueError("An item's name for an aisle is 80 characters at most.")
            if aisle and aisle not in AISLES:
                raise ValueError("No such aisle.")
            m["aisles"].pop(key, None)
            if aisle:
                m["aisles"][key] = aisle                       # the newest last, so the oldest go first past the cap
                m["aisles"] = dict(list(m["aisles"].items())[-AISLES_MAX:])
        elif op == "setting":
            key = a.get("key")
            if key not in DEFAULT_SETTINGS:
                raise ValueError("no such setting")
            if key == "units":
                v = a.get("value") or ""
                if v not in UNITS:
                    raise ValueError('Units are "" (as written), "metric" or "us".')
                m["settings"][key] = v
            else:
                m["settings"][key] = bool(a.get("value"))
        else:
            raise ValueError("no such change")
        if hid:
            _write_json(_lists_path(hid), {"plan": m["plan"], "shop": m["shop"]})
        else:
            _save(aid, m)
    return code if op in ("cooked", "uncook", "note", "rate") else None


def _factor(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0.25 <= v <= 10:
        raise ValueError("The amount you made goes from 0.25 to 10 times the recipe.")
    return v


def _note(v):
    return str(v or "").strip()[:500] if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""


def _name(v):
    name = str(v or "").strip()[:60].strip() if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""
    if not name:
        raise ValueError("A collection needs a name.")
    return name


def _collection(m, cid):
    c = next((c for c in m["collections"] if c["id"] == cid), None)
    if not c:
        raise ValueError("No such collection.")
    return c


# ---- households ----------------------------------------------------------------------------------

def _write_json(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(p)


def _hh_path():
    return config.STATE / "households.json"


def _households():
    try:
        d = json.loads(_hh_path().read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in d.items() if ID.match(k) and isinstance(v, dict) and isinstance(v.get("members"), list)} \
        if isinstance(d, dict) else {}


def _household(aid, d=None):
    """(id, {"members"}) of the household this account is in, or (None, None)."""
    for hid, h in (_households() if d is None else d).items():
        if aid in h["members"]:
            return hid, h
    return None, None


def _lists_path(hid):
    return config.STATE / "households" / f"{hid}.json"


def _lists(hid):
    try:
        lists = json.loads(_lists_path(hid).read_text())
    except (OSError, ValueError):
        lists = {}
    return {"plan": list(lists.get("plan") or []), "shop": list(lists.get("shop") or [])}


def households():
    return [{"id": hid, "members": list(h["members"])} for hid, h in _households().items()]


def _merge(into, more):
    """`into` and then whatever of `more` it doesn't have already (the same id)."""
    have = {x.get("id") for x in into}
    return into + [x for x in more if x.get("id") not in have]


def household_join(members):
    """Puts these accounts (two or more) in one household: a new one, or the one some of them are in
    already. Each account that joins brings its own week plan and list into the household's. Returns
    the household's id."""
    ids = []
    for x in members if isinstance(members, list) else []:
        x = str(x or "").strip().lower()
        if x and x not in ids:
            ids.append(x)
    if len(ids) < 2:
        raise ValueError("A household is two accounts or more.")
    for x in ids:
        if not accounts.get(x):
            raise ValueError(f"There's no account called {x}.")
    with _lock:
        d = _households()
        hids = {_household(x, d)[0] for x in ids} - {None}
        if len(hids) > 1:
            raise ValueError("Those accounts are in different households. One has to leave first.")
        hid = next(iter(hids)) if hids else None
        while not hid:
            hid = secrets.token_hex(4)
            hid = None if hid in d else hid
        h = d.get(hid) or {"members": []}
        joining = [x for x in ids if x not in h["members"]]
        if not joining:
            return hid
        lists = _lists(hid)
        for x in joining:
            m = load(x)
            lists["plan"], lists["shop"] = _merge(lists["plan"], m["plan"]), _merge(lists["shop"], m["shop"])
        lists["plan"], lists["shop"] = lists["plan"][-400:], lists["shop"][-SHOP_MAX:]
        _write_json(_lists_path(hid), lists)           # the lists first: a stop halfway loses nothing
        d[hid] = {**h, "members": h["members"] + joining}
        _write_json(_hh_path(), d)
        for x in joining:
            m = load(x)
            m["plan"], m["shop"] = [], []
            _save(x, m)
    return hid


def household_leave(aid):
    """Takes this account out of its household, with a copy of the household's plan and list. A
    household left with one account is over, and that account keeps the lists too."""
    with _lock:
        d = _households()
        hid, h = _household(aid, d)
        if not hid:
            raise ValueError("That account isn't in a household.")
        lists = _lists(hid)
        left = [x for x in h["members"] if x != aid]
        for x in [aid] + (left if len(left) < 2 else []):
            m = load(x)
            m["plan"], m["shop"] = json.loads(json.dumps(lists["plan"])), json.loads(json.dumps(lists["shop"]))
            _save(x, m)
        if len(left) < 2:
            del d[hid]
        else:
            d[hid] = {**h, "members": left}
        _write_json(_hh_path(), d)
        if hid not in d:
            _lists_path(hid).unlink(missing_ok=True)


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

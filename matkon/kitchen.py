"""Whose Instagram feeds the kitchen, through which browser.

Everyone sees every recipe. Any account can also connect a browser (the Matkon extension, with a key
made in Settings) and pick one of its saved collections there, and the reels in it join the kitchen with
that account as the one who added them. STATE/users/<account>/instagram.json ({collection_id,
collection_name}) and browser.json ({hash of the key, made, seen, version, error}).

The owner's account falls back to the collection in settings.json, which is how a setup from before
accounts keeps working.
"""
import hashlib
import hmac
import json
import secrets
import time

from . import accounts, config


def _dir(aid):
    f = config.STATE / "users" / aid
    f.mkdir(parents=True, exist_ok=True)
    return f


def _get(aid, name):
    try:
        return json.loads((_dir(aid) / name).read_text())
    except (OSError, ValueError):
        return {}


def _put(aid, name, info):
    p = _dir(aid) / name
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(info))
    tmp.replace(p)


def of(aid):
    """{"collection_id", "collection_name", "browser": {made, seen, version, error} or None}"""
    info = _get(aid, "instagram.json")
    is_owner = aid == accounts.owner()
    st = config.settings()
    cid = info.get("collection_id") or (st.get("collection_id") if is_owner else None)
    name = info.get("collection_name") or (st.get("collection_name") if is_owner and cid == st.get("collection_id") else None)
    b = _get(aid, "browser.json")
    return {"collection_id": str(cid) if cid else None, "collection_name": name or "",
            "browser": {k: b.get(k) for k in ("made", "seen", "version", "error", "checked")} if b.get("hash") else None}


def set_collection(aid, cid, name=""):
    info = _get(aid, "instagram.json")
    info.update(collection_id=str(cid), collection_name=(name or "").strip()[:60])
    _put(aid, "instagram.json", info)
    if aid == accounts.owner():
        st = config.settings()                     # the owner's collection lives in settings.json too
        st.update(collection_id=str(cid), collection_name=(name or "").strip()[:60] or "Recipes")
        config.save_settings(st)


# ---- the browser's key ----------------------------------------------------------------------------

def _hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


def new_key(aid):
    """A new key for this account's browser; the old one stops working. Only its hash is kept."""
    key = "mk_" + secrets.token_urlsafe(24)
    _put(aid, "browser.json", {"hash": _hash(key), "made": int(time.time())})
    return key


def forget_browser(aid):
    (_dir(aid) / "browser.json").unlink(missing_ok=True)


def who(key):
    """The account a browser key belongs to, or None."""
    if not key or not key.startswith("mk_") or len(key) > 100:
        return None
    h = _hash(key)
    for a in accounts.all_accounts():
        b = _get(a["id"], "browser.json")
        if b.get("hash") and hmac.compare_digest(b["hash"], h):
            return a["id"]
    return None


def seen(aid, version=None, error=None, checked=False):
    """The browser said hello: when, which version, and what went wrong on Instagram's side, if anything."""
    b = _get(aid, "browser.json")
    if not b.get("hash"):
        return
    b.update(seen=int(time.time()), version=str(version or "")[:20] or b.get("version"), error=(str(error)[:120] if error else None))
    if checked:
        b["checked"] = int(time.time())
    _put(aid, "browser.json", b)

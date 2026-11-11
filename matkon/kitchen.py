"""Whose Instagram feeds the kitchen, and how.

Everyone sees every recipe. Any account can also connect a browser (the Matkon extension, with a key
made in Settings) and pick one of its saved collections there, and the reels in it join the kitchen with
that account as the one who added them. STATE/users/<account>/instagram.json ({collection_id,
collection_name}) and browser.json ({hash of the key, made, seen, version, error}).

Or an account pastes an Instagram sign-in (its cookies) into Settings, and the server looks itself
(igserver.py). That's sign-in.json, mode 600: the cookies, the browser it came from, and how the
looking went. Its cookies never leave the server and never go to the app.

The owner's account falls back to the collection in settings.json, which is how a setup from before
accounts keeps working.
"""
import hashlib
import hmac
import json
import os
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


# ---- a pasted Instagram sign-in (the server looks itself) ------------------------------------------

SIGNIN = "sign-in.json"
REQUIRED = ("sessionid", "ds_user_id", "csrftoken")


def signin(aid):
    """Everything about the account's pasted sign-in (cookies included): for igserver.py only."""
    return _get(aid, SIGNIN)


def save_signin(aid, info):
    p = _dir(aid) / SIGNIN
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(info, f)
    tmp.replace(p)


def set_signin(aid, jar, ua, langs):
    """A new sign-in: the cookies, and the browser they came from (the server dresses as it)."""
    missing = [k for k in REQUIRED if not jar.get(k)]
    if missing:
        raise ValueError("That isn't a whole Instagram sign-in (no " + ", ".join(missing) + ").")
    save_signin(aid, {"jar": jar, "ua": str(ua or "")[:400], "langs": str(langs or "")[:200], "added": int(time.time())})


def forget_signin(aid):
    (_dir(aid) / SIGNIN).unlink(missing_ok=True)


def signin_status(aid):
    """What the app may see of it: when it came, when the server last looked, and what Instagram said."""
    s = _get(aid, SIGNIN)
    return {k: s.get(k) for k in ("added", "checked", "error", "brought_at")} if s.get("jar") else None


def with_signin():
    """Accounts that pasted a sign-in, the owner first."""
    owner = accounts.owner()
    ids = [a["id"] for a in accounts.all_accounts() if (_dir(a["id"]) / SIGNIN).exists()]
    return sorted(ids, key=lambda a: a != owner)

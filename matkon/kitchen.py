"""Whose Instagram feeds the kitchen.

Everyone sees every recipe. Any account can also connect its own Instagram sign-in and pick one of
its saved collections, and the reels in it join the kitchen with that account as the one who added
them. STATE/users/<account>/cookies.txt (600) and instagram.json ({collection_id, collection_name}).

The owner's account falls back to MATKON_COOKIES and the collection in settings.json, which is how a
setup from before accounts keeps working.
"""
import json
import os
import time

from . import accounts, config, instagram


def _dir(aid):
    f = config.STATE / "users" / aid
    f.mkdir(parents=True, exist_ok=True)
    return f


def _info(aid):
    try:
        return json.loads((_dir(aid) / "instagram.json").read_text())
    except (OSError, ValueError):
        return {}


def _put(aid, info):
    p = _dir(aid) / "instagram.json"
    p.write_text(json.dumps(info))


def of(aid):
    """{"cookies": Path or None, "collection_id", "collection_name", "shared": bool, "signed_out": time or None}"""
    own = _dir(aid) / "cookies.txt"
    info = _info(aid)
    is_owner = aid == accounts.owner()
    cookies = own if own.exists() else (config.COOKIES if is_owner and config.COOKIES.exists() else None)
    st = config.settings()
    cid = info.get("collection_id") or (st.get("collection_id") if is_owner else None)
    name = info.get("collection_name") or (st.get("collection_name") if is_owner and cid == st.get("collection_id") else None)
    flag = _dir(aid) / "signed-out"
    return {"cookies": cookies, "collection_id": cid, "collection_name": name or "",
            "shared": cookies is not None and cookies == config.COOKIES and not own.exists(),
            "signed_out": int(flag.stat().st_mtime) if flag.exists() else None}


def sources():
    """Every account that has a sign-in and a collection: [(account, cookies, collection_id)]."""
    out = []
    for a in accounts.all_accounts():
        i = of(a["id"])
        if i["cookies"] and i["collection_id"]:
            out.append((a["id"], i["cookies"], str(i["collection_id"])))
    return out


def set_cookies(aid, text):
    jar = instagram.parse_cookies(text)
    if not jar.get("sessionid"):
        raise ValueError("Those cookies have no Instagram sign-in in them (no sessionid).")
    p = _dir(aid) / "cookies.txt"
    tmp = p.with_suffix(".tmp")
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        f.write(instagram.netscape(jar))
    tmp.replace(p)
    mark_signed_in(aid)
    info = _info(aid)
    info["connected"] = int(time.time())
    _put(aid, info)


def disconnect(aid):
    (_dir(aid) / "cookies.txt").unlink(missing_ok=True)
    _put(aid, {})
    mark_signed_in(aid)


def set_collection(aid, cid, name=""):
    info = _info(aid)
    info.update(collection_id=str(cid), collection_name=(name or "").strip()[:60])
    _put(aid, info)
    if aid == accounts.owner() and not (_dir(aid) / "cookies.txt").exists():
        st = config.settings()                     # the owner's collection lives in settings.json too
        st.update(collection_id=str(cid), collection_name=(name or "").strip()[:60] or "Recipes")
        config.save_settings(st)


def mark_signed_out(aid):
    (_dir(aid) / "signed-out").touch()


def mark_signed_in(aid):
    (_dir(aid) / "signed-out").unlink(missing_ok=True)


def collections_file(aid):
    return _dir(aid) / "collections.json"

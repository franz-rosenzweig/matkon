"""Accounts and signing in.

Everyone signs in: a username (or the account's email) and a password, kept as scrypt hashes in
STATE/accounts.json (600), and a signed cookie that lasts a year. The first account is the owner's
(MATKON_OWNER, "me" by default); its first password is written to STATE/initial-password.txt (600)
until it's changed. There's no open sign-up: the owner makes accounts in Settings, or invites an
email, which gets a code (mail.py) to make its own.

Codes (STATE/codes.json, 600, only their hashes): an invite lasts 7 days, a password reset or a new
email's check 15 minutes, and each takes 8 wrong tries at most.

Wrong passwords: 8 from one address in 15 minutes, or 30 from everywhere in an hour, and it waits.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time

from . import config

COOKIE = "matkon"
YEAR = 365 * 86400
TRIES, ALL_TRIES = 8, 30
USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,31}$")
_lock = threading.Lock()
_fails = {}


def _path():
    return config.STATE / "accounts.json"


def _scrypt(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)


def _read():
    try:
        return json.loads(_path().read_text())
    except (OSError, ValueError):
        return {"secret": None, "accounts": []}


def _write(d):
    config.STATE.mkdir(parents=True, exist_ok=True)
    tmp = _path().with_suffix(".tmp")
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(d, f, indent=1)
    tmp.replace(_path())


def _public(a):
    return {k: a.get(k) for k in ("id", "name", "admin", "created", "email")}


def all_accounts():
    return [_public(a) for a in _read()["accounts"]]


def get(aid):
    return next((_public(a) for a in _read()["accounts"] if a["id"] == aid), None)


def owner():
    accs = _read()["accounts"]
    return next((a["id"] for a in accs if a.get("admin")), accs[0]["id"] if accs else None)


def ensure():
    """The owner's account and the cookie secret, the first time. Writes nothing when they're there, so
    two run.py at once (a sync and a fixed recipe's refresh) don't trip over each other."""
    with _lock:
        d = _read()
        if d.get("secret") and d["accounts"]:
            return
        if not d.get("secret"):
            d["secret"] = secrets.token_hex(32)
        if not d["accounts"]:
            aid = (os.environ.get("MATKON_OWNER") or "me").strip().lower()
            pw = secrets.token_urlsafe(12)
            d["accounts"].append(_new(aid, aid.capitalize(), pw, admin=True))
            with open(os.open(config.STATE / "initial-password.txt", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
                f.write(f"{aid}\n{pw}\n")
        _write(d)


def _new(aid, name, password, admin=False):
    salt = secrets.token_bytes(16)
    return {"id": aid, "name": name or aid, "salt": salt.hex(), "hash": _scrypt(password, salt).hex(),
            "admin": admin, "created": int(time.time()), "epoch": 0}


def add(aid, name, password, admin=False, email=None):
    aid = (aid or "").strip().lower()
    email = clean_email(email) if email else None
    if not USERNAME.match(aid):
        raise ValueError("A username is 2 to 32 letters, numbers, dots, dashes or underscores.")
    if len(password or "") < 8:
        raise ValueError("A password is at least 8 characters.")
    with _lock:
        d = _read()
        if any(a["id"] == aid for a in d["accounts"]):
            raise ValueError("That username is taken.")
        if email and any(a.get("email") == email for a in d["accounts"]):
            raise ValueError("That email already has an account.")
        a = _new(aid, (name or "").strip() or aid, password, admin)
        if email:
            a["email"] = email
        d["accounts"].append(a)
        _write(d)


def remove(aid):
    with _lock:
        d = _read()
        a = next((a for a in d["accounts"] if a["id"] == aid), None)
        if not a:
            raise ValueError("No such account.")
        if a.get("admin") and sum(1 for x in d["accounts"] if x.get("admin")) == 1:
            raise ValueError("The kitchen needs its owner.")
        d["accounts"] = [x for x in d["accounts"] if x["id"] != aid]
        _write(d)


def update(aid, name=None, password=None):
    """A new name, or a new password (which signs that account out everywhere)."""
    if password is not None and len(password) < 8:
        raise ValueError("A password is at least 8 characters.")
    with _lock:
        d = _read()
        a = next((a for a in d["accounts"] if a["id"] == aid), None)
        if not a:
            raise ValueError("No such account.")
        if name is not None and name.strip():
            a["name"] = name.strip()[:60]
        if password is not None:
            salt = secrets.token_bytes(16)
            a.update(salt=salt.hex(), hash=_scrypt(password, salt).hex(), epoch=a.get("epoch", 0) + 1)
            if a.get("admin"):
                (config.STATE / "initial-password.txt").unlink(missing_ok=True)
        _write(d)


def check(aid, password):
    """The account a username (or its email) and password sign in to, or None."""
    key = (aid or "").strip().lower()
    a = next((a for a in _read()["accounts"] if a["id"] == key or (a.get("email") and a["email"] == key)), None)
    if not a:
        _scrypt(password or "", b"0" * 16)       # the same time for a name that isn't there
        return None
    ok = hmac.compare_digest(_scrypt(password or "", bytes.fromhex(a["salt"])).hex(), a["hash"])
    return a["id"] if ok else None


def cookie(aid):
    d = _read()
    a = next(a for a in d["accounts"] if a["id"] == aid)
    body = f"{aid}.{a.get('epoch', 0)}.{int(time.time()) + YEAR}"
    return body + "." + hmac.new(bytes.fromhex(d["secret"]), body.encode(), hashlib.sha256).hexdigest()


def who(value):
    """The account a cookie belongs to, or None."""
    if not value or value.count(".") < 3:
        return None
    d = _read()
    if not d.get("secret"):
        return None
    body, sig = value.rsplit(".", 1)
    good = hmac.new(bytes.fromhex(d["secret"]), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, good):
        return None
    aid, epoch, exp = body.rsplit(".", 2)
    a = next((a for a in d["accounts"] if a["id"] == aid), None)
    if not a or str(a.get("epoch", 0)) != epoch or not exp.isdigit() or int(exp) < time.time():
        return None
    return aid


def held(addr):
    now = time.time()
    for k in list(_fails):
        _fails[k] = [t for t in _fails[k] if now - t < 3600]
        if not _fails[k]:
            del _fails[k]
    return len([t for t in _fails.get(addr, []) if now - t < 900]) >= TRIES or sum(map(len, _fails.values())) >= ALL_TRIES


def failed(addr):
    _fails.setdefault(addr, []).append(time.time())


def passed(addr):
    _fails.pop(addr, None)


# ---- emails and codes ------------------------------------------------------------------------------

EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
LIFE = {"invite": 7 * 86400, "reset": 15 * 60, "email": 15 * 60}
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def clean_email(e):
    e = (e or "").strip().lower()
    if not EMAIL.match(e):
        raise ValueError("That isn't an email address.")
    return e


def by_email(email):
    e = (email or "").strip().lower()
    return next((_public(a) for a in _read()["accounts"] if a.get("email") == e), None)


def set_email(aid, email):
    email = clean_email(email)
    with _lock:
        d = _read()
        if any(a.get("email") == email and a["id"] != aid for a in d["accounts"]):
            raise ValueError("That email already has an account.")
        for a in d["accounts"]:
            if a["id"] == aid:
                a["email"] = email
        _write(d)


def _codes_path():
    return config.STATE / "codes.json"


def _codes():
    try:
        c = json.loads(_codes_path().read_text())
    except (OSError, ValueError):
        c = {}
    now = time.time()
    return {k: v for k, v in c.items() if v.get("expires", 0) > now}


def _save_codes(c):
    tmp = _codes_path().with_suffix(".tmp")
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(c, f)
    tmp.replace(_codes_path())


def _hash(code):
    secret = bytes.fromhex(_read()["secret"])
    return hmac.new(secret, re.sub(r"[^A-Z0-9]", "", code.upper()).encode(), hashlib.sha256).hexdigest()


def make_code(kind, email, **extra):
    """A new code for this kind and email (replacing an older one). Returns it, for the email."""
    email = clean_email(email)
    if kind == "invite":
        code = "".join(secrets.choice(ALPHABET) for _ in range(8))
        code = code[:4] + "-" + code[4:]
    else:
        code = f"{secrets.randbelow(10 ** 6):06d}"
    with _lock:
        c = _codes()
        c[f"{kind}:{email}"] = {"hash": _hash(code), "expires": time.time() + LIFE[kind], "tries": 0,
                                "created": int(time.time()), **extra}
        _save_codes(c)
    return code


def use_code(kind, email, code, keep=False):
    """The code's record when the code is right (and gone, unless keep), else raises ValueError."""
    try:
        email = clean_email(email)
    except ValueError:
        raise ValueError("That code doesn't match.")
    with _lock:
        c = _codes()
        rec = c.get(f"{kind}:{email}")
        if not rec or rec["tries"] >= TRIES:
            _save_codes(c)
            raise ValueError("That code doesn't match, or it has run out. Ask for a new one.")
        if not hmac.compare_digest(rec["hash"], _hash(code or "")):
            rec["tries"] += 1
            _save_codes(c)
            raise ValueError("That code doesn't match.")
        if not keep:
            del c[f"{kind}:{email}"]
        _save_codes(c)
    return rec


def drop_code(kind, email):
    with _lock:
        c = _codes()
        c.pop(f"{kind}:{email.strip().lower()}", None)
        _save_codes(c)


def invites():
    return sorted(({"email": k.split(":", 1)[1], "name": v.get("name", ""), "created": v.get("created"), "expires": int(v["expires"])}
                   for k, v in _codes().items() if k.startswith("invite:")), key=lambda x: -(x["created"] or 0))


def recent_code(kind, email, within=60):
    """Whether a code of this kind went to this email in the last minute (so a button can't spam a mailbox)."""
    rec = _codes().get(f"{kind}:{(email or '').strip().lower()}")
    return bool(rec and time.time() - rec.get("created", 0) < within)

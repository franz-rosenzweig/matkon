"""matkon: saved recipe reels → recipe pages.

  python3 run.py collections                 your saved collections, to find the recipes one
  python3 run.py collection ID [NAME]        read that one
  python3 run.py sync [--full] [--limit N]   read the collection, work through new reels
  python3 run.py add URL|CODE                one reel, even one outside the collection
  python3 run.py redo CODE [--from STAGE]    again from: video, transcript, frames, link, recipe, note, translate
  python3 run.py status                      what's where
  python3 run.py password [ACCOUNT]          a new password (the owner's by default)
  python3 run.py serve                       the app (server.py)

Each reel goes through the stages in order (post → video → transcript → frames → link → recipe →
note → translate), and each stage leaves its file in reels/<code>/, so a run picks up where the last one stopped.
"""
import argparse
import collections
import fcntl
import json
import random
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

from . import accounts, config, instagram, kitchen, linked, memory, reel, recipe, translate, vault

STAGES = ["video", "transcript", "frames", "link", "recipe", "note", "translate"]
FILES = {"video": "video.mp4", "transcript": "transcript.json", "frames": "sheets.json", "link": "linked.json", "recipe": "recipe.json", "note": "note.json", "translate": "translated.json"}
MAX_TRIES = 3


def say(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _read(p, default=None):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default


def _write(p, data):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    tmp.replace(p)


def folder(code):
    f = config.REELS / code
    f.mkdir(parents=True, exist_ok=True)
    return f


def status_of(f):
    return _read(f / "status.json", {"error": None, "tries": 0})


def set_status(f, **kw):
    s = status_of(f)
    s.update(kw, updated=int(time.time()))
    _write(f / "status.json", s)


def notify(title, msg, level=None):
    """MATKON_NOTIFY title message [now], when there is one. True when it was delivered."""
    if not config.NOTIFY:
        return False
    try:
        r = subprocess.run(shlex.split(config.NOTIFY) + [title, msg] + ([level] if level else []),
                           capture_output=True, text=True, timeout=120)
    except OSError:
        return False
    return r.returncode == 0


def keep_post(p, rank=None, by=None):
    """Saves what the listing said about a reel; new ones are marked with when they were found, and
    who added them (the first account whose collection had it)."""
    f = folder(p["code"])
    old = _read(f / "post.json", {})
    p = {**old, **p}
    p.setdefault("found", time.time() - (rank or 0))
    if by and not p.get("added_by"):
        p["added_by"] = by
    _write(f / "post.json", p)
    if p.get("cover_url") and not (f / "cover.jpg").exists():
        try:
            instagram.download_cover(p["cover_url"], f / "cover.jpg")
        except Exception as e:  # noqa: BLE001 - the cover is only a fallback picture
            say(p["code"], "no cover:", e)
    return not old


# ---- the stages --------------------------------------------------------------------------------

def stage_video(f, post):
    if post.get("media_type") not in (2, None):
        raise RuntimeError("not a video post")
    who = post.get("added_by") or accounts.owner()
    cookies = kitchen.of(who)["cookies"] if who else None
    instagram.download_video(post["code"], f / "video.mp4", cookies or kitchen.of(accounts.owner())["cookies"])
    time.sleep(2 + random.random() * 3)


def stage_transcript(f, post):
    _write(f / "transcript.json", reel.transcript(f / "video.mp4"))


def stage_frames(f, post):
    reel.sheets(f / "video.mp4", f)


def stage_link(f, post):
    url = linked.link_in(post.get("caption"))
    _write(f / "linked.json", linked.fetch(url, post.get("caption")) if url else {"url": None})


def stage_recipe(f, post):
    sheets = _read(f / "sheets.json", [])
    lk = _read(f / "linked.json", {})
    msg = recipe.build_message(post, _read(f / "transcript.json", {}), sheets, f, linked.as_prompt(lk) if lk.get("url") else "(none)")
    model = config.model()
    answer = recipe.ask_claude(msg, model)
    (f / "answer.txt").write_text(answer)            # Claude's own words, for when a recipe looks wrong
    r = recipe.parse(answer)
    r["made"] = int(time.time())
    if lk.get("url") and lk.get("kind") != "error":
        r["link"] = lk.get("final") or lk["url"]
    r["model"] = model
    if r["photo_at"] is not None and reel.photo(f / "video.mp4", r["photo_at"], f / "photo.jpg"):
        r["photo"] = "photo.jpg"
    elif (f / "cover.jpg").exists():
        (f / "photo.jpg").unlink(missing_ok=True)
        r["photo"] = "cover.jpg"
    _write(f / "recipe.json", r)


def stage_note(f, post, notes):
    r = _read(f / "recipe.json")
    if not r or not r.get("is_recipe") or not config.VAULT:
        _write(f / "note.json", {"path": None, "skipped": "not a recipe" if config.VAULT else "no vault"})
        return
    path = vault.write(f, r, post, notes)
    say(post["code"], "note:", path.relative_to(config.VAULT) if path else "left alone (edited in Obsidian)")
    _write(f / "note.json", {"path": str(path) if path else None, "at": int(time.time())})


def stage_translate(f, post):
    """Hebrew recipes get an English version (recipe.en.json); the others only the marker."""
    r = _read(f / "recipe.json", {})
    done = {}
    if r.get("is_recipe") and r.get("lang") == "he":
        _write(f / "recipe.en.json", translate.to_english(r, config.model()))
        done["en"] = True
    _write(f / "translated.json", done)


RUN = {"video": stage_video, "transcript": stage_transcript, "frames": stage_frames, "link": stage_link, "recipe": stage_recipe,
       "translate": stage_translate}


def work(code, notes, force_from=None):
    """Runs a reel's remaining stages. Returns True when it reached the end."""
    f = folder(code)
    post = _read(f / "post.json")
    if not post:
        return False
    if force_from:
        for s in STAGES[STAGES.index(force_from):]:
            if s == "translate":
                (f / "recipe.en.json").unlink(missing_ok=True)
            if s != "video":
                (f / FILES[s]).unlink(missing_ok=True)
            elif (f / "video.mp4").exists():
                (f / "video.mp4").unlink()
        set_status(f, error=None, tries=0)
    for s in STAGES:
        if (f / FILES[s]).exists():
            continue
        say(code, s, "…")
        try:
            if s == "note":
                stage_note(f, post, notes)
            else:
                RUN[s](f, post)
        except instagram.SignedOut:
            raise
        except Exception as e:  # noqa: BLE001 - one reel's trouble shouldn't stop the others
            st = status_of(f)
            set_status(f, error=f"{s}: {e}", tries=st.get("tries", 0) + 1, stage=s)
            say(code, s, "failed:", e)
            return False
    set_status(f, error=None, tries=0, stage="done")
    return True


def pending():
    """Reels not finished yet and not given up on, oldest found first."""
    out = []
    for f in config.REELS.iterdir() if config.REELS.exists() else []:
        if not (f / "post.json").exists() or all((f / FILES[s]).exists() for s in STAGES):
            continue
        st = status_of(f)
        if st.get("tries", 0) >= MAX_TRIES:
            continue
        out.append((_read(f / "post.json", {}).get("found", 0), f.name))
    return [c for _, c in sorted(out)]


# ---- commands ----------------------------------------------------------------------------------

def signed_out(e, aid=None):
    """Instagram turned an account's sign-in away. The owner hears about it once (MATKON_NOTIFY);
    everyone sees it in Settings and on the home page."""
    aid = aid or accounts.owner()
    say(f"Instagram sign-in lapsed ({aid}):", e)
    if aid and not kitchen.of(aid)["signed_out"]:
        kitchen.mark_signed_out(aid)
        if aid == accounts.owner():
            notify("Matkon", "Instagram turned away the sign-in, so new recipe reels wait. " + config.SIGNIN_HELP, "now")
    return 0


def cmd_sync(a):
    st = config.settings()
    sources = kitchen.sources()
    if not sources:
        say("No collection to read: connect Instagram and pick a collection in Settings, or: python3 run.py collection ID")
        return 2
    # Once a week, every saved post: a reel saved long ago and only now put in the collection keeps its
    # old place among the saves, deeper than the newest few pages.
    last_full = config.STATE / "last-full"
    full = a.full or (st.get("full_every_hours") and
                      (not last_full.exists() or time.time() - last_full.stat().st_mtime > st["full_every_hours"] * 3600))
    pages = 5000 if full else st["scan_pages"]       # "every": until Instagram says there's no more
    found, lapsed = [], []
    for aid, cookies, cid in sources:
        new = 0
        try:
            for rank, m in enumerate(instagram.saved_posts(pages, cookies)):
                if cid in instagram.collections_of(m):
                    p = instagram.post(m)
                    if p.get("code") and keep_post(p, rank, by=aid):
                        new += 1
                        found.append({"code": p["code"], "by": aid})
                        say(p["code"], f"new from {aid}, by @" + p["user"])
            kitchen.mark_signed_in(aid)
        except instagram.SignedOut as e:
            signed_out(e, aid)
            lapsed.append(aid)
        say(f"{aid}: {new} new" + (" (looked through every saved post)" if full else ""))
    if full and len(lapsed) < len(sources):
        last_full.touch()
    notes = (vault.find_notes() if config.VAULT else {})
    done, failed = [], []
    try:
        for code in pending()[: (a.limit or st["per_run"])]:
            if work(code, notes):
                r = _read(config.REELS / code / "recipe.json", {})
                if r.get("is_recipe"):
                    done.append({"code": code, "title": r["title"]})
            else:
                failed.append({"code": code, "error": (status_of(config.REELS / code).get("error") or "")[:200]})
    except instagram.SignedOut as e:
        signed_out(e)
        lapsed.append(accounts.owner())
    if found or done or failed or lapsed:
        memory.log_run({"kind": "sync", "full": bool(full), "found": found, "made": done, "failed": failed, "signed_out": lapsed})
    if done and not a.quiet:
        notify("Matkon", "New recipes: " + "; ".join(d["title"] for d in done) + f". {st['app_url']}")
    return 0


def _code(s):
    m = re.search(r"instagram\.com/(?:[\w.]+/)?(?:reels?|p|tv)/([\w-]+)", s)
    return m.group(1) if m else s.strip().strip("/")


def queue_add(a):
    """Puts the reel in the kitchen's queue before anything else, so if another run holds the lock, that
    run (or the next one) makes it."""
    code = _code(a.what)
    if not memory.CODE.match(code):
        say("That isn't a reel link.")
        return None
    f = folder(code)
    if not (f / "post.json").exists():
        keep_post({"code": code, "user": "", "caption": "", "media_type": None,
                   "url": f"https://www.instagram.com/reel/{code}/"}, by=a.by or accounts.owner())
    return code


def cmd_add(a):
    code = _code(a.what)
    f = folder(code)
    try:
        ok = work(code, (vault.find_notes() if config.VAULT else {}))
    except instagram.SignedOut as e:
        return signed_out(e, a.by)
    r = _read(f / "recipe.json", {})
    memory.log_run({"kind": "add", "by": a.by or accounts.owner(), "made": [{"code": code, "title": r.get("title", "")}] if ok else [],
                    "failed": [] if ok else [{"code": code, "error": (status_of(f).get("error") or "")[:200]}]})
    return 0 if ok else 1


def cmd_redo(a):
    code = _code(a.code)
    if not (config.REELS / code / "post.json").exists():
        say("No reel", code)
        return 1
    try:
        return 0 if work(code, (vault.find_notes() if config.VAULT else {}), force_from=a.stage) else 1
    except instagram.SignedOut as e:
        return signed_out(e)


def cmd_status(a):
    st = config.settings()
    print("collection:", st.get("collection_id"), st.get("collection_name"))
    rows = []
    for f in sorted(config.REELS.iterdir()) if config.REELS.exists() else []:
        p = _read(f / "post.json", {})
        r = _read(f / "recipe.json", {})
        s = status_of(f)
        stage = next((x for x in STAGES if not (f / FILES[x]).exists()), "done")
        rows.append((p.get("found", 0), f.name, stage, r.get("title", ""), "" if r.get("complete", True) else "incomplete",
                     s.get("error") or ""))
    for _, code, stage, title, inc, err in sorted(rows, reverse=True):
        print(f"{code:13} {stage:10} {title[:40]:40} {inc:10} {err[:60]}")
    print(len(rows), "reels")


def cmd_collections(a):
    """Your saved collections, by Instagram's id for them, with a few captions from each, so you can
    tell which one is the recipes. (Instagram's web app doesn't give their names anymore.)"""
    seen, count = collections.defaultdict(list), collections.Counter()
    cookies = kitchen.of(a.account)["cookies"] if a.account else None
    try:
        for m in instagram.saved_posts(a.pages, cookies):
            cap = re.sub(r"\s+", " ", ((m.get("caption") or {}).get("text") or "")).strip()
            for c in instagram.collections_of(m) or ["(in no collection)"]:
                count[c] += 1
                if len(seen[c]) < 3 and cap:
                    seen[c].append(cap[:80])
    except instagram.SignedOut as e:
        print("Instagram sign-in lapsed:", e)
        if a.out:
            Path(a.out).write_text(json.dumps({"error": "signed out", "at": int(time.time())}))
        return 1
    if a.out:                                      # for the Settings page
        Path(a.out).write_text(json.dumps({"at": int(time.time()), "collections": [
            {"id": c, "count": n, "captions": seen[c]} for c, n in count.most_common() if c != "(in no collection)"]}))
        return 0
    for c, n in count.most_common():
        print(f"{c}  ({n} saved)")
        for cap in seen[c]:
            print("    " + cap)
    print("\nThen: python3 run.py collection <id> Recipes")
    return 0


def cmd_password(a):
    """A new password for an account (the owner's by default), typed twice."""
    import getpass
    aid = a.account or accounts.owner()
    pw = getpass.getpass(f"New password for {aid}: ")
    if pw != getpass.getpass("Again: "):
        print("They don't match.")
        return 1
    accounts.update(aid, password=pw)
    print(f"Done. {aid} is signed out everywhere until they sign in with it.")
    return 0


def cmd_collection(a):
    st = config.settings()
    st["collection_id"] = a.id
    if a.name:
        st["collection_name"] = " ".join(a.name)
    config.save_settings(st)
    print("collection:", st["collection_id"], st["collection_name"])


def main():
    ap = argparse.ArgumentParser(prog="matkon")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync"); s.add_argument("--full", action="store_true"); s.add_argument("--limit", type=int)
    s.add_argument("--quiet", action="store_true", help="no message about new recipes")
    s = sub.add_parser("add"); s.add_argument("what"); s.add_argument("--by", help="the account adding it")
    s = sub.add_parser("redo"); s.add_argument("code"); s.add_argument("--from", dest="stage", choices=STAGES, default="recipe")
    sub.add_parser("status")
    s = sub.add_parser("collections"); s.add_argument("--pages", type=int, default=5000)
    s.add_argument("--account"); s.add_argument("--out", help="write the list as JSON here")
    s = sub.add_parser("password"); s.add_argument("account", nargs="?")
    s = sub.add_parser("collection"); s.add_argument("id"); s.add_argument("name", nargs="*")
    sub.add_parser("serve")
    sub.add_parser("pause", help="stop asking Instagram for anything until resume")
    sub.add_parser("resume")
    a = ap.parse_args()
    config.STATE.mkdir(parents=True, exist_ok=True)
    accounts.ensure()
    if a.cmd == "password":
        return cmd_password(a)
    if a.cmd == "serve":
        from . import server
        return server.main()
    if a.cmd == "status":
        return cmd_status(a)
    if a.cmd == "collection":
        return cmd_collection(a)
    if a.cmd in ("pause", "resume"):
        config.PAUSED.unlink(missing_ok=True) if a.cmd == "resume" else config.PAUSED.write_text(time.strftime("%Y-%m-%d %H:%M\n"))
        say("Paused: nothing asks Instagram for anything until: python3 run.py resume" if a.cmd == "pause" else "Instagram checks are back on.")
        return 0
    if a.cmd in ("sync", "add", "collections") and config.paused():
        if a.cmd == "add":
            queue_add(a)
        say("Paused, so Instagram wasn't asked." + (" The reel waits in the queue." if a.cmd == "add" else ""))
        return 0
    if a.cmd == "collections":
        return cmd_collections(a)
    config.STATE.mkdir(parents=True, exist_ok=True)
    config.REELS.mkdir(exist_ok=True)
    if a.cmd == "add" and not queue_add(a):
        return 1
    lock = open(config.STATE / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        say("Another run is going; this one stops." + (" The reel waits in the queue for it." if a.cmd == "add" else ""))
        return 0
    return {"sync": cmd_sync, "add": cmd_add, "redo": cmd_redo}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main() or 0)

"""matkon: saved recipe reels → recipe pages.

  python3 run.py sync [--limit N]            work through the reels the browser brought in, and the pages and photos
                                             added (and look at Instagram first, for accounts that pasted a sign-in,
                                             unless --no-instagram)
  python3 run.py instagram                   just that look, when it's time (igserver.py; needs curl_cffi)
  python3 run.py add URL|CODE                one reel, even one outside the collection: it waits for the browser;
                                             or a recipe page's link (sources.py), read at the next sync
  python3 run.py redo CODE [--from STAGE]    again from: transcript, frames, link, recipe, note, translate (video: the browser brings it again)
  python3 run.py edited CODE                 after a recipe was fixed by hand in the app: its note, English copy and
                                             Cookbook copy again (the server starts it)
  python3 run.py collection ID [NAME]        the owner's collection (the extension sets it too)
  python3 run.py cookbook                    a copy of what changed in Nextcloud Cookbook (sync does it too)
  python3 run.py status                      what's where
  python3 run.py password [ACCOUNT]          a new password (the owner's by default)
  python3 run.py pause | resume              the browser extension leaves Instagram alone, or not
  python3 run.py serve                       the app (server.py)

The browser extension sends each reel's post and video (see server.py, /api/ext), or, for an account
that pasted its Instagram sign-in into Settings, the server looks itself (igserver.py, gently, from
`sync`). The stages take it from there, in order (video → transcript → frames → link →
recipe → note → translate), each leaving its file in reels/<code>/, so a run picks up where the last one
stopped. A recipe page or photos of a recipe (sources.py) take the same road without the video's stages.
"""
import argparse
import fcntl
import re
import shlex
import subprocess
import sys
import time

from . import accounts, config, cookbook, edits, instagram, kitchen, linked, memory, reel, recipe, sources, store, translate, vault
from .store import FILES, STAGES, folder, pending, queue, read as _read, set_status, status_of, write as _write


class Waiting(Exception):
    """The reel's video isn't in yet: the browser brings it."""


def say(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


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


# ---- the stages --------------------------------------------------------------------------------

def stage_video(f, post):
    if post.get("media_type") not in (2, None):
        raise RuntimeError("not a video post")
    raise Waiting()                                  # the browser extension brings it (server.py, /api/ext)


def stage_transcript(f, post):
    _write(f / "transcript.json", reel.transcript(f / "video.mp4"))


def stage_frames(f, post):
    reel.sheets(f / "video.mp4", f)


def stage_link(f, post):
    if store.source(post) == "web":
        return sources.stage_page(f, post)             # the page itself, by its link
    url = linked.link_in(post.get("caption"))
    _write(f / "linked.json", linked.fetch(url, post.get("caption")) if url else {"url": None})


def stage_recipe(f, post):
    if store.source(post) != "reel":
        return sources.stage_recipe(f, post)
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
    elif reel.photo(f / "video.mp4", reel.duration(f / "video.mp4") * 0.6, f / "photo.jpg"):
        r["photo"] = "photo.jpg"                      # no moment picked: one from near the end, where the dish is
    _write(f / "recipe.json", r)


def stage_note(f, post, notes):
    r = edits.effective(f)                           # a recipe fixed by hand in the app: the fixed one
    if not r or not r.get("is_recipe") or not config.VAULT:
        _write(f / "note.json", {"path": None, "skipped": "not a recipe" if config.VAULT else "no vault"})
        return
    path = vault.write(f, r, post, notes)
    say(post["code"], "note:", path.relative_to(config.VAULT) if path else "left alone (edited in Obsidian)")
    _write(f / "note.json", {"path": str(path) if path else None, "at": int(time.time())})


def stage_translate(f, post):
    """Hebrew recipes get an English version (recipe.en.json); the others only the marker."""
    r = edits.effective(f) or {}
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
    todo = store.stages(post)
    if force_from:
        for s in [s for s in todo if STAGES.index(s) >= STAGES.index(force_from)]:
            if s == "translate":
                (f / "recipe.en.json").unlink(missing_ok=True)
            (f / FILES[s]).unlink(missing_ok=True)       # "video": the browser brings it again
        set_status(f, error=None, tries=0)
    for s in todo:
        if (f / FILES[s]).exists():
            continue
        say(code, s, "…")
        try:
            if s == "note":
                stage_note(f, post, notes)
            else:
                RUN[s](f, post)
        except Waiting:
            set_status(f, stage="waiting")
            say(code, "waits for the browser to bring its video")
            return False
        except Exception as e:  # noqa: BLE001 - one reel's trouble shouldn't stop the others
            st = status_of(f)
            set_status(f, error=f"{s}: {e}", tries=st.get("tries", 0) + 1, stage=s)
            say(code, s, "failed:", e)
            return False
    set_status(f, error=None, tries=0, stage="done")
    return True


# ---- commands ----------------------------------------------------------------------------------

def _instagram():
    """The server's own look, for accounts that pasted a sign-in: in IG_PY, the Python with curl_cffi."""
    if not kitchen.with_signin() or config.paused():
        return
    try:
        subprocess.run([config.IG_PY, "-I", str(config.ROOT / "run.py"), "instagram"], timeout=3600, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        say("instagram:", e)


def cmd_instagram(a):
    try:
        import curl_cffi  # noqa: F401 - only to know it's there
    except ImportError:
        say("The server's look at Instagram needs curl_cffi: set MATKON_IG_PY to a Python that has it.")
        return 1
    if config.paused():
        say("Paused: Matkon leaves Instagram alone.")
        return 0
    lock = open(config.STATE / ".ig-lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    from . import igserver
    igserver.run_all(say)
    return 0


def cmd_sync(a):
    """Works through the reels the browser brought in (new ones that come in meanwhile too)."""
    if not a.no_instagram:
        _instagram()
    st = config.settings()
    notes = (vault.find_notes() if config.VAULT else {})
    done, failed, tried = [], [], set()
    left = a.limit or st["per_run"]
    while left > 0:
        todo = [c for c in pending() if c not in tried][:left]
        if not todo:
            break
        for code in todo:
            tried.add(code)
            left -= 1
            if work(code, notes):
                r = _read(config.REELS / code / "recipe.json", {})
                if r.get("is_recipe"):
                    done.append({"code": code, "title": r["title"]})
            else:
                failed.append({"code": code, "error": (status_of(config.REELS / code).get("error") or "")[:200]})
    found = [{"code": c, "by": (_read(config.REELS / c / "post.json", {}).get("added_by") or accounts.owner())} for c in sorted(tried)]
    if done or failed:
        memory.log_run({"kind": "sync", "found": found, "made": done, "failed": failed})
    if done and not a.quiet:
        notify("Matkon", "New recipes: " + "; ".join(d["title"] for d in done) + f". {st['app_url']}")
    cookbook.catch_up(say)
    return 0


def cmd_cookbook(a):
    if not cookbook.enabled():
        say("No Cookbook: set MATKON_COOKBOOK and MATKON_COOKBOOK_LOGIN.")
        return 1
    say(cookbook.catch_up(say), "sent to Cookbook")
    return 0


def cmd_add(a):
    code = queue(a.what, a.by or accounts.owner())
    if not code and not sources.is_reel_link(a.what):
        try:
            d = sources.add_link(a.what, a.by or accounts.owner())
        except ValueError as e:
            say(e)
            return 1
        say(d["code"], "is already made." if d["done"] else "is in the queue: the next sync reads it.")
        return 0
    if not code:
        say("That isn't a reel link.")
        return 1
    say(code, "is in the queue." + ("" if (config.REELS / code / "video.mp4").exists() else
                                     " The browser extension brings it the next time you're on Instagram."))
    return 0


def cmd_redo(a):
    code = instagram.code_in(a.code)
    if not (config.REELS / code / "post.json").exists():
        say("No reel", code)
        return 1
    ok = work(code, (vault.find_notes() if config.VAULT else {}), force_from=a.stage)
    cookbook.catch_up(say)
    return 0 if ok else 1


def cmd_edited(a):
    """After a recipe was fixed by hand in the app (edits.py, server.py starts this): its note and its
    Cookbook copy again, the way a redo makes them, and a new English copy of a Hebrew recipe whose
    Hebrew changed, unless the English was fixed by hand too. It waits for a run that's going, and
    steps aside when a newer edit came in meanwhile (that one has its own)."""
    f = config.REELS / a.code
    if a.stamp and a.stamp != edits.stamp(f):
        return 0                                     # a newer edit came in already
    lock = open(config.STATE / ".lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    if a.stamp and a.stamp != edits.stamp(f):
        return 0
    post, r = _read(f / "post.json"), edits.effective(f)
    if not post or not r:
        return 1
    if (f / "note.json").exists():                   # once the reel got that far; else its run writes it
        stage_note(f, post, vault.find_notes() if config.VAULT else {})
    en = f / "recipe.en.json"
    if (r.get("is_recipe") and r.get("lang") == "he" and not edits.load(f, "en") and (en.exists() or (f / "translated.json").exists())
            and (_read(en, {}) or {}).get("source") != translate.fingerprint(r)):
        say(a.code, "translate …")
        try:
            _write(en, translate.to_english(r, config.model()))
        except Exception as e:  # noqa: BLE001 - the English copy it had stays
            say(a.code, "translate failed:", e)
    cookbook.catch_up(say)
    return 0


def cmd_status(a):
    st = config.settings()
    print("collection:", st.get("collection_id"), st.get("collection_name"))
    rows = []
    for f in sorted(config.REELS.iterdir()) if config.REELS.exists() else []:
        p = _read(f / "post.json", {})
        r = _read(f / "recipe.json", {})
        s = status_of(f)
        stage = next((x for x in store.stages(p) if not (f / FILES[x]).exists()), "done")
        rows.append((p.get("found", 0), f.name, stage, r.get("title", ""), "" if r.get("complete", True) else "incomplete",
                     s.get("error") or ""))
    for _, code, stage, title, inc, err in sorted(rows, reverse=True):
        print(f"{code:13} {stage:10} {title[:40]:40} {inc:10} {err[:60]}")
    print(len(rows), "reels")
    if cookbook.enabled():
        print(len(_read(cookbook.SENT, {}) or {}), "in Cookbook")


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
    s = sub.add_parser("sync"); s.add_argument("--limit", type=int)
    s.add_argument("--quiet", action="store_true", help="no message about new recipes")
    s.add_argument("--no-instagram", action="store_true", help="no look at Instagram first (a page or photos were added)")
    s = sub.add_parser("add"); s.add_argument("what"); s.add_argument("--by", help="the account adding it")
    s = sub.add_parser("redo"); s.add_argument("code"); s.add_argument("--from", dest="stage", choices=STAGES, default="recipe")
    sub.add_parser("status")
    s = sub.add_parser("edited", help="after a recipe was fixed by hand: its note, English copy and Cookbook copy")
    s.add_argument("code", type=lambda c: c if re.match(r"^[\w-]{5,40}$", c) else ap.error("bad code"))
    s.add_argument("stamp", nargs="?", help="edits.stamp() when it was started")
    sub.add_parser("cookbook", help="a copy of what changed in Nextcloud Cookbook")
    sub.add_parser("instagram", help="the server's own look at Instagram, for accounts that pasted a sign-in")
    s = sub.add_parser("password"); s.add_argument("account", nargs="?")
    s = sub.add_parser("collection"); s.add_argument("id"); s.add_argument("name", nargs="*")
    sub.add_parser("serve")
    sub.add_parser("pause", help="the browser extension leaves Instagram alone until resume")
    sub.add_parser("resume")
    a = ap.parse_args()
    config.STATE.mkdir(parents=True, exist_ok=True)
    config.REELS.mkdir(exist_ok=True)
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
        say("Paused: the browser extension leaves Instagram alone until: python3 run.py resume" if a.cmd == "pause"
            else "The browser extension checks Instagram again.")
        return 0
    if a.cmd == "add":
        return cmd_add(a)
    if a.cmd == "instagram":
        return cmd_instagram(a)
    if a.cmd == "edited":
        return cmd_edited(a)                         # it waits for the lock rather than stop
    lock = open(config.STATE / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        say("Another run is going; this one stops.")
        return 0
    return {"sync": cmd_sync, "redo": cmd_redo, "cookbook": cmd_cookbook}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main() or 0)

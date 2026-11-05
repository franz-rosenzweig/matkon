"""matkon: saved recipe reels → recipe pages.

  python3 run.py sync [--limit N]            work through the reels the browser brought in
  python3 run.py add URL|CODE                one reel, even one outside the collection: it waits for the browser
  python3 run.py redo CODE [--from STAGE]    again from: transcript, frames, link, recipe, note, translate (video: the browser brings it again)
  python3 run.py collection ID [NAME]        the owner's collection (the extension sets it too)
  python3 run.py status                      what's where
  python3 run.py password [ACCOUNT]          a new password (the owner's by default)
  python3 run.py pause | resume              the browser extension leaves Instagram alone, or not
  python3 run.py serve                       the app (server.py)

Matkon never talks to Instagram itself. The browser extension sends each reel's post and video (see
server.py, /api/ext), and the stages take it from there, in order (video → transcript → frames → link →
recipe → note → translate), each leaving its file in reels/<code>/, so a run picks up where the last one
stopped.
"""
import argparse
import fcntl
import shlex
import subprocess
import sys
import time

from . import accounts, config, instagram, linked, memory, reel, recipe, translate, vault
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
    elif reel.photo(f / "video.mp4", reel.duration(f / "video.mp4") * 0.6, f / "photo.jpg"):
        r["photo"] = "photo.jpg"                      # no moment picked: one from near the end, where the dish is
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
            (f / FILES[s]).unlink(missing_ok=True)       # "video": the browser brings it again
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

def cmd_sync(a):
    """Works through the reels the browser brought in (new ones that come in meanwhile too)."""
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
    return 0


def cmd_add(a):
    code = queue(a.what, a.by or accounts.owner())
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
    return 0 if work(code, (vault.find_notes() if config.VAULT else {}), force_from=a.stage) else 1


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
    s = sub.add_parser("add"); s.add_argument("what"); s.add_argument("--by", help="the account adding it")
    s = sub.add_parser("redo"); s.add_argument("code"); s.add_argument("--from", dest="stage", choices=STAGES, default="recipe")
    sub.add_parser("status")
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
    lock = open(config.STATE / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        say("Another run is going; this one stops.")
        return 0
    return {"sync": cmd_sync, "redo": cmd_redo}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main() or 0)

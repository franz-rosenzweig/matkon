#!/usr/bin/env python3
"""The app's API for collections, the pantry, aisles, the cooking log, units, households, fixing a
recipe, asking about one, sharing one by link, the export and the search text: against the demo's
made-up recipes (tools/demo.py) in a throwaway state, with a pretend `claude` first on the PATH. Nothing
here touches a real Matkon or asks the real Claude.

  python3 -I tools/test_api.py          (needs ffmpeg, for the demo's photos)
"""
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILS = []


def ok(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what, flush=True)
    if not cond:
        FAILS.append(what)


TMP = Path(tempfile.mkdtemp(prefix="matkon-api-test-"))
STATE, VAULT, BIN, LOG = TMP / "kitchen", TMP / "vault", TMP / "bin", TMP / "claude.jsonl"
PORT = 8574
M = f"http://127.0.0.1:{PORT}"

# a pretend Claude: a translation gives the recipe back as it came, a reel gets a made-up recipe, a
# question gets "Fake answer: <question>" (slowly when it says SLOW). Every call is written to LOG.
FAKE = r'''#!/usr/bin/env python3
import json, os, sys, time
msg = json.loads(sys.stdin.read().splitlines()[0])
text = "\n".join(c.get("text", "") for c in msg["message"]["content"] if c.get("type") == "text")
with open(os.environ["FAKE_CLAUDE_LOG"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "text": text}) + "\n")
if "Translate this recipe" in text:
    out = text.split("Recipe:\n", 1)[1]
elif "You turn a saved Instagram cooking reel" in text:
    out = json.dumps({"is_recipe": True, "lang": "en", "title": "Redone by Claude", "summary": "Again.", "kind": "Snacks",
                      "ingredient_groups": [{"name": "", "items": [{"amount": "", "item": "chickpeas", "note": ""}]}],
                      "steps": [{"text": "Blend.", "timers": []}], "complete": False, "missing": ["how much"], "photo_at": 1.0})
else:
    q = text.rsplit("The question:\n<<<\n", 1)[1].split("\n>>>", 1)[0]
    if "SLOW" in q:
        time.sleep(10)
    out = "Fake answer: " + q
print(json.dumps({"type": "result", "is_error": False, "result": out}))
'''
BIN.mkdir(parents=True)
VAULT.mkdir()
(BIN / "claude").write_text(FAKE)
(BIN / "claude").chmod(0o755)
ENV = TMP / "test.env"
ENV.write_text("\n".join([f"MATKON_STATE={STATE}", f"MATKON_SETTINGS={STATE}/settings.json", "MATKON_OWNER=sam",
                          "MATKON_HOSTS=127.0.0.1", f"MATKON_PORT={PORT}", f"MATKON_VAULT={VAULT}", "MATKON_NOTIFY=",
                          "MATKON_PY=/bin/false", "MATKON_ASK_TIMEOUT=3", "MATKON_COOKBOOK=", "MATKON_MODEL="]) + "\n")
for k in ("MATKON_DEMO_ACCOUNT", "MATKON_MODEL_FROM", "MATKON_MODEL", "MATKON_DEMO_PASSWORD"):
    os.environ.pop(k, None)
os.environ.update(MATKON_ENV=str(ENV), FAKE_CLAUDE_LOG=str(LOG), PATH=f"{BIN}:{os.environ.get('PATH', '/usr/bin:/bin')}")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import demo  # noqa: E402
from matkon import accounts, config, cookbook, edits, memory  # noqa: E402

assert config.STATE == STATE, "the test must never see a real state"

# ---- setup: the demo's ten recipes and its two accounts (Sam, the owner, and Alex), and three more ----
demo.build(STATE)
demo.remembered(STATE)
PW = {"sam": "sam-test-password", "alex": "alex-test-password"}
accounts.update("sam", password=PW["sam"])
accounts.update("alex", password=PW["alex"])
for x in ("carol", "dana", "erin"):
    PW[x] = f"{x}-test-password"
    accounts.add(x, x.capitalize(), PW[x])
for code in ("demo-hummus", "demo-shakshuka"):      # as if the reel had been through every stage
    f = STATE / "reels" / code
    (f / "transcript.json").write_text('{"language": "en", "segments": []}')
    (f / "sheets.json").write_text("[]")
    (f / "linked.json").write_text('{"url": null}')


def run(*args):
    return subprocess.run([sys.executable, "-I", str(ROOT / "run.py"), *args], capture_output=True, text=True, timeout=120)


def jobs():
    """This test's own background refreshes (run.py edited), by their environment."""
    out = []
    for p in Path("/proc").iterdir():
        try:
            cmd = (p / "cmdline").read_bytes().split(b"\0") if p.name.isdigit() else []
            if b"edited" in cmd and any(c.endswith(b"run.py") for c in cmd) and str(ENV).encode() in (p / "environ").read_bytes():
                out.append(p.name)
        except OSError:
            pass
    return out


def wait_for_runs(seconds=60):
    """Until no refresh is waiting or going and nothing holds the kitchen's lock."""
    end = time.time() + seconds
    while time.time() < end:
        if not jobs():
            with open(STATE / ".lock", "w") as lk:
                try:
                    fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return True
                except BlockingIOError:
                    pass
        time.sleep(0.2)
    return False


def until(cond, seconds=30):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.2)
    return False


def calls(kind):
    try:
        return [json.loads(x) for x in LOG.read_text().splitlines() if kind in json.loads(x)["text"]]
    except OSError:
        return []


r1, r2 = run("redo", "demo-hummus", "--from", "note"), run("redo", "demo-shakshuka", "--from", "note")
ok(r1.returncode == 0 and r2.returncode == 0, "setup: the two reels' notes (and the Hebrew one's English copy) are made")
NOTE = lambda code: Path(json.loads((STATE / "reels" / code / "vault-note.json").read_text())["path"])  # noqa: E731
ok(NOTE("demo-hummus").exists() and "Silky Hummus" in NOTE("demo-hummus").read_text(), "setup: the hummus note is in the vault")


class Client:
    def __init__(self, user=None):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        if user:
            st, _, _ = self.call("/api/signin", {"username": user, "password": PW[user]})
            assert st == 200, f"{user} can't sign in"

    def call(self, path, body=None, headers=None):
        req = urllib.request.Request(M + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", "X-Matkon": "1", **(headers or {})})
        try:
            with self.opener.open(req, timeout=30) as r:
                raw, st, h = r.read(), r.status, r.headers
        except urllib.error.HTTPError as e:
            raw, st, h = e.read(), e.code, e.headers
        try:
            return st, json.loads(raw), h
        except ValueError:
            return st, raw, h

    def me(self, op, **kw):
        return self.call("/api/me", {"op": op, **kw})

    def settings(self, op, **kw):
        return self.call("/api/settings", {"op": op, **kw})


import socket  # noqa: E402
with socket.socket() as probe:
    if probe.connect_ex(("127.0.0.1", PORT)) == 0:
        sys.exit(f"Port {PORT} is taken: stop what's on it first.")
log = open(TMP / "server.log", "w")
app = subprocess.Popen([sys.executable, "-I", str(ROOT / "run.py"), "serve"], stdout=log, stderr=subprocess.STDOUT)
try:
    for _ in range(100):
        try:
            urllib.request.urlopen(M + "/", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    sam, alex, carol, dana, erin, anon = Client("sam"), Client("alex"), Client("carol"), Client("dana"), Client("erin"), Client()

    print("memory: what's new in it")
    _, d, _ = alex.call("/api/me")
    m = d["memory"]
    ok(m["collections"] == [] and m["pantry"] == [] and m["aisles"] == {} and m["household"] == [] and m["settings"]["units"] == "",
       "a new view has collections, pantry, aisles, household and the units setting, all empty")

    print("collections")
    st, d, _ = alex.me("coll-new", name="  Weeknight  ")
    c = d["memory"]["collections"]
    ok(st == 200 and len(c) == 1 and c[0]["name"] == "Weeknight" and re.match(r"^[0-9a-f]{8}$", c[0]["id"]) and c[0]["codes"] == [],
       "coll-new: a trimmed name and a new 8-hex id")
    first = c[0]["id"]
    _, d, _ = alex.me("coll-new", id="abcdef01", name="x" * 80)
    c = d["memory"]["collections"]
    ok([x["id"] for x in c] == [first, "abcdef01"] and c[1]["name"] == "x" * 60, "an app's own id is kept, the name cut to 60, in creation order")
    _, d, _ = alex.me("coll-new", id="abcdef01", name="again")
    ok(len(d["memory"]["collections"]) == 2, "the same id again makes nothing new (an app catching up)")
    st, d, _ = alex.me("coll-new", name="   ")
    ok(st == 400 and d["error"] == "A collection needs a name.", "an empty name is refused")
    _, d, _ = alex.me("coll-rename", id="abcdef01", name=" Fridays ")
    ok(d["memory"]["collections"][1]["name"] == "Fridays", "coll-rename")
    st, d, _ = alex.me("coll-rename", id="00000000", name="x")
    ok(st == 400 and d["error"] == "No such collection.", "renaming a collection that isn't there is refused")
    alex.me("coll-add", id="abcdef01", code="demo-ramen")
    alex.me("coll-add", id="abcdef01", code="demo-ramen")
    _, d, _ = alex.me("coll-add", id="abcdef01", code="demo-hummus")
    ok(d["memory"]["collections"][1]["codes"] == ["demo-ramen", "demo-hummus"], "coll-add, once each, in order")
    st, _, _ = alex.me("coll-add", id="abcdef01", code="no!")
    st2, _, _ = alex.me("coll-add", id="abcdef01")
    st3, _, _ = alex.me("coll-add", id="12345678", code="demo-ramen")
    ok(st == 400 and st2 == 400 and st3 == 400, "coll-add refuses a bad code, no code, and a collection that isn't there")
    _, d, _ = alex.me("coll-remove", id="abcdef01", code="demo-ramen")
    ok(d["memory"]["collections"][1]["codes"] == ["demo-hummus"], "coll-remove")
    _, d, _ = alex.me("coll-delete", id=first)
    ok([x["id"] for x in d["memory"]["collections"]] == ["abcdef01"], "coll-delete")
    for n in range(99):
        st, _, _ = alex.me("coll-new", name=f"c{n}")
    st, d, _ = alex.me("coll-new", name="one too many")
    ok(st == 400 and d["error"] == "That's 100 collections already.", "100 collections at most")
    _, d, _ = sam.call("/api/me")
    ok(d["memory"]["collections"] == [], "collections are each account's own")

    print("pantry")
    _, d, _ = alex.me("pantry", items=["  Olive oil ", "olive OIL", "Salt", "", "   ", 5, True, None, "x" * 100])
    ok(d["memory"]["pantry"] == ["Olive oil", "Salt", "5", "x" * 60], "pantry: trimmed, cut to 60, deduplicated ignoring case")
    _, d, _ = alex.me("pantry", items=[f"thing {n}" for n in range(500)])
    ok(len(d["memory"]["pantry"]) == 400, "400 things at most")
    st, _, _ = alex.me("pantry", items="salt")
    ok(st == 400, "the pantry must be a list")
    _, d, _ = alex.me("pantry", items=["Rice"])
    ok(d["memory"]["pantry"] == ["Rice"], "pantry replaces the whole list")

    print("aisles")
    _, d, _ = alex.me("aisle", key="olive oil", aisle="pantry")
    ok(d["memory"]["aisles"] == {"olive oil": "pantry"}, "aisle sets one")
    _, d, _ = alex.me("aisle", key="olive oil", aisle="spices")
    ok(d["memory"]["aisles"] == {"olive oil": "spices"}, "and changes it")
    st, d, _ = alex.me("aisle", key="olive oil", aisle="garage")
    ok(st == 400 and d["error"] == "No such aisle.", "an aisle that isn't one of the ten is refused")
    st, _, _ = alex.me("aisle", key="k" * 81, aisle="dairy")
    st2, _, _ = alex.me("aisle", key="", aisle="dairy")
    ok(st == 400 and st2 == 400, "a key over 80 characters, or none, is refused")
    _, d, _ = alex.me("aisle", key="k" * 80, aisle="dairy")
    ok(d["memory"]["aisles"].get("k" * 80) == "dairy", "an 80-character key is fine")
    _, d, _ = alex.me("aisle", key="olive oil", aisle="")
    ok("olive oil" not in d["memory"]["aisles"], "an empty aisle takes the key away")

    print("cooking log")
    _, d, _ = alex.me("cooked", code="demo-ramen", id="c0ffee01", factor=2, note="  Doubled it  ")
    e = next(x for x in d["memory"]["cooked"] if x["id"] == "c0ffee01")
    ok(e["factor"] == 2 and e["note"] == "Doubled it" and e["code"] == "demo-ramen", "cooked keeps factor and a trimmed note")
    ok(all(alex.me("cooked", code="demo-ramen", factor=f)[0] == 400 for f in (0.1, 11, True, "2")), "a factor outside 0.25 to 10, or not a number, is refused")
    _, d, _ = alex.me("cooked", code="demo-ramen", id="c0ffee02", factor=0.25)
    e = next(x for x in d["memory"]["cooked"] if x["id"] == "c0ffee02")
    ok(e["factor"] == 0.25 and "note" not in e, "0.25 is fine, and no note is no note")
    _, d, _ = alex.me("cook-note", id="c0ffee02", note="y" * 600)
    ok(len(next(x for x in d["memory"]["cooked"] if x["id"] == "c0ffee02")["note"]) == 500, "cook-note, cut to 500")
    _, d, _ = alex.me("cook-note", id="c0ffee02", note="  ")
    ok("note" not in next(x for x in d["memory"]["cooked"] if x["id"] == "c0ffee02"), "an empty cook-note takes the note away")
    st, d, _ = alex.me("cook-note", id="ffffffff", note="x")
    ok(st == 400 and d["error"] == "That isn't in the cooking log.", "cook-note on an entry that isn't there is refused")
    _, h, _ = alex.call("/api/history")
    ok(any(x.get("factor") == 2 and x.get("note") == "Doubled it" for x in h["cooked"]), "the history has them too")

    print("units")
    _, d, _ = alex.me("setting", key="units", value="metric")
    ok(d["memory"]["settings"]["units"] == "metric", "units: metric")
    st, d, _ = alex.me("setting", key="units", value="imperial")
    ok(st == 400 and "metric" in d["error"], "units: anything else is refused")
    _, d, _ = alex.me("setting", key="units", value="")
    ok(d["memory"]["settings"]["units"] == "", "units: as written")
    alex.settings("units", value="us")
    _, d, _ = alex.call("/api/settings")
    ok(d["settings"]["units"] == "us", "units through Settings too")
    _, d, _ = alex.me("setting", key="english", value=1)
    ok(d["memory"]["settings"]["english"] is True, "the other settings are still true or false")
    alex.me("setting", key="english", value=False)

    print("households")
    shop_sam = [i["id"] for i in json.loads((STATE / "users" / "sam" / "memory.json").read_text())["shop"]]
    today = time.strftime("%Y-%m-%d")
    alex.me("plan-add", code="demo-hummus", day=today, id="aaaa0001")
    alex.me("shop-add", code="demo-hummus", items=[{"id": "bbbb0001", "item": "tahini", "amount": "1 cup"}])
    st, d, _ = alex.settings("household", members=["sam", "alex"])
    ok(st == 400 and d["error"] == "no such change", "only an admin makes a household")
    st, d, _ = sam.settings("household", members=["sam", " ALEX ", "sam"])
    ok(st == 200 and len(d["households"]) == 1 and d["households"][0]["members"] == ["sam", "alex"], "an admin puts Sam and Alex in one")
    hid = d["households"][0]["id"]
    ok(re.match(r"^[0-9a-f]{8}$", hid) and (STATE / "households" / f"{hid}.json").exists(), "STATE/households/<id>.json")
    _, s, _ = sam.call("/api/settings")
    _, s2, _ = alex.call("/api/settings")
    ok(s["households"] == [{"id": hid, "members": ["sam", "alex"]}] and "households" not in s2, "GET /api/settings lists households, for an admin only")
    _, a, _ = alex.call("/api/me")
    _, b, _ = sam.call("/api/me")
    am, bm = a["memory"], b["memory"]
    ok(am["household"] == ["sam"] and bm["household"] == ["alex"], "view: household is the other members")
    ok({p["id"] for p in am["plan"]} == {p["id"] for p in bm["plan"]} and "aaaa0001" in {p["id"] for p in am["plan"]},
       "both see one plan, with Alex's meal in it")
    ok([i["id"] for i in am["shop"]] == shop_sam + ["bbbb0001"] == [i["id"] for i in bm["shop"]], "and one list: Sam's, then Alex's")
    ok(all(set(p) == {"id", "code", "day", "at"} for p in am["plan"]) and
       all(set(i) == {"id", "item", "amount", "code", "done", "at"} for i in am["shop"]), "the plan and list keep the shapes the Android app reads")
    own = json.loads((STATE / "users" / "alex" / "memory.json").read_text())
    ok(own["plan"] == [] and own["shop"] == [], "Alex's own lists were merged in, and emptied")
    alex.me("plan-add", code="demo-ramen", day=today, id="aaaa0002")
    sam.me("shop-tick", ids=["bbbb0001"], done=True)
    sam.me("plan-move", id="aaaa0001", day="2099-01-01")
    _, a, _ = alex.call("/api/me")
    ok("aaaa0002" in {p["id"] for p in a["memory"]["plan"]}, "a meal Alex plans, Sam sees (plan-add)")
    ok(next(i for i in a["memory"]["shop"] if i["id"] == "bbbb0001")["done"], "what Sam ticks, Alex sees (shop-tick)")
    ok(next(p for p in a["memory"]["plan"] if p["id"] == "aaaa0001")["day"] == "2099-01-01", "plan-move")
    alex.me("shop-remove", ids=["bbbb0001"])
    _, b, _ = sam.call("/api/me")
    ok("bbbb0001" not in {i["id"] for i in b["memory"]["shop"]}, "shop-remove")
    st, d, _ = sam.settings("household", members=["carol", "sam"])
    ok(st == 200 and d["households"][0]["members"] == ["sam", "alex", "carol"], "Carol joins the household Sam is in")
    st, d, _ = sam.settings("household", members=["dana", "erin"])
    ok(st == 200 and len(d["households"]) == 2, "Dana and Erin make another")
    st, d, _ = sam.settings("household", members=["dana", "sam"])
    ok(st == 400 and "different households" in d["error"], "an account is in one household at most")
    ok(sam.settings("household", members=["sam"])[0] == 400 and sam.settings("household", members=["sam", "nobody"])[0] == 400
       and sam.settings("household", members="sam,alex")[0] == 400, "two real accounts or more, in a list")
    st, d, _ = alex.settings("household-leave", aid="carol")
    ok(st == 400 and "owner" in d["error"], "only an admin takes someone else out")
    _, b, _ = sam.call("/api/me")
    before = b["memory"]
    st, d, _ = alex.settings("household-leave", aid="alex")
    ok(st == 200 and "households" not in d, "Alex leaves on their own")
    _, a, _ = alex.call("/api/me")
    _, b, _ = sam.call("/api/me")
    ok(a["memory"]["household"] == [] and b["memory"]["household"] == ["carol"], "and the others go on without them")
    ok([i["id"] for i in a["memory"]["shop"]] == [i["id"] for i in before["shop"]] and
       [p["id"] for p in a["memory"]["plan"]] == [p["id"] for p in before["plan"]], "Alex keeps a copy of the plan and the list")
    alex.me("shop-add", items=[{"id": "bbbb0009", "item": "lemons", "amount": "2"}])
    st, d, _ = sam.settings("household", members=["alex", "sam"])
    _, b, _ = sam.call("/api/me")
    ids = [i["id"] for i in b["memory"]["shop"]]
    ok(st == 200 and len(ids) == len(set(ids)) and ids == [i["id"] for i in before["shop"]] + ["bbbb0009"],
       "Alex joins again: the copies with the same ids are dropped, the new lemons come in")
    sam.settings("household-leave", aid="carol")
    _, c, _ = carol.call("/api/me")
    ok(c["memory"]["household"] == [] and "bbbb0009" in {i["id"] for i in c["memory"]["shop"]}, "an admin takes Carol out; she keeps a copy")
    st, d, _ = sam.settings("household-leave", aid="alex")
    ok(st == 200 and [h["members"] for h in d["households"]] == [["dana", "erin"]] and not (STATE / "households" / f"{hid}.json").exists(),
       "left with one member, a household is over")
    _, b, _ = sam.call("/api/me")
    ok(b["memory"]["household"] == [] and "bbbb0009" in {i["id"] for i in b["memory"]["shop"]}, "and the last one keeps the lists")
    sam.me("shop-add", items=[{"id": "cccc0001", "item": "salt", "amount": ""}])
    _, a, _ = alex.call("/api/me")
    ok("cccc0001" not in {i["id"] for i in a["memory"]["shop"]}, "after that, their lists are their own again")
    dana.me("shop-add", items=[{"id": "dddd0001", "item": "milk", "amount": ""}])
    st, _, _ = sam.settings("account-remove", id="erin")
    _, d, _ = dana.call("/api/me")
    ok(st == 200 and d["memory"]["household"] == [] and "dddd0001" in {i["id"] for i in d["memory"]["shop"]} and memory.households() == [],
       "removing an account takes it out of its household (here, the end of it)")
    st, d, _ = dana.settings("household-leave", aid="dana")
    ok(st == 400 and d["error"] == "That account isn't in a household.", "leaving when not in one is refused")

    print("fixing a recipe")
    _, r, _ = alex.call("/api/r/demo-ramen")
    _, r2, _ = alex.call("/api/r/demo-hummus")
    _, r3, _ = sam.call("/api/r/demo-hummus")
    ok(r["can_edit"] is False and r2["can_edit"] is True and r3["can_edit"] is True and r["edited"] is None,
       "can_edit: the account that added it, and an admin")
    st, d, _ = alex.call("/api/r/demo-ramen/edit", {"lang": "en", "recipe": {"title": "Mine now"}})
    ok(st == 403 and d["error"] == "Only the kitchen's owner or whoever added this recipe can change it.", "anyone else gets 403")
    fix = {k: r2[k] for k in edits.FIELDS}
    fix["title"] = "Alex's Hummus"
    fix["ingredient_groups"] = [{"name": g["name"], "items": [{**i, "amount": i["amount"] or "a pinch"} for i in g["items"]]}
                                for g in fix["ingredient_groups"]] + [{"name": "To serve", "items": [{"amount": "", "item": "  ", "note": ""}]}]
    fix["missing"] = []
    fix["steps"] = fix["steps"] + [{"text": "Rest it for an hour.", "timers": [60, 1440]}, {"text": "   ", "timers": []}]
    st, d, _ = alex.call("/api/r/demo-hummus/edit", {"lang": "en", "recipe": fix})
    _, g, _ = alex.call("/api/r/demo-hummus?lang=en")
    ok(st == 200 and d["title"] == "Alex's Hummus" and d["edited"]["by"] == "alex" and d["edited"]["at"] > 0, "an edit is saved, by Alex")
    ok(d == g, "the answer is the recipe as GET /api/r/<code>?lang= gives it")
    ok(d["complete"] is True and all(i["amount"] for gr in d["ingredient_groups"] for i in gr["items"]), "every amount there and nothing missing: complete")
    ok(len(d["ingredient_groups"]) == len(r2["ingredient_groups"]) and d["steps"][-1]["timers"] == [60, 1440],
       "empty lines are dropped; the timers are kept")
    saved = json.loads((STATE / "reels" / "demo-hummus" / "edits.en.json").read_text())
    ok(saved["by"] == "alex" and saved["at"] and saved["recipe"]["title"] == "Alex's Hummus", "it's kept as edits.en.json with by and at")
    _, idx, _ = alex.call("/api/recipes")
    h = next(x for x in idx["recipes"] if x["code"] == "demo-hummus")
    ok(h["title"] == "Alex's Hummus" and h["items"] == [i["item"] for gr in d["ingredient_groups"] for i in gr["items"]] and
       h["complete"] is True and "Rest it for an hour." in h["text"],
       "the list shows the fix: title, items, complete, text")
    bad = [({"lang": "en", "recipe": {**fix, "steps": [{"text": "x", "timers": [0]}]}}, "timer"),
           ({"lang": "en", "recipe": {**fix, "steps": [{"text": "x", "timers": [2000]}]}}, "timer"),
           ({"lang": "en", "recipe": {**fix, "steps": [{"text": "x", "timers": [1.5]}]}}, "timer"),
           ({"lang": "en", "recipe": {**fix, "title": "  "}}, "title"),
           ({"lang": "en", "recipe": {**fix, "ingredient_groups": "flour"}}, "shape"),
           ({"lang": "en", "recipe": "hummus"}, "shape"),
           ({"lang": "en", "recipe": {**fix, "steps": [{"text": f"s{n}"} for n in range(101)]}}, "100 steps"),
           ({"lang": "en", "recipe": {**fix, "tips": [{"x": 1}]}}, "shape"),
           ({"lang": "fr", "recipe": fix}, "language"),
           ({"lang": "he", "recipe": fix}, "language")]
    ok(all(alex.call("/api/r/demo-hummus/edit", b)[0] == 400 for b, _ in bad), "bad edits are refused: timers, title, shapes, sizes, languages")
    _, d, _ = alex.call("/api/r/demo-hummus/edit", {"lang": "en", "recipe": {**fix, "title": "T" * 500, "summary": "s" * 5000}})
    ok(len(d["title"]) == 200 and len(d["summary"]) == 1000, "long text is cut to its size")
    alex.call("/api/r/demo-hummus/edit", {"lang": "en", "recipe": fix})
    _, sp, _ = sam.call("/api/r/demo-spaghetti")
    fix_sp = {k: sp[k] for k in edits.FIELDS}
    _, d, _ = sam.call("/api/r/demo-spaghetti/edit", {"lang": "en", "recipe": fix_sp})
    ok(sp["complete"] is False and d["complete"] is False and d["edited"]["by"] == "sam", "an incomplete recipe saved as it is stays incomplete")
    groups = [{"name": g["name"], "items": [{**i, "amount": i["amount"] or "200g"} for i in g["items"]]} for g in fix_sp["ingredient_groups"]]
    _, d, _ = sam.call("/api/r/demo-spaghetti/edit", {"lang": "en", "recipe": {**fix_sp, "ingredient_groups": groups}})
    ok(d["complete"] is False, "every amount filled in but something still missing: incomplete")
    _, d, _ = sam.call("/api/r/demo-spaghetti/edit", {"lang": "en", "recipe": {**fix_sp, "ingredient_groups": groups, "missing": []}})
    ok(d["complete"] is True, "every amount there and nothing missing: complete")
    _, d, _ = sam.call("/api/r/demo-spaghetti/edit", {"lang": "en", "revert": True})
    ok(d["complete"] is False and d["edited"] is None and d["missing"] == sp["missing"], "revert: Claude's recipe again")
    ok(until(lambda: "Alex's Hummus" in NOTE("demo-hummus").read_text()), "in the background, the vault note gets the fix")
    ok(cookbook.chosen(STATE / "reels" / "demo-hummus")["title"] == "Alex's Hummus", "and so does the Cookbook copy")
    ok("|fixed:" in cookbook._sig(STATE / "reels" / "demo-hummus", cookbook.chosen(STATE / "reels" / "demo-hummus")) and
       "|fixed:" not in cookbook._sig(STATE / "reels" / "demo-ramen", cookbook.chosen(STATE / "reels" / "demo-ramen")),
       "Cookbook sends it again; a recipe nobody fixed keeps the signature it was sent with")

    print("fixing a Hebrew recipe, and its English copy")
    SH = STATE / "reels" / "demo-shakshuka"
    en_copy = lambda: json.loads((SH / "recipe.en.json").read_text())  # noqa: E731
    _, he, _ = sam.call("/api/r/demo-shakshuka?lang=he")
    fix_he = {k: he[k] for k in edits.FIELDS} | {"title": "שקשוקה של סם"}
    n0 = len(calls("Translate this recipe"))
    st, d, _ = sam.call("/api/r/demo-shakshuka/edit", {"lang": "he", "recipe": fix_he})
    ok(st == 200 and d["lang"] == "he" and d["title"] == "שקשוקה של סם", "Sam fixes the Hebrew")
    ok(until(lambda: en_copy().get("title") == "שקשוקה של סם"), "the English copy is made again from the fixed Hebrew (the pretend translator copies it)")
    ok(len(calls("Translate this recipe")) == n0 + 1 and en_copy().get("source"), "one translation, and the copy knows what it came from")
    _, d, _ = sam.call("/api/r/demo-shakshuka?lang=en")
    ok(d["edited"] is None and d["lang"] == "en", "the English copy itself isn't edited")
    st, d, _ = sam.call("/api/r/demo-shakshuka/edit", {"lang": "en", "recipe": {**fix_he, "title": "Sam's Shakshuka"}})
    ok(st == 200 and d["title"] == "Sam's Shakshuka" and d["edited"]["by"] == "sam", "a fix of the English copy")
    wait_for_runs()
    n1 = len(calls("Translate this recipe"))
    sam.call("/api/r/demo-shakshuka/edit", {"lang": "he", "recipe": {**fix_he, "title": "שקשוקה חריפה"}})
    wait_for_runs()
    ok(len(calls("Translate this recipe")) == n1 and en_copy()["title"] == "שקשוקה של סם",
       "with an English fix, a new Hebrew fix doesn't translate again")
    _, d, _ = sam.call("/api/r/demo-shakshuka/edit", {"lang": "en", "revert": True})
    ok(d["edited"] is None and not (SH / "edits.en.json").exists(), "revert takes the English fix away")
    ok(until(lambda: en_copy()["title"] == "שקשוקה חריפה"), "and the English copy catches up with the Hebrew")
    _, d, _ = sam.call("/api/r/demo-shakshuka/edit", {"lang": "he", "revert": True})
    ok(d["title"] == "שקשוקה" and d["edited"] is None, "reverting the Hebrew brings back Claude's")
    ok(until(lambda: en_copy()["title"] == "שקשוקה"), "and the English copy follows")
    sam.call("/api/r/demo-shakshuka/edit", {"lang": "he", "recipe": fix_he})
    ok(until(lambda: en_copy()["title"] == "שקשוקה של סם"), "(fixed again, for the share page below)")

    print("a fix outlives a redo")
    ok(wait_for_runs(), "(no run is going)")
    rr = run("redo", "demo-hummus")
    rec = json.loads((STATE / "reels" / "demo-hummus" / "recipe.json").read_text())
    ok(rr.returncode == 0 and rec["title"] == "Redone by Claude", "run.py redo makes a new recipe.json (the pretend Claude's)")
    _, d, _ = alex.call("/api/r/demo-hummus?lang=en")
    ok(d["title"] == "Alex's Hummus" and d["edited"]["by"] == "alex" and d["complete"] is True, "and the fix still wins")
    ok("Alex's Hummus" in NOTE("demo-hummus").read_text() and "Redone by Claude" not in NOTE("demo-hummus").read_text(),
       "the redone note has the fix too")
    rr = run("redo", "demo-shakshuka", "--from", "translate")
    ok(rr.returncode == 0 and en_copy()["title"] == "שקשוקה של סם", "a redo's translation starts from the fixed Hebrew")

    print("search text")
    _, idx, _ = alex.call("/api/recipes")
    by = {x["code"]: x for x in idx["recipes"]}
    ok(all("text" in x for x in idx["recipes"]), "every entry has text")
    ok("Boil the eggs" in by["demo-ramen"]["text"] and "text_en" not in by["demo-ramen"], "steps of the recipe's own language")
    ok(any(t in by["demo-cookies"]["text"] for t in json.loads((STATE / "reels" / "demo-cookies" / "recipe.json").read_text())["tips"]),
       "and its tips")
    ok("text_en" in by["demo-shakshuka"] and by["demo-shakshuka"]["text"], "a Hebrew recipe has text_en too")

    print("sharing by link")
    st, d, _ = sam.settings("share", code="demo-shakshuka")
    url = d.get("url", "")
    token = url.rsplit("/", 1)[-1]
    ok(st == 200 and d["ok"] and url == config.settings()["app_url"].rstrip("/") + "/s/" + token and len(token) >= 20, "share gives <app_url>/s/<token>")
    ok(sam.settings("share", code="demo-shakshuka")[1]["url"] == url and alex.settings("share", code="demo-shakshuka")[1]["url"] == url,
       "the same link, whoever asks again")
    _, r, _ = alex.call("/api/r/demo-shakshuka")
    _, r2, _ = alex.call("/api/r/demo-ramen")
    ok(r["share"] == url and r2["share"] is None, "GET /api/r/<code> has share: the link or null")
    ok(sam.settings("share", code="no!")[0] == 400 and sam.settings("share", code="demo-nothing")[0] == 400, "only a recipe can be shared")
    sam.me("note", code="demo-shakshuka", text="SECRET NOTE about it")
    sam.me("rate", code="demo-shakshuka", rating=7)
    st, page, hd = anon.call(f"/s/{token}")
    page = page.decode() if isinstance(page, bytes) else str(page)
    ok(st == 200 and hd.get("Content-Type", "").startswith("text/html"), "the page opens without signing in")
    ok('dir="rtl"' in page and 'lang="he"' in page and "שקשוקה של סם" in page, "in Hebrew, right to left, with the fix")
    ok('<meta name="robots" content="noindex' in page and "noindex" in (hd.get("X-Robots-Tag") or ""), "search engines are told to stay away")
    ok('href="?lang=en"' in page and "@shuk.example" in page and "https://www.instagram.com/reel/demo-shakshuka/" in page,
       "a link to the English copy, the creator and the post")
    ok(f"{token}/photo" in page and "<video" not in page and "SECRET NOTE" not in page and not re.search(r"\b(Sam|Alex|sam|alex)\b", page),
       "the photo, but no video, no notes and no account names")
    ok("<style>" in page and "<script" not in page and "@media print" in page and "#B8441A" in page and "#F0804A" in page,
       "one file: inline CSS in Matkon's colors, for print too, and no scripts")
    ok("default-src 'none'" in (hd.get("Content-Security-Policy") or ""), "a strict content policy")
    st, page_en, _ = anon.call(f"/s/{token}?lang=en")
    page_en = page_en.decode()
    ok(st == 200 and 'lang="en" dir="ltr"' in page_en and 'href="?lang=he"' in page_en, "?lang=en: the English copy, with a way back")
    st, photo, hd = anon.call(f"/s/{token}/photo")
    ok(st == 200 and hd.get("Content-Type") == "image/jpeg" and photo[:2] == b"\xff\xd8", "/s/<token>/photo is the photo")
    st, nope, _ = anon.call("/s/thisisnotatokenatall123")
    ok(st == 404 and b"doesn't work" in nope, "an unknown token: a small 404 page")
    ok(all(anon.call(p)[0] == 401 for p in ("/api/recipes", "/api/r/demo-shakshuka", "/m/demo-shakshuka/photo.jpg", "/api/export", "/api/me")),
       "everything else still needs signing in")
    ok(anon.call("/api/settings", {"op": "share", "code": "demo-ramen"})[0] == 401, "and sharing does too")
    alex.settings("share", code="demo-hummus")
    _, r, _ = alex.call("/api/r/demo-hummus")
    st, page_h, _ = anon.call("/s/" + r["share"].rsplit("/", 1)[-1])
    page_h = page_h.decode()
    ok(st == 200 and "Alex&#x27;s Hummus" in page_h and 'lang="en" dir="ltr"' in page_h and "?lang=" not in page_h,
       "an English recipe: its fix, no language link")
    st, d, _ = sam.settings("unshare", code="demo-shakshuka")
    ok(st == 200 and d == {"ok": True}, "unshare")
    ok(anon.call(f"/s/{token}")[0] == 404 and anon.call(f"/s/{token}/photo")[0] == 404 and alex.call("/api/r/demo-shakshuka")[1]["share"] is None,
       "after that, the link and its photo are gone")
    ok(json.loads((STATE / "shares.json").read_text()) and all(v["code"] != "demo-shakshuka" for v in json.loads((STATE / "shares.json").read_text()).values()),
       "kept kitchen-wide in shares.json")

    print("export")
    st, raw, hd = alex.call("/api/export")
    ok(st == 200 and hd.get("Content-Disposition") == 'attachment; filename="matkon-recipes.jsonld"' and
       hd.get("Content-Type", "").startswith("application/ld+json"), "a .jsonld download")
    items = raw if isinstance(raw, list) else []
    n = sum(1 for f in (STATE / "reels").iterdir() if (json.loads((f / "recipe.json").read_text()) if (f / "recipe.json").exists() else {}).get("is_recipe"))
    ok(len(items) == n == 10, f"every recipe ({n})")
    iso = re.compile(r"^PT\d+H\d+M$")
    good = all(x["@context"] == "https://schema.org" and x["@type"] == "Recipe" and x["name"] and x["inLanguage"] in ("en", "he")
               and all(isinstance(i, str) and not i.startswith("## ") for i in x.get("recipeIngredient", []))
               and all(s["@type"] == "HowToStep" and s["text"] for s in x.get("recipeInstructions", []))
               and all(iso.match(x[k]) for k in ("prepTime", "cookTime", "totalTime") if k in x)
               and x["url"].startswith("https://www.instagram.com/reel/") and x["author"]["name"].startswith("@")
               and datetime.fromisoformat(x["datePublished"]) for x in items)
    ok(good, "each a schema.org Recipe: HowToSteps, ISO 8601 times, author, url, language, date posted")
    names = {x["url"].split("/")[-2]: x for x in items}
    ok(names["demo-hummus"]["name"] == "Alex's Hummus" and names["demo-shakshuka"]["name"] == "שקשוקה של סם" and
       names["demo-shakshuka"]["inLanguage"] == "he", "in each recipe's own language, with the fixes")
    ok(names["demo-ramen"]["totalTime"] == "PT0H15M" and names["demo-ramen"]["recipeYield"] == "2 bowls" and
       names["demo-ramen"]["recipeCuisine"] == "Japanese", "times, yield and cuisine as the recipe has them")
    ok("Not in the reel" in names["demo-spaghetti"]["description"], "what's not in the reel goes in the description")

    print("asking about a recipe")
    hist = [{"q": f"q{n}", "a": f"a{n}"} for n in range(8)]
    st, d, _ = alex.call("/api/ask", {"code": "demo-ramen", "lang": "en", "question": "  Can I use udon?  ", "history": hist})
    last = calls("The question:")[-1]
    ok(st == 200 and d == {"answer": "Fake answer: Can I use udon?"}, "an answer, as plain text")
    ok("15-Minute Miso Ramen" in last["text"] and "Boil the eggs" in last["text"] and "Can I use udon?" in last["text"],
       "Claude gets the recipe and the question")
    ok(last["text"].count("\nQ: ") == 6 and "Q: q2" in last["text"] and "Q: q1\n" not in last["text"], "and the last six questions before it")
    ok("--tools" in last["argv"] and last["argv"][last["argv"].index("--tools") + 1] == "" and "--model" not in last["argv"],
       "the same claude call as the recipes: no tools, the model setting")
    alex.call("/api/ask", {"code": "demo-hummus", "question": "How long does it keep?"})
    ok("Alex's Hummus" in calls("The question:")[-1]["text"], "the recipe as shown, fixes and all")
    ok(alex.call("/api/ask", {"code": "demo-ramen", "question": "   "})[0] == 400 and
       alex.call("/api/ask", {"code": "demo-ramen", "question": "x" * 1001})[0] == 400 and
       alex.call("/api/ask", {"code": "demo-ramen", "question": "ok?", "history": "no"})[0] == 400, "an empty or too long question is refused")
    ok(alex.call("/api/ask", {"code": "demo-nothing", "question": "?"})[0] == 404, "a recipe that isn't there: 404")
    t = time.time()
    st, d, _ = alex.call("/api/ask", {"code": "demo-ramen", "question": "SLOW one"})
    ok(st == 504 and d == {"error": "Claude didn't answer in time."} and time.time() - t < 8, "Claude too slow: 504 (here after 3 s)")
    answers = [dana.call("/api/ask", {"code": "demo-soup", "question": f"q {n}"})[0] for n in range(31)]
    st, d, _ = dana.call("/api/ask", {"code": "demo-soup", "question": "one more"})
    ok(answers[:30] == [200] * 30 and answers[30] == 429 and st == 429 and "30 questions" in d["error"], "30 questions an hour, then 429")
    ok(alex.call("/api/ask", {"code": "demo-soup", "question": "still me"})[0] == 200, "counted for each account")
finally:
    app.terminate()
    app.wait(10)
    wait_for_runs(30)

if FAILS:
    print("server log:\n" + (TMP / "server.log").read_text()[-3000:])
    for p in (STATE / "logs").glob("*.log"):
        print(p.name + ":\n" + p.read_text()[-3000:])
shutil.rmtree(TMP, ignore_errors=True)
print(f"{len(FAILS)} FAILED" if FAILS else "all good")
sys.exit(1 if FAILS else 0)

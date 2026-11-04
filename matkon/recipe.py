"""Turning a reel into a recipe, with Claude.

Claude gets the caption, the transcript and the frame sheets in one message and no tools at all
(claude --print, --tools "", images sent inline), and answers with one JSON object. The rule that
matters: only what the reel gives. An amount the reel doesn't say stays empty; nutrition numbers
are copied only as the reel states them.
"""
import base64
import json
import re
import subprocess

from . import config

KINDS = ["Breakfast", "Mains", "Salads & sides", "Soups", "Bread & dough", "Baking & sweets",
         "Snacks", "Sauces & dips", "Drinks"]

PROMPT = """You turn a saved Instagram cooking reel into a recipe someone can cook from.

You have:
- the post's caption, written by the creator (@{user});
- a transcript of what's said (speech-to-text: it can mishear words, and if nobody talks it may be song lyrics or noise);
- the creator's own recipe page, when the caption links one (under "Linked page");
- frames from the video, on {n} contact sheets. Each sheet is a 2×2 grid, read left to right, top to bottom. The times of the frames on each sheet are listed under "Sheets".

Rules:
1. Use only what the reel gives: the caption, the speech, the words on screen, what is plainly shown, and the creator's linked recipe page. The linked page is the best source for amounts and steps; when it gives a full recipe, follow it, and add what the video adds as tips. Never estimate, assume or fill in an amount, a time, a temperature or a serving count. If the reel doesn't give an ingredient's amount, leave "amount" empty. If the caption and the video disagree, prefer the caption and add a tip that says what the video shows instead.
2. Nutrition (calories, protein and so on): copy it only exactly as the reel states it. If the reel doesn't state it, leave "nutrition" empty.
3. If the reel sends people elsewhere for the recipe ("comment RECIPE", "link in bio") and there's no readable linked page, still write down everything the reel does give, set "complete" to false, and list in "missing" what a cook would still need. "complete" is true only when someone could cook it from this page alone: every ingredient with its amount (or "to taste"), and the steps.
4. If the reel isn't a recipe at all (a joke, a review, a restaurant visit with nothing to cook), set "is_recipe" to false and fill only "title" and "summary".
5. Language: if the reel is in Hebrew, write the whole recipe in Hebrew. Otherwise write it in English, translating whatever is in another language. A dish's own name stays as the creator calls it (Shakshuka, Pad Kra Pao, Tarte Tatin).
6. Steps: short, clear, in order, built from what's said, written and shown. The creator's asides and tips go in "tips", not in the steps. Keep units as given; don't convert them. An ingredient's "note" is a few words at most (chopped, at room temperature); if you can't tell what an ingredient is, write your best plain name for it ("white flour or starch") and put the question in "missing".
7. "time" and "servings": only as stated; don't add times up or work anything out.
   "timers": whole minutes, only where a step itself states a time ("bake 20 to 25 minutes" gives [20, 25]).
8. "photo_at": the time, in seconds, of the frame where the finished dish fills most of the picture: not a frame where a person is the main thing in it, and ideally with no words over it. If no frame shows the finished dish, pick the best one of the food.
9. "tags": two to four, plain lowercase words.

Answer with one JSON object and nothing else:
{{
  "is_recipe": true,
  "lang": "en or he",
  "title": "the dish's name",
  "summary": "one plain sentence: what the dish is",
  "kind": "one of: {kinds}",
  "cuisine": "",
  "tags": ["like: passover, vegan, air fryer, no-bake"],
  "servings": "",
  "time": {{"prep": "", "cook": "", "total": ""}},
  "oven": "",
  "ingredient_groups": [{{"name": "", "items": [{{"amount": "", "item": "", "note": ""}}]}}],
  "steps": [{{"text": "", "timers": []}}],
  "tips": [],
  "nutrition": {{"per": "", "calories": "", "protein": "", "carbs": "", "fat": "", "other": ""}},
  "main_ingredients": ["three to six plain words"],
  "complete": true,
  "missing": ["short phrases, like: how much flour, oven temperature"],
  "from": {{"caption": true, "speech": true, "screen": true}},
  "photo_at": "seconds: one of the frame times under Sheets"
}}

Caption:
<<<
{caption}
>>>

Transcript ({lang}):
<<<
{transcript}
>>>

Linked page:
<<<
{linked}
>>>

Sheets:
{sheets}
"""


def _transcript_text(tr):
    segs = (tr or {}).get("segments") or []
    return "\n".join(f"[{s['start']:.0f}s] {s['text']}" for s in segs if s.get("text", "").strip()) or "(nothing said)"


def build_message(post, tr, sheets, folder, linked_text="(none)"):
    text = PROMPT.format(
        user=post.get("user") or "unknown", n=len(sheets), kinds=", ".join(KINDS),
        caption=post.get("caption") or "(no caption)", lang=(tr or {}).get("language") or "?",
        transcript=_transcript_text(tr), linked=linked_text,
        sheets="\n".join(f"Sheet {i + 1}: frames at " + ", ".join(f"{t}s" for t in s["times"]) for i, s in enumerate(sheets)))
    content = []
    for i, s in enumerate(sheets):
        content.append({"type": "text", "text": f"Sheet {i + 1}"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                     "data": base64.b64encode((folder / "sheets" / s["file"]).read_bytes()).decode()}})
    content.append({"type": "text", "text": text})
    return {"type": "user", "message": {"role": "user", "content": content}}


def ask_claude(message, model=None):
    cmd = ["claude", "--print", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
           "--tools", "", "--strict-mcp-config", "--setting-sources", "project", "--permission-mode", "dontAsk"]
    if model:
        cmd += ["--model", model]
    r = subprocess.run(cmd, input=json.dumps(message) + "\n", capture_output=True, text=True, timeout=900,
                       cwd=str(config.STATE))
    result = None
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "result":
            result = d
    if not result or result.get("is_error"):
        why = (result or {}).get("result") or (r.stderr or "").strip()[-300:] or "no answer"
        raise RuntimeError("Claude: " + str(why)[:300])
    return result.get("result") or ""


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError("Claude's answer had no JSON in it")
    return clean(json.loads(m.group(0)))


def _s(v):
    return v.strip() if isinstance(v, str) else ("" if v is None else str(v).strip())


def _list(v):
    return [x for x in (v if isinstance(v, list) else []) if x not in (None, "", [], {})]


def _seconds(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    m = re.search(r"\d+(?:\.\d+)?", v) if isinstance(v, str) else None
    return float(m.group(0)) if m else None


def clean(d):
    """Every field there and the right shape, whatever the answer left out."""
    r = {
        "is_recipe": bool(d.get("is_recipe", True)),
        "lang": "he" if _s(d.get("lang")).lower().startswith("he") else "en",
        "title": _s(d.get("title")) or "Untitled",
        "summary": _s(d.get("summary")),
        "kind": _s(d.get("kind")) if _s(d.get("kind")) in KINDS else "Mains",
        "cuisine": _s(d.get("cuisine")),
        "tags": [_s(t).lower() for t in _list(d.get("tags")) if _s(t)][:4],
        "servings": _s(d.get("servings")),
        "time": {k: _s((d.get("time") or {}).get(k)) for k in ("prep", "cook", "total")},
        "oven": _s(d.get("oven")),
        "ingredient_groups": [],
        "steps": [],
        "tips": [_s(t) for t in _list(d.get("tips")) if _s(t)],
        "nutrition": {k: _s((d.get("nutrition") or {}).get(k)) for k in ("per", "calories", "protein", "carbs", "fat", "other")},
        "main_ingredients": [_s(t).lower() for t in _list(d.get("main_ingredients")) if _s(t)][:6],
        "complete": bool(d.get("complete", True)),
        "missing": [_s(t) for t in _list(d.get("missing")) if _s(t)],
        "from": {k: bool((d.get("from") or {}).get(k)) for k in ("caption", "speech", "screen")},
        "photo_at": _seconds(d.get("photo_at")),
    }
    for g in _list(d.get("ingredient_groups")):
        items = [{"amount": _s(i.get("amount")), "item": _s(i.get("item")), "note": _s(i.get("note"))}
                 for i in _list(g.get("items")) if isinstance(i, dict) and _s(i.get("item"))]
        if items:
            r["ingredient_groups"].append({"name": _s(g.get("name")), "items": items})
    for s in _list(d.get("steps")):
        if isinstance(s, str):
            s = {"text": s}
        if isinstance(s, dict) and _s(s.get("text")):
            timers = [int(t) for t in _list(s.get("timers")) if isinstance(t, (int, float)) and 0 < t <= 24 * 60]
            r["steps"].append({"text": _s(s["text"]), "timers": timers[:3]})
    if not any(r["nutrition"].values()):
        r["nutrition"] = {}
    return r

"""A Hebrew recipe in English (reels/<code>/recipe.en.json), made once, so switching is instant.

Claude gets the recipe as JSON and gives back the same JSON with the words in English: the same
groups, items and steps in the same order (so ticked ingredients and the cooking step still line up),
the same numbers and timers. Anything that doesn't line up is thrown away and tried again next run.
"""
import json

from . import recipe

FIELDS = ("title", "summary", "kind", "cuisine", "tags", "servings", "time", "oven", "ingredient_groups", "steps",
          "tips", "nutrition", "missing")

PROMPT = """Translate this recipe from Hebrew into natural, idiomatic English, the way an English-language cookbook would write it.

Rules:
- Give back the same JSON: every key, and the same number of ingredient groups, items, steps, tips and "missing" lines, in the same order. Don't add, drop, merge or split anything.
- Translate only the words. Keep every number exactly as it is, and keep each step's "timers" list as it is.
- Units: translate the words (כוס = cup, כף = tbsp, כפית = tsp, גרם = g, מ״ל = ml, ק״ג = kg, קילו = kg), and don't convert anything. A "חצי קילו" is "half a kilo".
- A dish's own name keeps its name, written in English letters (Shakshuka, Burmelos, Chalachapuri), with a few words of explanation in the summary if it helps.
- "kind" stays exactly as it is. "tags" become short lowercase English words.
- Leave empty strings empty.

Answer with the JSON and nothing else.

Recipe:
"""


def _shape(r):
    return ([len(g["items"]) for g in r.get("ingredient_groups", [])], len(r.get("steps", [])), len(r.get("tips", [])),
            len(r.get("missing", [])), [s.get("timers") for s in r.get("steps", [])])


def to_english(r, model=None):
    """The English version's fields, or raises RuntimeError when Claude's answer doesn't line up."""
    src = {k: r.get(k) for k in FIELDS}
    msg = {"type": "user", "message": {"role": "user", "content": [
        {"type": "text", "text": PROMPT + json.dumps(src, ensure_ascii=False, indent=1)}]}}
    out = recipe.parse(recipe.ask_claude(msg, model))     # parse() also cleans it into the usual shape
    out["kind"] = r.get("kind")
    for s_out, s_in in zip(out["steps"], r.get("steps", [])):
        s_out["timers"] = s_in.get("timers", [])
    if _shape(out) != _shape(r):
        raise RuntimeError("the English version doesn't line up with the Hebrew one")
    return {k: out.get(k) for k in FIELDS} | {"lang": "en", "translated_from": r.get("lang")}

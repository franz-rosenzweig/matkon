"""Asking about a recipe while cooking it: "can I use butter instead?", "how far ahead can I make it?"

Claude gets the recipe as it's shown (edits and all), the last few questions and answers, and the new
question, the same way recipe.py calls it (claude --print, no tools, the model setting), and answers
in plain text, in the question's language. It's told never to put words in the reel's mouth and to
say when it's guessing. 30 questions an account an hour, and 90 seconds an answer
(MATKON_ASK_TIMEOUT, for tests).
"""
import json
import os
import subprocess
import threading
import time

from . import config

TIMEOUT = int(os.environ.get("MATKON_ASK_TIMEOUT") or 90)
PER_HOUR = 30
MAX_QUESTION = 1000
MAX_HISTORY = 6
_asked = {}
_lock = threading.Lock()

PROMPT = """You help someone who is cooking from a recipe in Matkon, an app that turns saved Instagram cooking reels into recipes. Answer their question about this recipe.

How to answer:
- Short and practical, like a friend who cooks well, standing next to them: a few sentences, or a short list when it's steps. Plain text only: no headings, no tables, no Markdown.
- Answer in the language the question is written in.
- Kitchen help is what's wanted: substitutions, timing, technique, make-ahead and storage, scaling, saving something that went wrong. Keep food safety right.
- The recipe below is everything Matkon took from the reel (its caption, what's said and what's shown). Never say the reel or the creator says, shows or means anything that isn't in it.
- When the recipe doesn't give something (an amount, a time, a temperature), say so, and if you suggest one, say it's your suggestion and not the creator's.
- When you're guessing, or it depends on what you can't see (their oven, their pan, their ingredients), say so plainly.
- If the question has nothing to do with cooking or this recipe, say in a sentence that you can only help with the recipe.

The recipe:
<<<
{recipe}
>>>
{history}
The question:
<<<
{question}
>>>
"""


def allowed(aid):
    """Counts a question for this account; False when it has asked PER_HOUR in the last hour."""
    now = time.time()
    with _lock:
        for k in list(_asked):
            _asked[k] = [t for t in _asked[k] if now - t < 3600]
            if not _asked[k]:
                del _asked[k]
        if len(_asked.get(aid, [])) >= PER_HOUR:
            return False
        _asked.setdefault(aid, []).append(now)
    return True


def context(r):
    """The recipe as Claude reads it: what the cook sees, nothing about the app."""
    keep = {"title": r.get("title"), "summary": r.get("summary"), "creator": "@" + r["user"] if r.get("user") else "",
            "servings": r.get("servings"), "time": r.get("time"), "oven": r.get("oven"),
            "ingredient_groups": r.get("ingredient_groups"), "steps": [s.get("text") for s in r.get("steps") or []],
            "tips": r.get("tips"), "not_in_the_reel": r.get("missing"), "nutrition": r.get("nutrition"),
            "kind": r.get("kind"), "cuisine": r.get("cuisine")}
    return json.dumps({k: v for k, v in keep.items() if v not in (None, "", [], {})}, ensure_ascii=False, indent=1)


def message(r, question, history=()):
    past = ""
    if history:
        past = "\nEarlier in this conversation:\n" + "\n".join(f"Q: {q}\nA: {a}" for q, a in history) + "\n"
    text = PROMPT.format(recipe=context(r), history=past, question=question)
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def answer(r, question, history=(), model=None, timeout=None):
    """Claude's answer, as plain text. Raises subprocess.TimeoutExpired when it takes too long, and
    RuntimeError when Claude says no."""
    cmd = ["claude", "--print", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
           "--tools", "", "--strict-mcp-config", "--setting-sources", "project", "--permission-mode", "dontAsk"]
    if model:
        cmd += ["--model", model]
    p = subprocess.run(cmd, input=json.dumps(message(r, question, history)) + "\n", capture_output=True, text=True,
                       timeout=timeout or TIMEOUT, cwd=str(config.STATE))
    result = None
    for line in p.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("type") == "result":
            result = d
    if not result or result.get("is_error") or not (result.get("result") or "").strip():
        why = (result or {}).get("result") or (p.stderr or "").strip()[-300:] or "no answer"
        raise RuntimeError("Claude: " + str(why)[:300])
    return result["result"].strip()

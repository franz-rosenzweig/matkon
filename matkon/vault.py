"""The recipe as a note in an Obsidian vault (settings: notes_dir, photos_dir, note_tag).

The front matter is the usual recipe kind (categories [[Recipes]], cuisine, type, ingredients,
author, url, image, rating, cooked), plus `matkon: <code>`. Notes are found by that line, wherever
they've been moved to. Matkon rewrites a note only while its body is exactly as Matkon wrote it:
once it's been edited in Obsidian, it's left alone.
"""
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path

from . import config

SKIP_DIRS = {".obsidian", ".trash", ".claude", ".git", "node_modules"}
HEAD = {
    "en": {"ing": "Ingredients", "dir": "Directions", "tips": "Tips", "nut": "Nutrition", "miss": "Not in the reel",
           "src": "Source", "notes": "Notes", "serves": "Serves", "makes": "Makes", "prep": "Prep", "cook": "Cook", "total": "Total",
           "oven": "Oven", "per": "Per", "open": "Open in Matkon", "on": "on Instagram", "page": "Recipe page"},
    "he": {"ing": "מצרכים", "dir": "אופן ההכנה", "tips": "טיפים", "nut": "ערכים תזונתיים", "miss": "חסר בסרטון",
           "src": "מקור", "notes": "הערות", "serves": "מנות", "makes": "כמות", "prep": "הכנה", "cook": "בישול", "total": "סה״כ",
           "oven": "תנור", "per": "ל", "open": "פתיחה במתכון", "on": "באינסטגרם", "page": "דף המתכון"},
}


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def find_notes():
    """{code: path} for every Matkon note in the vault, by the `matkon:` line in its front matter."""
    found = {}
    for root, dirs, files in os.walk(config.VAULT or "/nonexistent"):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".md"):
                continue
            p = Path(root) / f
            try:
                with open(p, encoding="utf-8") as fh:
                    head = fh.read(3000)
            except OSError:
                continue
            if head.startswith("---"):
                m = re.search(r"^matkon:\s*\"?([\w-]+)\"?\s*$", head.split("\n---", 1)[0], re.M)
                if m:
                    found[m.group(1)] = p
    return found


def _safe(name):
    name = re.sub(r'[\\/:*?"<>|#^\[\]]', "", name).strip(" .")
    return re.sub(r"\s+", " ", name)[:100] or "Recipe"


def _yaml(v):
    v = str(v)
    if re.fullmatch(r"[^\W\d][\w &'.-]*", v) and v.lower() not in ("yes", "no", "true", "false", "null", "on", "off"):
        return v
    return json.dumps(v, ensure_ascii=False)


def render(r, post, photo_name):
    h = HEAD[r["lang"]]
    st = config.settings()
    code = post["code"]
    who = "@" + post["user"] if post.get("user") else ""
    fm = ["---", "categories:", '  - "[[Recipes]]"', f"cuisine: {_yaml(r['cuisine']) if r['cuisine'] else ''}".rstrip(),
          "type:", f"  - {_yaml(r['kind'].lower())}"]
    fm += [f"  - {_yaml(t)}" for t in r["tags"][:3] if t != r["kind"].lower()]
    fm += ["ingredients:"] + [f"  - {_yaml(x)}" for x in r["main_ingredients"]]
    fm += ["author:", f"  - {_yaml(who)}" if who else "  -", f"url: {post['url']}",
           f'image: "[[{photo_name}]]"' if photo_name else "image:", "rating:", "cooked: false",
           "tags:", "  - recipes", "  - instagram-reels", f"matkon: {code}", "---"] + ([st["note_tag"]] if st.get("note_tag") else [])
    body = [f"# {r['title']}", ""]
    if r["summary"]:
        body += [r["summary"], ""]
    if photo_name:
        body += [f"![[{photo_name}]]", ""]
    facts = []
    if r["servings"]:
        plain = re.match(r"^\d+([–-]\d+)?( |$)(as\b|people|servings?\b|$)", r["servings"].strip())
        facts.append(f"{h['serves'] if plain else h['makes']}: {r['servings']}")
    for k in ("prep", "cook", "total"):
        if r["time"].get(k):
            facts.append(f"{h[k]}: {r['time'][k]}")
    if r["oven"]:
        facts.append(f"{h['oven']}: {r['oven']}")
    if facts:
        body += [" · ".join(facts), ""]
    if r["ingredient_groups"]:
        body += [f"## {h['ing']}", ""]
        for g in r["ingredient_groups"]:
            if g["name"]:
                body += [f"### {g['name']}", ""]
            for i in g["items"]:
                line = " ".join(x for x in (i["amount"], i["item"]) if x)
                body.append(f"- {line}" + (f", {i['note']}" if i["note"] else ""))
            body.append("")
    if r["steps"]:
        body += [f"## {h['dir']}", ""] + [f"{n}. {s['text']}" for n, s in enumerate(r["steps"], 1)] + [""]
    if r["tips"]:
        body += [f"## {h['tips']}", ""] + [f"- {t}" for t in r["tips"]] + [""]
    if r["nutrition"]:
        n = r["nutrition"]
        lines = [f"- {k.capitalize()}: {n[k]}" for k in ("calories", "protein", "carbs", "fat") if n.get(k)]
        if n.get("other"):
            lines.append(f"- {n['other']}")
        body += [f"## {h['nut']}" + (f" ({n['per']})" if n.get("per") else ""), ""] + lines + [""]
    if r["missing"]:
        body += [f"## {h['miss']}", ""] + [f"- {m}" for m in r["missing"]] + [""]
    src = [f"[{who or 'Instagram'} {h['on']}]({post['url']})"]
    if r.get("link"):
        src.append(f"[{h['page']}]({r['link']})")
    src.append(f"[{h['open']}]({st['app_url']}/#/r/{code})")
    body += [f"## {h['src']}", "", " · ".join(src), "",
             f"## {h['notes']}", "", "- ", ""]
    return "\n".join(fm + body)


def split(text):
    """(front matter with its --- lines, body)."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[: end + 5], text[end + 5:]
    return "", text


def write(folder, r, post, notes):
    """Writes (or refreshes) the note for this reel. Returns its path, or None when it was left alone.

    Obsidian's plugins rewrite front matter on their own (quotes, an `updated:` line), and rating and
    cooked are yours to fill in, so only the body counts as Matkon's: a refresh keeps the note's front
    matter as it is and replaces the body, and only while the body is still exactly what Matkon wrote."""
    st = config.settings()
    code = post["code"]
    record_path = folder / "vault-note.json"    # kept across redos: it knows whether the note was edited
    record = json.loads(record_path.read_text()) if record_path.exists() else {}
    photo_name = None
    src = folder / "photo.jpg" if (folder / "photo.jpg").exists() else folder / "cover.jpg"
    if src.exists():
        pdir = config.VAULT / st["photos_dir"]
        pdir.mkdir(parents=True, exist_ok=True)
        photo_name = f"{code}.jpg"
        dst = pdir / photo_name
        if not dst.exists() or dst.read_bytes() != src.read_bytes():
            shutil.copyfile(src, dst)
    text = render(r, post, photo_name)
    path = notes.get(code)
    if path and path.exists():
        fm, body = split(path.read_text(encoding="utf-8"))
        if _sha(body) != record.get("body_sha"):
            return None                                   # edited in Obsidian since: yours now
        text = (fm or split(text)[0]) + split(text)[1]
    else:
        ndir = config.VAULT / st["notes_dir"]
        ndir.mkdir(parents=True, exist_ok=True)
        base = _safe(r["title"])
        path = ndir / f"{base}.md"
        if path.exists():
            path = ndir / f"{base} (@{post.get('user') or code}).md"
        if path.exists():
            path = ndir / f"{base} ({code}).md"
    tmp = path.with_name(path.name + ".matkon-tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    record_path.write_text(json.dumps({"path": str(path), "body_sha": _sha(split(text)[1]), "written": int(time.time())}))
    notes[code] = path
    return path

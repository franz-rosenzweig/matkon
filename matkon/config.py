"""Where Matkon keeps things, and the few settings it has.

Everything about one particular setup (paths, addresses, which collection) lives outside the code:
- an env file, KEY=value lines: MATKON_ENV, or else private/matkon.env, or else matkon.env, in the
  checkout. Real environment variables win over it.
- settings.json (MATKON_SETTINGS, or else STATE/settings.json): the collection and the note folders.

STATE (MATKON_STATE, ~/.local/share/matkon by default) holds one folder per reel (reels/<code>/:
the post, the video, its frames, the transcript, the recipe).
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env():
    # MATKON_ENV, when it's set, is the only file read (a name that isn't there: none at all)
    paths = [os.environ["MATKON_ENV"]] if "MATKON_ENV" in os.environ else [ROOT / "private" / "matkon.env", ROOT / "matkon.env"]
    for p in paths:
        if p and Path(p).is_file():
            for line in Path(p).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), os.path.expanduser(v.strip().strip('"\'')))
            return


_load_env()
env = os.environ.get

STATE = Path(env("MATKON_STATE") or Path.home() / ".local" / "share" / "matkon")
REELS = STATE / "reels"
PAUSED = STATE / "paused"          # while it's there, the browser extension leaves Instagram alone


def paused():
    return PAUSED.exists()
SETTINGS_PATH = Path(env("MATKON_SETTINGS") or STATE / "settings.json")

# The Python that has faster-whisper (pip install -r requirements.txt into .venv).
_VENV = ROOT / ".venv" / "bin" / "python"
PY = env("MATKON_PY") or (str(_VENV) if _VENV.exists() else sys.executable)
WHISPER = [PY, str(ROOT / "tools" / "whisper_segments.py")]

# An Obsidian vault for the recipe notes (optional: no vault, no notes).
VAULT = Path(env("MATKON_VAULT")) if env("MATKON_VAULT") else None

# A command to tell you things: NOTIFY "Matkon" "message" [now]. Optional.
NOTIFY = env("MATKON_NOTIFY")

DEFAULTS = {
    "collection_id": None,          # the saved collection to read (Instagram's id for it; the extension sets it)
    "collection_name": "Recipes",
    "notes_dir": "Recipes",         # vault folder for the recipe notes
    "photos_dir": "Recipes/media",  # vault folder for their photos
    "note_tag": "",                 # an inline tag put on its own line above each note's title, if you want one
    "app_url": "http://127.0.0.1:8510",   # where the app is, for the link in each note
    "check_hours": 6,               # the browser looks at your newest saves this often, while you're on Instagram
    "scan_pages": 2,                # how many pages of newest saves it looks at (21 posts a page)
    "per_hour": 4,                  # reels it brings in an hour, at most
    "per_run": 6,                   # reels a run works through, at most
}


def settings():
    s = dict(DEFAULTS)
    try:
        s.update(json.loads(SETTINGS_PATH.read_text()))
    except (OSError, ValueError):
        pass
    return s


def save_settings(s):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps({k: s[k] for k in s if k in DEFAULTS}, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(SETTINGS_PATH)


def model():
    """MATKON_MODEL, or the CLAUDE_MODEL line of the file MATKON_MODEL_FROM names (so a model chosen
    once for several automations is followed here too), or Claude Code's own default."""
    if env("MATKON_MODEL"):
        return env("MATKON_MODEL")
    if env("MATKON_MODEL_FROM"):
        try:
            for line in open(env("MATKON_MODEL_FROM"), encoding="utf-8"):
                if line.startswith("CLAUDE_MODEL="):
                    return line.split("=", 1)[1].strip().strip('"\'') or None
        except OSError:
            pass
    return None

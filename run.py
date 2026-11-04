#!/usr/bin/env python3
"""python3 -I run.py <command>: the same as python3 -m matkon, for cron and systemd (-I keeps the
current folder and the environment's Python paths out of it)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matkon.__main__ import main  # noqa: E402

sys.exit(main() or 0)

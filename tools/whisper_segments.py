#!/usr/bin/env python3
"""whisper_segments.py FILE [--model small]

What's said in a video, with faster-whisper on the CPU, printed as one line of JSON:
{"language": "en", "segments": [{"start": 0.0, "end": 2.1, "text": "..."}]}.
Matkon runs it with MATKON_PY, the Python that has faster-whisper."""
import argparse
import json
import os

from faster_whisper import WhisperModel

ap = argparse.ArgumentParser()
ap.add_argument("file")
ap.add_argument("--model", default=os.environ.get("MATKON_WHISPER_MODEL", "small"))
a = ap.parse_args()
model = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=min(8, os.cpu_count() or 4))
segments, info = model.transcribe(a.file, vad_filter=True)
print(json.dumps({"language": info.language,
                  "segments": [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segments]}))

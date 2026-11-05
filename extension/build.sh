#!/bin/sh
# Packs the extension into dist/ (git ignores it):
#   dist/chromium/              for Chrome, Arc or Edge: chrome://extensions, Developer mode, "Load unpacked"
#   dist/matkon-extension.zip   the same, zipped (what Matkon's Settings hands out for Chrome)
#   dist/firefox/               for Firefox or Zen: about:debugging, "Load Temporary Add-on"
#   dist/matkon-extension.xpi   the same, zipped; a lasting install needs Mozilla's signature (sign.sh)
# Each browser gets a manifest without the other's keys. No build step otherwise.
set -eu
cd "$(dirname "$0")"
rm -rf dist
mkdir -p dist/chromium dist/firefox
FILES="background.js content.js popup.html popup.js options.html options.js ui.css icons"
for d in chromium firefox; do cp -R $FILES "dist/$d/"; done
python3 - <<'PY'
import json, os, zipfile
m = json.load(open("manifest.json"))
for target in ("chromium", "firefox"):
    t = json.loads(json.dumps(m))
    if target == "chromium":
        t["background"] = {"service_worker": "background.js"}
        t.pop("browser_specific_settings", None)
    else:
        t["background"] = {"scripts": ["background.js"]}
    with open(f"dist/{target}/manifest.json", "w") as f:
        json.dump(t, f, indent=2, ensure_ascii=False)
        f.write("\n")
    out = "dist/matkon-extension." + ("zip" if target == "chromium" else "xpi")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, names in os.walk(f"dist/{target}"):
            for n in sorted(names):
                p = os.path.join(root, n)
                z.write(p, os.path.relpath(p, f"dist/{target}"))
    print(out, os.path.getsize(out), "bytes")
PY

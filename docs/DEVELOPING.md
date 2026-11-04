# Developing Matkon

The notes I want when I come back to this later.

## Layout

- `matkon/config.py` holds the paths and settings. Everything about one particular setup comes from the env file (`MATKON_ENV`, else `private/matkon.env`, else `matkon.env`) and `settings.json`, never from the code.
- `matkon/instagram.py` reads the saved posts and downloads videos. The website's per-collection address answers with a page now, so it pages through `/api/v1/feed/saved/posts/` (newest save first, 21 a page) and keeps the posts whose `saved_collection_ids` has the recipe collection. A normal run looks at 3 pages, and `--full` goes through all of them, which takes a few minutes for a couple of thousand saves.
- `matkon/reel.py` handles the frames (one every 1.5 s, 32 at most, four to a 2×2 sheet at 432 px), the transcript (`tools/whisper_segments.py`, run with `MATKON_PY`) and the dish photo.
- `matkon/linked.py` fetches the caption's link once, as itself (no disguise). It keeps the page's schema.org Recipe when there is one, and the page's text when there isn't. A Substack front page gets an archive search for the dish.
- `matkon/recipe.py` holds the prompt and the call: `claude --print` with `--tools ""`, the frames sent inline in one stream-json message, and the answer cleaned into a fixed shape. Claude's raw answer is kept as `answer.txt`.
- `matkon/translate.py` makes the English version of a Hebrew recipe (`recipe.en.json`), the last stage of a reel's run, so a hiccup there never holds up the recipe or the note. Claude gets the recipe JSON and gives back the same JSON in English; the timers are put back from the original, and anything whose groups, items, steps, tips or "missing" lines don't line up is thrown away and tried again. The server serves either language (`api/r/<code>?lang=en`), the account's "Hebrew recipes in English" switch picks the default, and the list carries `title_en` and `items_en` for cards and search.
- `matkon/vault.py` writes the note. It compares only the BODY to what Matkon wrote last (`vault-note.json`), because Obsidian's plugins rewrite front matter on their own.
- `matkon/accounts.py` holds the accounts (scrypt hashes in `accounts.json`, 600) and the signed cookie, which carries an epoch so a new password signs that account out everywhere. It also keeps the one-time codes (`codes.json`, 600, hashes only): an invite for 7 days, a password reset or an email check for 15 minutes, 8 wrong tries each. Joining checks the username and password before it uses up the invite.
- `matkon/mail.py` sends the invites and codes over SMTP with STARTTLS (`mail.json`; `MATKON_MAIL=outbox` writes them to `outbox.jsonl` instead, for tests). "Forgot password" answers the same whether or not the email has an account.
- `matkon/kitchen.py` says whose Instagram feeds the kitchen: each account's own `users/<id>/cookies.txt` and `instagram.json`, and for the owner, `MATKON_COOKIES` and `settings.json` as a fallback.
- `matkon/memory.py` is each account's memory (`users/<id>/memory.json`), the run log (`runs.jsonl`) and `suggest`, which ranks the kitchen for one account from what it saved, cooked, rated and opened.
- `matkon/server.py` serves the app, the JSON and the media, with byte ranges for Safari's video player. Everything but the app's own files needs an account, and every change is a POST with JSON and an `X-Matkon: 1` header. Settings actions that take a while (finding collections, adding a reel, "Check now") run `run.py` in the background.
- `app/` is plain JS with no build step.

## A reel's folder

`<state>/reels/<code>/` holds `post.json`, `cover.jpg`, `video.mp4`, `transcript.json`, `sheets/` + `sheets.json`, `linked.json`, `answer.txt`, `recipe.json`, `photo.jpg`, `note.json` (the stage marker), `vault-note.json` (what was written, for the edit check), `recipe.en.json` + `translated.json` (the English version, and its stage marker) and `status.json`. A run does whatever stages are missing, so deleting a file redoes that stage. A reel that fails 3 times waits until `redo`.

## Two traps

- **Frame times.** ffmpeg's fps filter gives each slot the last frame before its middle, so sheet frame k is really from k·step + step/2, less one frame (0.73 s for a 1.5 s step at 30 fps). `sheets.json` records those real times. With the slot's start time instead, the photo cut lands on whatever was there, often a camera whip.
- **Template defaults.** Claude copied a placeholder `"photo_at": 0` from the answer template. The template now asks for "one of the frame times," and `_seconds()` reads "27.0" as well as 27.

## When Instagram signs out

Matkon sends one message (`MATKON_NOTIFY ... now`) and then stays quiet until the sign-in works again. The app shows a line on the home page too.

## The pictures in the README

They all come from the demo, never from a real collection, since real recipes show other people's videos and faces.

1. `tools/demo.py [host] [port]` serves ten made-up recipes by made-up creators (`@….example`), with the public-domain photos in `tools/demo/photos` (credits in `tools/demo/CREDITS.md`) and a short clip made from each one in place of the reel.
2. `tools/shot.js` (Node 22+, for its built-in WebSocket) drives a headless Chrome over DevTools: `DEVTOOLS=host:port`, or `CHROME=<docker container>` to find one. Each shot gets a fresh browser context.
3. `tools/readme_images.py <shots dir>` (Pillow) puts the screens in device frames and builds `docs/images`.

```bash
python3 tools/demo.py 127.0.0.1 8519 &
node tools/shot.js http://127.0.0.1:8519/ /tmp/shots home:390x844 home-tab:1317x823 \
  "ramen:390x844:#/r/demo-ramen" "cookies-tab:1317x823:#/r/demo-cookies" "cook:390x844:#/cook/demo-pancakes/4" \
  "cook-dark:390x844:dark:#/cook/demo-ramen/1" "he:390x844:dark:#/r/demo-shakshuka" \
  "he-cook:390x844:dark:#/cook/demo-shakshuka/5" "missing:390x844:full:#/r/demo-spaghetti"
python3 tools/readme_images.py /tmp/shots
```

`how-it-works.svg` is drawn by hand.

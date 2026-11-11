# Developing Matkon

The notes I want when I come back to this later.

## Layout

- `matkon/config.py` holds the paths and settings. Everything about one particular setup comes from the env file (`MATKON_ENV`, else `private/matkon.env`, else `matkon.env`) and `settings.json`, never from the code.
- `extension/` is the browser extension, one of the two ways Matkon reaches Instagram (see "The two ways to Instagram" below). `content.js` runs on instagram.com: it asks `/api/v1/feed/saved/posts/` (newest save first, 21 a page) with the page's own sign-in and headers, keeps the posts whose `saved_collection_ids` has the account's collection, stops at the first one Matkon has, and asks `/api/v1/media/<pk>/info/` only for reels it didn't see in the list (the queue, or the collection page's links). `background.js` talks to Matkon with the key and fetches each video from Instagram's video servers. `build.sh` packs it for Chrome and Firefox, `sign.sh` has Mozilla sign the Firefox one, and `node extension/test.mjs` runs the real scripts against a pretend Instagram and a throwaway Matkon.
- `matkon/instagram.py` turns a post as Instagram gives it into what Matkon keeps (`post.json`), and holds what both ways share: a code's number (base 64), the video to take, and reading a pasted sign-in (a Cookie header, cookies.txt, or a cookie-export JSON). It makes no requests.
- `matkon/igserver.py` is the other way: the server's own look, for an account that pasted a sign-in (`users/<id>/sign-in.json`, mode 600: the cookies, the browser's User-Agent and languages, `checked`, `error`, `wait_until`, `brought`). It runs from `sync` (cron, daytime only) as `run.py instagram`, in `MATKON_IG_PY` (`.venv-ig`), because it needs curl_cffi: each request takes the TLS and HTTP/2 shape of the browser the sign-in came from (`target()` picks the nearest curl_cffi browser from the User-Agent), with the website's headers, `X-IG-WWW-Claim` and the cookies Instagram sets kept between runs. The same steps as the extension: `check_hours`, `scan_pages`, `per_hour`, stopping at the first known reel; signed-out waits for a new sign-in, busy waits a day. The app sees only `added`, `checked` and `error`. `python3 tools/test_igserver.py` runs it against a pretend Instagram (`MATKON_IG_ORIGIN`).
- `matkon/store.py` is the reel folders: a post, then its video, then the stages. A post with no video is "wanted", and the extension brings it.
- `matkon/reel.py` handles the frames (one every 1.5 s, 32 at most, four to a 2×2 sheet at 432 px), the transcript (`tools/whisper_segments.py`, run with `MATKON_PY`) and the dish photo.
- `matkon/linked.py` fetches the caption's link once, as itself (no disguise). It keeps the page's schema.org Recipe when there is one, and the page's text when there isn't. A Substack front page gets an archive search for the dish.
- `matkon/recipe.py` holds the prompt and the call: `claude --print` with `--tools ""`, the frames sent inline in one stream-json message, and the answer cleaned into a fixed shape. Claude's raw answer is kept as `answer.txt`.
- `matkon/translate.py` makes the English version of a Hebrew recipe (`recipe.en.json`), the last stage of a reel's run, so a hiccup there never holds up the recipe or the note. Claude gets the recipe JSON and gives back the same JSON in English; the timers are put back from the original, and anything whose groups, items, steps, tips or "missing" lines don't line up is thrown away and tried again. The server serves either language (`api/r/<code>?lang=en`), the account's "Hebrew recipes in English" switch picks the default, and the list carries `title_en` and `items_en` for cards and search.
- `matkon/cookbook.py` copies each recipe to Nextcloud Cookbook over WebDAV (optional): a folder named after it with `recipe.json` (schema.org, ingredient groups as `## ` lines, times as ISO durations) and `full.jpg`, then Cookbook's `api/v1/reindex`. `cookbook.json` in the state folder records each reel's folder and a signature of its files' mtimes, so a recipe goes again only when Matkon's copy changes; a rename moves the folder. `sync` and `redo` end with it, and `run.py cookbook` runs it alone.
- `matkon/vault.py` writes the note. It compares only the BODY to what Matkon wrote last (`vault-note.json`), because Obsidian's plugins rewrite front matter on their own.
- `matkon/accounts.py` holds the accounts (scrypt hashes in `accounts.json`, 600) and the signed cookie, which carries an epoch so a new password signs that account out everywhere. It also keeps the one-time codes (`codes.json`, 600, hashes only): an invite for 7 days, a password reset or an email check for 15 minutes, 8 wrong tries each. Joining checks the username and password before it uses up the invite.
- `matkon/mail.py` sends the invites and codes over SMTP with STARTTLS (`mail.json`; `MATKON_MAIL=outbox` writes them to `outbox.jsonl` instead, for tests). "Forgot password" answers the same whether or not the email has an account.
- `matkon/kitchen.py` says whose Instagram feeds the kitchen: each account's collection (`users/<id>/instagram.json`, and for the owner, `settings.json` as a fallback) and its browser key (`users/<id>/browser.json`, the key's hash only, with when the browser last said hello, which version, and what Instagram said if it said no).
- `matkon/memory.py` is each account's memory (`users/<id>/memory.json`), the run log (`runs.jsonl`) and `suggest`, which ranks the kitchen for one account from what it saved, cooked, rated and opened. The week plan (`plan-add`, `plan-move`, `plan-remove`) and the shopping list (`shop-add`, `shop-tick`, `shop-remove`, `shop-clear`) live there too, for the [Android app](android-app.md); an app may send its own 8-hex ids for new entries, so what it made offline keeps the same id once it reaches the server.
- `matkon/server.py` serves the app, the JSON and the media, with byte ranges for Safari's video player. Everything but the app's own files needs an account, and every change is a POST with JSON and an `X-Matkon: 1` header. `/api/ext/*` is the extension's: `hello` (the account's collection, the pace, and the queue), `seen` (which of these codes Matkon wants), `post` (a reel's post, or why Instagram can't give it), `PUT video/<code>` (its video, checked with ffprobe; a run starts right away) and `collection`. They take the key in `X-Matkon-Key` instead of the cookie.
- `app/` is plain JS with no build step.

## A reel's folder

`<state>/reels/<code>/` holds `post.json`, `video.mp4` (and `cover.jpg` on reels from before the extension), `transcript.json`, `sheets/` + `sheets.json`, `linked.json`, `answer.txt`, `recipe.json`, `photo.jpg`, `note.json` (the stage marker), `vault-note.json` (what was written, for the edit check), `recipe.en.json` + `translated.json` (the English version, and its stage marker) and `status.json`. A run does whatever stages are missing, so deleting a file redoes that stage. A reel that fails 3 times waits until `redo`.

## Two traps

- **Frame times.** ffmpeg's fps filter gives each slot the last frame before its middle, so sheet frame k is really from k·step + step/2, less one frame (0.73 s for a 1.5 s step at 30 fps). `sheets.json` records those real times. With the slot's start time instead, the photo cut lands on whatever was there, often a camera whip.
- **Template defaults.** Claude copied a placeholder `"photo_at": 0` from the answer template. The template now asks for "one of the frame times," and `_seconds()` reads "27.0" as well as 27.

## The two ways to Instagram

The first version read the saved posts and downloaded the videos (yt-dlp) on the server, with a copy of the owner's Instagram sign-in. On its first day it paged through every save twice and downloaded about sixty reels in two hours, all from a Python client calling itself Safari, while the real browser used the same sign-in. Instagram took that for a stolen sign-in: it cut the session off, then locked the account for a day until the passwords were changed.

So there are two ways now. The extension asks only what the website itself asks, from the browser the sign-in belongs to, while someone is actually on instagram.com; with it, the server makes no request to Instagram and holds no sign-in. Or an account pastes a sign-in, and `igserver.py` looks from the server, which fixes each thing that went wrong the first time: a sign-in made for Matkon alone (so one session is never in two places), the browser's own TLS, User-Agent and languages (curl_cffi), the same slow pace as the extension (`check_hours`, `scan_pages`, `per_hour` in `settings.json`, only from the daytime cron), and a full stop at the first refusal. A browser whose account has a sign-in is told it's paused, so the two never both look. Don't make the server's way any faster or louder than the extension.

## When Instagram says no

The extension stops at the first refusal (a sign-in page, a 401 or 403, or a 429), says hello with the error, and waits for the next check. The server's look stops the same way, harder: after a sign-in page (or `login_required`, `checkpoint_required`, `challenge_required`) it does nothing until a new sign-in is pasted, after a 429 or `feedback_required` it waits a day, and after anything else three hours. Settings and the home page show it.

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

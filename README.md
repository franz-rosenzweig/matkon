# Matkon

Matkon (מתכון, Hebrew for "recipe") turns the cooking reels you save on Instagram into real recipe pages. I save cooking reels to a "Recipes" collection, and the recipe is always spread across a fast video, a caption and "comment RECIPE for the link." Now I save a reel the way I always do, and within the hour it's a page with the ingredients, the amounts, the steps and the reel itself, plus a note in my Obsidian vault.

It's made for one person running it for themselves, on their own computer or server.

## How it works

Every run, Matkon looks at your newest saved posts and picks out the ones in your recipe collection. For each new reel it:

1. downloads the video with yt-dlp, using your own Instagram sign-in (a cookies file),
2. writes out what's said with faster-whisper,
3. takes a frame every second and a half, so the words on screen can be read,
4. follows the link in the caption when there is one ("full recipe on my blog"), since that's usually where the amounts are, and if the link goes to a Substack's front page, it searches that Substack for the dish,
5. hands all of that to Claude (through Claude Code, with no tools at all), which writes the recipe,
6. picks a still of the finished dish for the photo, and writes the note.

The one rule that matters: **only what the reel gives**. If the creator never says how much flour, the page says "no amount" and lists it under "Not in the reel." Claude never guesses an amount, a time or a temperature, and calories and protein show up only when the reel says them. Hebrew reels stay in Hebrew and everything else comes out in English.

## The app

- **Home:** every recipe, newest first, with search (it searches the ingredients too) and kinds (Mains, Baking & sweets…).
- **A recipe:** the photo, with the reel one tap away, the ingredients to tick off, the steps with timers, the tips, and the creator's account and recipe page.
- **Cooking:** one step at a time, in big letters, with that step's amounts right under it, a timer that keeps going if the page reloads, and read-aloud.

Hebrew recipes get Hebrew labels and run right to left. It's plain HTML and JS, works on a phone, a tablet and a computer, and follows the system's light or dark mode.

## Setting it up

You need Python 3.11 or newer, ffmpeg, and [Claude Code](https://claude.com/claude-code) signed in on the same machine.

```bash
git clone https://github.com/franz-rosenzweig/matkon && cd matkon
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Then make a `matkon.env` next to `run.py` (it's ignored by git). Everything in it is optional except the cookies:

```bash
MATKON_COOKIES=/path/to/instagram-cookies.txt   # a Netscape cookies.txt from a browser signed in to Instagram
MATKON_STATE=~/.local/share/matkon              # where the videos, frames and recipes go
MATKON_VAULT=~/Obsidian/MyVault                 # an Obsidian vault for the notes (leave out for no notes)
MATKON_HOSTS=127.0.0.1                          # where the app answers; add a private address to use it from your phone
MATKON_PORT=8510
MATKON_MODEL=                                   # a Claude model id, or leave it to Claude Code's default
MATKON_NOTIFY=                                  # a command to tell you things: CMD "Matkon" "message" [now]
```

Any browser extension that exports cookies.txt will do for the cookies file. Then find your recipe collection. Instagram doesn't hand out collection names anymore, so this lists each collection's id with a few of its captions:

```bash
python3 run.py collections
python3 run.py collection <id> Recipes
python3 run.py sync --full      # the first run looks through ALL your saved posts
python3 run.py serve            # the app, at http://127.0.0.1:8510
```

After that, run `python3 run.py sync` every hour or so (cron is fine), which only looks at your newest saves. The other settings (the vault folders, a tag for the notes, the app's address for the link in each note) are in `settings.json` in the state folder.

| Command | What it does |
| --- | --- |
| `sync [--full] [--limit N]` | reads the collection and works through new reels |
| `add <reel link>` | one reel, even one that isn't in the collection |
| `redo <code> [--from STAGE]` | makes it again from `video`, `transcript`, `frames`, `link`, `recipe` or `note` |
| `status` | what's where |
| `serve` | the app |

## The vault notes

Each note follows the usual Obsidian recipe shape (categories `[[Recipes]]`, cuisine, type, ingredients, author, url, image, rating, cooked), so a Bases view over `[[Recipes]]` lists them, and has `matkon: <code>` in its front matter, which is how Matkon finds it again, even after you move it.

Once you edit a note's text in Obsidian, it's yours and Matkon leaves it alone. Matkon only rewrites a note whose body is still exactly what it wrote, and even then it keeps the front matter, so your `rating` and `cooked` stay. If a note with the same name is already there, the new one gets the creator's name after it.

## A few honest notes

- Matkon reads Instagram the way its own website does, with your own sign-in. That isn't an official API, so it can break when Instagram changes things, and it's kept gentle on purpose (a few pages, a few seconds apart).
- The pages hold other people's videos and recipes, so keep the app to yourself. It has no login, so it should only answer on your own machine or a private network, never the open internet.
- The creators did the cooking. Every page links back to the reel and to the creator's own recipe page.

## License

MIT. See [LICENSE](LICENSE). How the code fits together is in [docs/DEVELOPING.md](docs/DEVELOPING.md).

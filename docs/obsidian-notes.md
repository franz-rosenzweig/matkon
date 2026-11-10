<sub>[Matkon docs](README.md) › How it works</sub>

# Obsidian notes

When the owner gives Matkon an Obsidian vault, every recipe also becomes a note in it, next to the recipes already there, so a Bases view of your Recipes lists them with everything else.

## What's in a note

The front matter is the usual recipe kind, so a Bases view picks it up:

| Key | What it holds |
| --- | --- |
| `categories` | `[[Recipes]]` |
| `cuisine`, `type` | the cuisine, and the kind plus a few tags |
| `ingredients` | the three to six main ingredients |
| `author` | the creator's account |
| `url` | the reel |
| `image` | the photo, saved in the photos folder |
| `rating`, `cooked`, `last` | the owner's rating, whether they've made it, and when they last did |
| `tags` | `recipes` and `instagram-reels` |
| `matkon` | the reel's code, which is how Matkon finds the note again |

The body has the photo, the facts (serves, times, oven), the ingredients, the steps (numbered), the tips, the nutrition when the reel gives it, **Not in the reel**, the links to the reel, the creator's page and the recipe in Matkon, and a **Notes** heading at the end. A Hebrew recipe's note is in Hebrew, with Hebrew headings. A tag of your choice can go on its own line above the title (Settings › Kitchen).

## What Matkon will and won't change

- **The note is found by its `matkon:` line,** wherever you've moved it.
- **Once you edit the body, it's yours.** Matkon only rewrites a note while its body is still exactly what Matkon wrote, and leaves it alone the moment you change a word.
- **The front matter stays yours.** Obsidian's plugins reformat front matter on their own (quotes, an `updated:` line), so Matkon never judges a note by it and keeps it as it is when it refreshes the body.
- **Your rating, cooked and last** are the only front matter keys Matkon writes, whenever you rate or make a recipe in the app.
- **Your notes from the app** go under the Notes heading, while the body is still Matkon's.
- **A note with the same name already there** (say you already wrote your own Shakshuka) stays put, and Matkon's comes in as "Shakshuka (@the.creator)" next to it.

Only the owner's memory goes into the notes, since the vault is theirs. Everyone else's stays in Matkon.

Next: [Nextcloud Cookbook](nextcloud-cookbook.md)

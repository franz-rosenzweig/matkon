<sub>[Matkon docs](README.md) › How it works</sub>

# Nextcloud Cookbook

Matkon can keep a copy of every recipe in [Nextcloud Cookbook](https://apps.nextcloud.com/apps/cookbook), the recipe app for Nextcloud. I run Nextcloud anyway, and Cookbook has free, open-source phone apps for Android and the iPhone, so my recipes are on my phone even when Matkon isn't in reach, along with the shopping lists and meal plans those apps have.

## What goes over

Each recipe becomes a folder in Cookbook's Recipes folder, named after the dish, with the recipe and its photo:

- the name, and the summary as the description, with the oven, the tips and what's "Not in the reel" under it
- the ingredients, with each group's name as a heading
- the steps
- the prep, cook and total times, and how many it serves, when the reel says
- the kind as Cookbook's category, and the tags and cuisine as its keywords
- the reel's link, and the creator's account

A Hebrew recipe goes over in Hebrew, unless the owner has "Hebrew recipes in English" on, and then it goes over in English. Reels that aren't recipes stay out.

## Matkon's copy wins

It only goes one way. Matkon sends a recipe when it's new, and again only when Matkon's own copy changes (when a recipe is redone, say), so:

- a recipe you delete in Cookbook stays deleted
- an edit you make in Cookbook lasts until Matkon redoes that recipe, and then Matkon's version replaces it
- a recipe Matkon no longer has, or that turned out not to be a recipe, is taken out of Cookbook too
- a folder of the same name that Matkon didn't make is left alone, and Matkon's comes in as "Name (2)" next to it

Your ratings, notes and what you cooked stay in Matkon. So do cooking mode and its timers, and the switch between Hebrew and English.

## When it happens

Every run after a reel comes in sends whatever changed, so a new recipe is in Cookbook a minute after it's in Matkon. If Nextcloud is away, the recipe waits for the next run. `python3 run.py cookbook` sends whatever changed right away.

## Setting it up (the owner)

1. In Nextcloud, install **Cookbook** from the apps.
2. Make an app password for Matkon: **Settings › Security › Devices & sessions**, name it Matkon, and **Create new app password**.
3. Put your Nextcloud username and that password in a file on the server, as `username:password`, readable only by you.
4. Tell Matkon where they are, in its env file:

```bash
MATKON_COOKBOOK=https://your-cloud/remote.php/dav/files/<username>/Recipes
MATKON_COOKBOOK_LOGIN=/path/to/that/file
```

The folder is Cookbook's own (Recipes, unless you changed it in Cookbook's settings). Then `python3 run.py cookbook` sends everything that's already in.

To stop it, take those two lines out. What's already in Cookbook stays. Deleting the Matkon app password in Nextcloud cuts it off too.

## On your phone

The Cookbook apps sign in to your Nextcloud and read the same recipes:

- **Android:** [Nextcloud Cookbook](https://f-droid.org/packages/de.micmun.android.nextcloudcookbook/) on F-Droid. It can sign in through the Nextcloud app.
- **iPhone and iPad:** [Cookbook Client](https://apps.apple.com/app/id6467141985), or [AvoCook](https://apps.apple.com/app/id6769012665), which keeps the recipes on the phone for when there's no connection.

Next: [Developing and running it](DEVELOPING.md)

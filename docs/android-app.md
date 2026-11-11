<sub>[Matkon docs](README.md) › Using it</sub>

# The Android app

Matkon has its own Android app, for a phone or a tablet. It reads the same recipes from the same Matkon, and it's made for the kitchen: the screen stays on while I cook, timers ring like an alarm clock, and every recipe is kept on the device so it still works where the Wi-Fi doesn't reach.

It started as a fork of [Nextcloud Cookbook for Android](https://github.com/lneugebauer/nextcloud-cookbook), Lukas Neugebauer's open-source app, and was rebuilt for Matkon's recipes. The code is at [matkon-android](https://github.com/franz-rosenzweig/matkon-android).

## Getting it

The app comes from the repository's GitHub Releases. The easiest way is [Obtainium](https://github.com/ImranR98/Obtainium), which keeps it up to date: add an app and paste `https://github.com/franz-rosenzweig/matkon-android`. Or download the newest APK from the [releases page](https://github.com/franz-rosenzweig/matkon-android/releases/latest) and open it.

The first screen asks for three things: Matkon's address (the one you open in a browser), and your Matkon username or email and password. That's the same account as on the web, so everything you've saved, rated and made is already there.

## What's in it

**Home** shows what's planned for today, Up next, the rest of the week, and what was added and made lately. The **+** at the top adds a reel by its link.

**Recipes** is the whole kitchen, with search, the kinds, Saved and Made. The sliders button sorts by when a reel was added or posted, by name, by rating or by what you made last, and filters to one creator. Tapping @creator on a recipe does the same.

**A recipe** has everything the web page has: the photo and the reel's own video, both languages for a Hebrew recipe (the English or עברית button at the top), the dates, the ingredients to tick off, the steps, the tips and what's "Not in the reel." Under **Amounts** it can be halved, doubled or tripled. Every number in an amount changes, so "2 portions (about 200g)" becomes "4 portions (about 400g)", and an amount without a number, like "salt to taste," stays as it is. At the bottom are the rating, the note and **I made it**, the same ones the web app keeps.

**Cook mode** is **Start cooking**: one step at a time in big type, with the ingredients that step uses and their amounts. Swipe or use Back and Next. The ingredient list is one tap away on a phone, and on a tablet on its side it sits next to the step. The step you're on and what you've ticked are remembered, on every device, for twelve hours.

**Timers** come from the steps themselves. When a step says "bake 25 minutes," there's a 25-minute button. A running timer shows at the bottom of every screen and in the notifications, and when it's done it rings like an alarm clock until you stop it, even if the phone is asleep or you're in another app. The first time, the app asks to send notifications; say yes, or the alarm can't show.

**Week** has this week and next, starting on Sunday. Put a recipe on a day with **Plan** on the recipe, or with the **+** next to a day. The cart button at the top puts every recipe from today to the end of the week onto the shopping list.

**List** is the shopping list. **Add to list** on a recipe puts its ingredients on it at the amounts you're looking at, and the same thing from different recipes is added up where the units agree ("1 cup" and "½ cup" of rice become "1½ cups"). Tap a line to tick it off, type at the top to add something that isn't from a recipe, and share the list as text from the top bar.

The week plan and the shopping list live on the Matkon server, under your account, so they're the same on the phone, the tablet and the web app (its [Week and List](week-and-list.md) pages), and on anyone else's device signed in to your account.

## Everything else the web has

Since 0.2.0 the app has the same newer features as the web, so the pages for the web describe them for the phone too:

- **Units** (as written, metric or US) in Settings. See [Units](recipes.md#units).
- **Fix this recipe**, **Share a link**, **Print** and **Collections** in a recipe's menu (the three dots). See [Fixing a recipe](recipes.md#fixing-a-recipe), [Sharing a recipe](recipes.md#sharing-a-recipe) and [Printing](recipes.md#printing). Printing goes through Android's own print screen, which can also save a PDF.
- **Ask** at the bottom of a recipe. See [Asking about a recipe](recipes.md#asking-about-a-recipe).
- **What can I make?** and **Surprise me** on Home, and a search that reads the steps and forgives a typo. See [What can I make?](recipes.md#what-can-i-make).
- **I made it** asks for the amounts and a note, the recipe offers **Again, like last time**, and **History** has the calendar. See [Memory and history](memory-and-history.md).
- The shopping list sorts itself by aisle (the tag on a line moves it), and a planned recipe moves to another day by holding it and dragging. See [The week and the shopping list](week-and-list.md).
- The **+** adds a reel, any recipe page, or up to four photos of a recipe. See [Adding recipes](adding-recipes.md).
- **Download all recipes** in Settings saves every recipe as one file, wherever you pick.

## Sharing a reel from Instagram

In the Instagram app, tap Share on a reel and pick **Matkon**. The app adds it to the queue and says "Added," "Already on the way" or "Already in Matkon." A recipe page shared from the browser, or photos shared from the gallery, come in the same way.

## Without a connection

Every recipe, both of its languages and its photo stay on the device, and they're refreshed each time the app opens. With no connection, everything still opens, and whatever you change (ticks, the plan, the list, a note, I made it) waits on the device and goes to Matkon in order as soon as it answers. The reel videos aren't kept, so those need a connection.

## Settings

The gear (in the side rail on a tablet) has your account, **Hebrew recipes in English** and **Calories and protein**, which are the same switches as on the web, how many recipes are kept on the device, **Refresh**, and **Sign out**, which also clears what the app kept.

Next: [Settings](settings.md)

<sub>[Matkon docs](README.md) › Using it</sub>

# The browser extension

The extension is how saved reels get from Instagram into Matkon. It lives in your own browser, and it's the only part of Matkon that ever talks to Instagram.

## Why it works this way

The first version did it all on the server. Matkon read my saved posts and downloaded the reels itself, using a copy of my Instagram sign-in. Instagram saw that sign-in being used from my browser and from a server at the same time, and on the first day the server did far more than any person would, going through every save I had and downloading sixty videos in a couple of hours. So Instagram decided someone had broken into my account. It locked me out for a day, and I had to change my passwords.

So now the server never asks Instagram for anything. The extension does that part from my own browser, signed in as me, while I'm on instagram.com anyway, and it asks only for what the website itself asks for when I use it. To Instagram it just looks like me, looking at my own saves.

## What it does

- **Looks at your newest saves,** a little while after you open Instagram, only while the tab is in front of you, and only when it's been a while (six hours, unless the owner changes it). It reads the newest page or two of your saved posts, the same list the website loads when you open them, and stops as soon as it reaches a reel Matkon already has.
- **Sends Matkon what's new** in your recipe collection: first the post (who made it and the caption), then the video, the same file the page plays. That's a few an hour at most, half a minute or so apart, and the rest come next time.
- **Picks up older saves** when you open your recipe collection's own page on instagram.com: the reels you scroll past that Matkon doesn't have yet come in too.
- **Stops when Instagram says no.** If Instagram wants you to sign in again, or asks for a break, the extension stops right there until the next check, and Matkon's Settings says so.

Your Instagram sign-in never leaves the browser. The extension can't even read it: it only asks Instagram the way the page would, and it sends Matkon the post and the video, nothing else.

## Setting it up

1. In Matkon, open **Settings › Instagram** and download the extension for your browser. **Firefox or Zen** installs straight from the link. For **Chrome** (Arc and Edge work too), unzip it, open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked**, and pick the folder.
2. Tap **Connect a browser**, then **Copy**. That copies one line with Matkon's address and a key for this browser.
3. Click the Matkon button in the browser's toolbar, then **Settings**. Paste the line into **Connection** and click **Save**. The browser asks whether the extension may use Instagram and your Matkon; say yes. It says "Connected" with your name.
4. Open your recipe collection on instagram.com, click the Matkon button, and click **Use this collection**. (The owner's collection is set already.)

A new connection stops the old one, so if you lose the line, make another. **Disconnect** turns the key off.

## The toolbar button

It says whether the extension is connected and when it last looked, and on Instagram it has:

- **Check now:** looks at your newest saves right away, instead of waiting.
- **Send this reel,** on a reel's own page: brings that reel in, even one that isn't in your collection.
- **Use this collection,** on one of your saved collections: makes it the one Matkon reads for you.

**Add a reel** in Matkon's Settings works too, and so does sharing a reel to Matkon from an Android phone: the reel waits in the kitchen's queue, and the extension brings it the next time any connected browser is on Instagram.

## Turning it off

The owner's **Check Instagram** switch (Settings › Kitchen) makes every connected browser leave Instagram alone until it's on again. Or just remove the extension. The recipes already in Matkon stay.

It doesn't come in a Safari version yet.

Next: [Settings](settings.md)

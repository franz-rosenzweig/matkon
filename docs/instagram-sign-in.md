<sub>[Matkon docs](README.md) › Using it</sub>

# Instagram sign-in on the server

There are two ways for saved reels to get into Matkon. The [browser extension](browser-extension.md) looks at Instagram from your own browser while you're on instagram.com. Or you paste an Instagram sign-in (its cookies) into Matkon's Settings, and the server looks by itself. Then nothing needs a browser open: reels come in on their own during the day, and a reel shared from your phone comes in within a minute or two.

## The trade-off

This is the riskier of the two, and I want to be honest about why. The first version of Matkon worked this way, and in November Instagram locked my account for a day over it. The server used the same sign-in my browser was using, from a program that didn't look like any browser, and on its first day it went through every save I had and downloaded sixty videos in two hours. Instagram took that for someone who had stolen my sign-in.

So this time it's built to look as little like that as it can:

- **Its own sign-in.** You sign in once in a private window just for Matkon, and nothing else ever uses that sign-in. Instagram sees one more device, which only ever does what Matkon does, instead of one sign-in in two places at once.
- **It dresses as your browser.** Each request looks like the browser you signed in with, down to how it connects, with the same browser name and languages, and the same headers the website itself sends. Cookies Instagram changes along the way are kept, the way a browser keeps them.
- **It's slow.** It looks at your newest saves, a page or two, every six hours, and stops as soon as it reaches a reel Matkon already has. It brings in a few videos an hour at most, half a minute or so apart. It looks only during the day, or right after you share or add a reel yourself.
- **It stops at the first no.** If Instagram wants you to sign in again, it stops completely until you paste a new sign-in. If Instagram asks it to slow down, it rests for a whole day. Settings and the home page tell you either way.

It's still automation on your account, which is against Instagram's rules, so it's yours to decide. If Instagram ever asks you to confirm it's you, or locks you out, forget the sign-in in Settings and go back to the extension.

## Pasting a sign-in

These steps are for Zen or Firefox on the Mac. Other browsers are much the same.

1. Open a **private window** (File › New Private Window) and sign in to instagram.com there.
2. Open the developer tools (**⌥⌘I**) and pick the **Network** tab. Reload the page.
3. Click the first line in the list, the one for `www.instagram.com`. Under **Request Headers**, find **Cookie**, right-click it and **Copy Value**.
4. In a normal window of the **same browser**, open Matkon's **Settings › Instagram**, paste it into **Cookies**, and **Save**. Matkon notes which browser you pasted it from, and that's the one the server looks like.
5. Close the private window **without signing out**. Signing out would end the sign-in Matkon uses.

A cookies.txt file from a cookie-export extension works too: paste the whole file.

Then tell Matkon which collection is your recipes: open it on instagram.com, copy its address (it ends in a long number), and paste it into **Collection** in the same place. The owner's is set already.

## What happens then

The line at the top of Settings › Instagram says "Waiting for the first check," then when it last looked. The first look comes with the next run, within the hour. The Kitchen's **Check Instagram** switch stops it, just like it stops the extension.

While the server looks for you, a connected browser leaves Instagram alone, so the two never both do it.

- **Replace** puts in a new sign-in, after Instagram asked you to sign in again, say.
- **Forget** deletes it from the server. The extension takes over again if you have one connected.

The cookies stay on the server, in a file only Matkon can read. They're never shown in the app, and never sent anywhere but Instagram.

Next: [Settings](settings.md)

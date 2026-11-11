#!/usr/bin/env python3
"""The pictures in docs/images, from screenshots of the demo (tools/demo.py + tools/shot.js):
screens get a device frame and a soft shadow, and the hero puts a tablet between two phones.

  python3 tools/readme_images.py <shots dir>      needs Pillow
The shots it expects: home, ramen, cook, cook-dark, he, he-cook, home-tab, cookies-tab, missing (full),
cookies-full (full), history, imported, cookdone, settings (full), and for docs/: signin, join, he-en.
"""
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"


def rounded(img, r):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width - 1, img.height - 1], r, fill=255)
    img = img.convert("RGBA")
    img.putalpha(mask)
    return img


def device(screen, bezel, radius, color=(28, 27, 26)):
    """The screen inside a dark rounded frame."""
    inner = rounded(screen, radius)
    w, h = inner.width + 2 * bezel, inner.height + 2 * bezel
    frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle([0, 0, w - 1, h - 1], radius + bezel, fill=color + (255,))
    frame.alpha_composite(inner, (bezel, bezel))
    return frame


def shadowed(img, blur=40, offset=(0, 24), alpha=70):
    pad = blur * 3
    out = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    a = img.split()[3].point(lambda v: v * alpha // 255)
    sh.paste((20, 16, 10, 255), (pad + offset[0], pad + offset[1]), a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(sh)
    out.alpha_composite(img, (pad, pad))
    return out, pad


def phone(path, height):
    s = Image.open(path).convert("RGB")
    if s.height > s.width * 2.3:                      # a full-page shot: its first screen
        s = s.crop((0, 0, s.width, round(s.width * 844 / 390)))
    s = s.resize((round(s.width * height / s.height), height), Image.LANCZOS)
    return device(s, bezel=round(height * 0.018), radius=round(height * 0.05))


def tablet(path, width):
    s = Image.open(path).convert("RGB")
    s = s.resize((width, round(s.height * width / s.width)), Image.LANCZOS)
    return device(s, bezel=round(width * 0.016), radius=round(width * 0.018))


def save(img, name, width=None):
    if width and img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    img.save(OUT / name, optimize=True)
    print(name, img.size)


def main():
    shots = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)

    # hero: a tablet between two phones, on a warm ground
    W, H = 3000, 1640
    hero = Image.new("RGBA", (W, H))
    top, bottom = (248, 244, 237), (236, 227, 213)
    for y in range(H):
        t = y / (H - 1)
        ImageDraw.Draw(hero).line([(0, y), (W, y)], fill=tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    tab, p = shadowed(tablet(shots / "cookies-tab.png", 2000), blur=50, offset=(0, 30))
    hero.alpha_composite(tab, ((W - tab.width) // 2, 150 - p))
    left, p = shadowed(phone(shots / "home.png", 1300), blur=46, offset=(0, 28), alpha=90)
    hero.alpha_composite(left, (150 - p, 250 - p))
    right, p = shadowed(phone(shots / "cook-dark.png", 1300), blur=46, offset=(0, 28), alpha=90)
    hero.alpha_composite(right, (W - 150 - right.width + p, 250 - p))
    hero = rounded(hero.convert("RGB"), 48)
    save(hero, "hero.png", 1800)

    # four phones in a row
    names = ["home", "ramen", "cook", "he"]
    ph = [shadowed(phone(shots / f"{n}.png", 1200), blur=30, offset=(0, 16), alpha=60) for n in names]
    gap = 40 - 2 * ph[0][1]          # the shadows' margins overlap; the phones keep 40 px between them
    row = Image.new("RGBA", (sum(i.width for i, _ in ph) + gap * (len(ph) - 1), max(i.height for i, _ in ph)), (0, 0, 0, 0))
    x = 0
    for img, _ in ph:
        row.alpha_composite(img, (x, 0))
        x += img.width + gap
    save(row, "phones.png", 1800)

    # memory and history: what was cooked, what came in, rating and notes after cooking, settings
    names = ["history", "imported", "cookdone", "settings"]
    ph = [shadowed(phone(shots / f"{n}.png", 1200), blur=30, offset=(0, 16), alpha=60) for n in names]
    gap = 40 - 2 * ph[0][1]
    row = Image.new("RGBA", (sum(i.width for i, _ in ph) + gap * (len(ph) - 1), max(i.height for i, _ in ph)), (0, 0, 0, 0))
    x = 0
    for img, _ in ph:
        row.alpha_composite(img, (x, 0))
        x += img.width + gap
    save(row, "memory.png", 1800)

    # the "Mine" box on a recipe: made it, rating, notes
    c = Image.open(shots / "cookies-full.png").convert("RGB")
    c = c.crop((0, 4780, c.width, min(c.height, 5520)))
    card, _ = shadowed(rounded(c, 40), blur=26, offset=(0, 14), alpha=55)
    save(card, "mine.png", 700)

    # Hebrew, right to left
    he = [shadowed(phone(shots / f"{n}.png", 1200), blur=30, offset=(0, 16), alpha=60)[0] for n in ["he", "he-cook"]]
    step = he[0].width - 2 * 90 + 40
    pair = Image.new("RGBA", (he[0].width + step, he[0].height), (0, 0, 0, 0))
    pair.alpha_composite(he[0], (0, 0))
    pair.alpha_composite(he[1], (step, 0))
    save(pair, "hebrew.png", 900)

    # the tablet home page
    t, _ = shadowed(tablet(shots / "home-tab.png", 2200), blur=40, offset=(0, 22), alpha=60)
    save(t, "tablet.png", 1800)

    # a recipe the reel doesn't finish: its ingredients with no amounts, and "Not in the reel"
    m = Image.open(shots / "missing.png").convert("RGB")
    m = m.crop((0, 1580, m.width, min(m.height, 3880)))
    card, _ = shadowed(rounded(m, 40), blur=26, offset=(0, 14), alpha=55)
    save(card, "missing.png", 700)

    # single phones for the guide pages in docs/
    for name, out in [("signin", "signin.png"), ("join", "join.png"), ("cook", "cook.png"), ("he-en", "english.png"),
                      ("settings", "settings.png"), ("history", "history.png"), ("home", "home.png"),
                      ("week", "week.png"), ("list", "list.png")]:
        if (shots / f"{name}.png").exists():
            p, _ = shadowed(phone(shots / f"{name}.png", 1200), blur=30, offset=(0, 16), alpha=60)
            save(p, out, 520)

    shutil.copyfile(ROOT / "app" / "icon-512.png", OUT / "icon.png")
    print("icon.png")


if __name__ == "__main__":
    main()

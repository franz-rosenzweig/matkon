#!/usr/bin/env python3
"""Matkon over made-up recipes, for screenshots: ten dishes by made-up creators (@….example), with
public-domain photos (tools/demo/photos, see CREDITS.md) and a short clip made from each photo in
place of the reel. Nothing from a real collection. Every picture in docs/images comes from this.

  python3 tools/demo.py [host] [port]      default 127.0.0.1 8519
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = Path(__file__).resolve().parent / "demo" / "photos"


def g(name, *items):
    return {"name": name, "items": [{"amount": a, "item": i, "note": n} for a, i, n in items]}


def s(text, *timers):
    return {"text": text, "timers": list(timers)}


NONE = {"prep": "", "cook": "", "total": ""}
RECIPES = [
    dict(code="demo-ramen", user="noodles.example", photo="ramen", crop_x="iw-ow", title="15-Minute Miso Ramen",
         summary="A quick bowl of miso broth, springy noodles, a jammy egg and greens.", kind="Mains", cuisine="Japanese",
         tags=["weeknight", "noodles"], servings="2 bowls", time={"prep": "5 min", "cook": "10 min", "total": "15 min"}, oven="",
         ingredient_groups=[
             g("", ("2", "eggs", "at room temperature"), ("2 portions (about 200g)", "fresh ramen noodles", ""),
               ("3 cups (720ml)", "chicken or vegetable stock", ""), ("2 tbsp", "white miso", ""), ("1 tbsp", "soy sauce", ""),
               ("1 tsp", "toasted sesame oil", ""), ("1 clove", "garlic", "grated"), ("1 thumb", "ginger", "grated"),
               ("2 heads", "baby bok choy", "halved"), ("2", "spring onions", "sliced"))],
         steps=[s("Boil the eggs for 6½ minutes, then cool them in ice water and peel them.", 6),
                s("Bring the stock to a simmer with the garlic and ginger."),
                s("Whisk the miso with a ladle of the hot stock until smooth, then stir it back into the pot with the soy sauce and sesame oil. Don't let it boil again."),
                s("Cook the noodles and the bok choy together in boiling water for 2 minutes and drain.", 2),
                s("Split the noodles and bok choy between two bowls, pour over the broth, and top with the halved eggs and spring onions.")],
         tips=["Miso loses its flavour if it boils, so keep the broth just under a simmer once it's in."],
         nutrition={"per": "per bowl", "calories": "520", "protein": "27g", "carbs": "", "fat": "", "other": ""}),
    dict(code="demo-shakshuka", user="shuk.example", photo="shakshuka", lang="he", title="שקשוקה",
         summary="ביצים שמתבשלות ברוטב עגבניות ופלפלים חריף-מתקתק, במחבת אחת.", kind="Breakfast", cuisine="ישראלי",
         tags=["ארוחת בוקר", "מחבת אחת"], servings="4", time={"prep": "", "cook": "", "total": "35 דקות"}, oven="",
         ingredient_groups=[
             g("", ("2 כפות", "שמן זית", ""), ("1", "בצל", "קצוץ"), ("1", "פלפל אדום", "קצוץ"), ("3 שיני", "שום", "פרוסות"),
               ("1 כפית", "פפריקה מתוקה", ""), ("1 כפית", "כמון", ""), ("1 פחית (800 גרם)", "עגבניות מרוסקות", ""),
               ("1 כפית", "סוכר", ""), ("לפי הטעם", "מלח ופלפל", ""), ("6", "ביצים", ""), ("חופן", "פטרוזיליה", "קצוצה"))],
         steps=[s("מחממים את השמן במחבת רחבה ומטגנים את הבצל והפלפל עד שהם מתרככים, כ-8 דקות.", 8),
                s("מוסיפים את השום, הפפריקה והכמון ומערבבים דקה."),
                s("מוסיפים את העגבניות והסוכר, מתבלים ומבשלים על אש בינונית עד שהרוטב מסמיך, כ-15 דקות.", 15),
                s("עושים שש גומות ברוטב ושוברים ביצה לתוך כל אחת."),
                s("מכסים ומבשלים 6–8 דקות, עד שהחלבון מתייצב והחלמון עדיין רך.", 6, 8),
                s("מפזרים פטרוזיליה ומגישים עם לחם טרי.")],
         tips=["אם הרוטב סמיך מדי לפני הביצים, מוסיפים מעט מים."], nutrition={}),
    dict(code="demo-cookies", user="bakes.example", photo="cookies", title="Brown Butter Chocolate Chip Cookies",
         summary="Chewy cookies with nutty brown butter, pools of dark chocolate and flaky salt.", kind="Baking & sweets",
         cuisine="American", tags=["cookies", "chocolate"], servings="16 cookies", time={"prep": "20 min", "cook": "11 min", "total": ""},
         oven="180°C / 350°F", link="https://example.com/brown-butter-cookies",
         ingredient_groups=[
             g("", ("170g (¾ cup)", "unsalted butter", ""), ("150g (¾ cup)", "brown sugar", "packed"), ("50g (¼ cup)", "white sugar", ""),
               ("1", "egg", ""), ("1", "egg yolk", ""), ("2 tsp", "vanilla extract", ""), ("220g (1¾ cups)", "plain flour", ""),
               ("½ tsp", "baking soda", ""), ("¾ tsp", "salt", ""), ("200g", "dark chocolate", "roughly chopped"),
               ("to finish", "flaky salt", ""))],
         steps=[s("Melt the butter in a light-coloured pan and keep cooking, swirling, until it smells nutty and the bits at the bottom turn brown, about 5 minutes. Pour it into a bowl and let it cool for 10 minutes.", 5, 10),
                s("Whisk both sugars into the butter, then the egg, the yolk and the vanilla, until glossy."),
                s("Stir in the flour, baking soda and salt, then fold in the chocolate."),
                s("Scoop 16 balls onto two lined trays and bake at 180°C until the edges are golden but the middles look underdone, 10 to 12 minutes.", 10, 12),
                s("Sprinkle with flaky salt and let them set on the tray for 5 minutes.", 5)],
         tips=["Chilling the dough for 30 minutes makes them thicker."], nutrition={}),
    dict(code="demo-salad", user="kitchen.example", photo="salad", title="Greek Salad with a Feta Slab",
         summary="Tomatoes, cucumber and red onion with a whole slab of feta and oregano on top.", kind="Salads & sides",
         cuisine="Greek", tags=["no-cook", "summer"], servings="4 as a side", time={"prep": "", "cook": "", "total": "10 min"}, oven="",
         ingredient_groups=[
             g("", ("4", "ripe tomatoes", "cut in wedges"), ("1", "cucumber", "in thick half-moons"), ("½", "red onion", "thinly sliced"),
               ("1", "green pepper", "in rings"), ("a handful", "kalamata olives", ""), ("200g", "feta", "in one slab"),
               ("1 tsp", "dried oregano", ""), ("4 tbsp", "olive oil", ""), ("1 tbsp", "red wine vinegar", ""), ("a pinch", "salt", ""))],
         steps=[s("Put the tomatoes, cucumber, onion, pepper and olives in a wide bowl and season them with the salt."),
                s("Lay the feta on top in one piece."),
                s("Sprinkle the oregano over everything, then drizzle with the olive oil and vinegar. Don't toss it.")],
         tips=["Salt the tomatoes a few minutes ahead so they give up their juice for the dressing."], nutrition={}),
    dict(code="demo-spaghetti", user="pasta.example", photo="spaghetti", title="Garlicky Mushroom Spaghetti",
         summary="Spaghetti tossed with browned mushrooms, garlic butter, parsley and parmesan.", kind="Mains", cuisine="Italian",
         tags=["pasta", "vegetarian"], servings="", time=NONE, oven="", complete=False,
         ingredient_groups=[
             g("", ("", "spaghetti", ""), ("", "mixed mushrooms", "sliced"), ("", "butter", ""), ("", "garlic", "sliced"),
               ("", "parsley", "chopped"), ("", "parmesan", "grated"), ("", "salt and pepper", ""), ("a ladle", "pasta water", ""))],
         steps=[s("Cook the spaghetti in well-salted water."),
                s("Brown the mushrooms in a hot pan without moving them too much, then add the butter and garlic."),
                s("Add the drained spaghetti with a ladle of pasta water and toss until glossy."),
                s("Finish with parsley, parmesan and black pepper.")],
         tips=[], nutrition={},
         missing=["how much spaghetti and how many mushrooms", "how much butter and garlic", "how long to brown the mushrooms",
                  "how many it serves (the reel says to comment PASTA for the full recipe)"]),
    dict(code="demo-pancakes", user="stack.example", photo="pancakes", title="Fluffy Buttermilk Pancakes",
         summary="Tall, tender pancakes with crisp edges, made in one bowl.", kind="Breakfast", cuisine="American",
         tags=["brunch"], servings="about 12 pancakes", time={"prep": "10 min", "cook": "20 min", "total": ""}, oven="",
         ingredient_groups=[
             g("Dry", ("2 cups (250g)", "plain flour", ""), ("2 tbsp", "sugar", ""), ("2 tsp", "baking powder", ""),
               ("½ tsp", "baking soda", ""), ("½ tsp", "salt", "")),
             g("Wet", ("2 cups (480ml)", "buttermilk", ""), ("2", "eggs", ""), ("3 tbsp", "butter", "melted, plus more for the pan")),
             g("To serve", ("", "maple syrup", ""), ("", "butter", "")),
         ],
         steps=[s("Whisk the dry ingredients in a big bowl, and the wet ones in a jug."),
                s("Pour the wet into the dry and stir just until there's no dry flour left. Lumps are fine."),
                s("Let the batter rest for 10 minutes while the pan heats over medium.", 10),
                s("Butter the pan, pour in ¼ cup of batter per pancake and cook until bubbles cover the top, 2 to 3 minutes.", 2, 3),
                s("Flip and cook another minute or two, then serve with butter and maple syrup.")],
         tips=["The rest lets the baking powder get going, which is what makes them tall."], nutrition={}),
    dict(code="demo-hummus", user="chickpea.example", photo="hummus", title="Silky Hummus",
         summary="Very smooth hummus from tinned chickpeas, whipped with tahini and ice water.", kind="Sauces & dips",
         cuisine="Middle Eastern", tags=["vegan", "dip"], servings="4", time={"prep": "", "cook": "", "total": "30 min"}, oven="",
         ingredient_groups=[
             g("", ("1 tin (400g)", "chickpeas", "drained"), ("½ tsp", "baking soda", ""), ("½ cup (120g)", "tahini", ""),
               ("1", "lemon", "juiced"), ("1 clove", "garlic", ""), ("4–6 tbsp", "ice water", ""), ("¾ tsp", "salt", ""),
               ("to serve", "olive oil and sesame seeds", ""))],
         steps=[s("Simmer the chickpeas with the baking soda in plenty of water until very soft, about 20 minutes. Drain.", 20),
                s("Blend the tahini, lemon juice, garlic and salt until thick and pale."),
                s("Add the warm chickpeas and blend for 2 full minutes, adding the ice water a spoonful at a time.", 2),
                s("Spread it in a bowl and finish with olive oil and sesame seeds.")],
         tips=["Blend the chickpeas while they're still warm: it's the secret to the texture."], nutrition={}),
    dict(code="demo-soup", user="kitchen.example", photo="soup", title="Roasted Tomato Soup",
         summary="Tomatoes, onion and garlic roasted until sweet, then blended smooth.", kind="Soups", cuisine="",
         tags=["vegetarian", "freezer-friendly"], servings="4", time={"prep": "10 min", "cook": "45 min", "total": ""}, oven="220°C / 425°F",
         ingredient_groups=[
             g("", ("1kg", "tomatoes", "halved"), ("1", "onion", "in wedges"), ("1 head", "garlic", "top cut off"),
               ("3 tbsp", "olive oil", ""), ("2 cups (480ml)", "vegetable stock", ""), ("a handful", "basil", ""),
               ("to taste", "salt and pepper", ""))],
         steps=[s("Toss the tomatoes and onion with the oil, salt and pepper on a tray, add the garlic, and roast at 220°C for 35 minutes.", 35),
                s("Squeeze the garlic out of its skins into a pot, add everything from the tray and the stock, and simmer for 10 minutes.", 10),
                s("Blend with the basil until smooth, and season to taste.")],
         tips=[], nutrition={}),
    dict(code="demo-pappardelle", user="pasta.example", photo="pappardelle", title="Pappardelle with Brown Butter and Greens",
         summary="Wide ribbons of pasta in brown butter with wilted greens and lots of parmesan.", kind="Mains", cuisine="Italian",
         tags=["pasta"], servings="2", time={"prep": "", "cook": "", "total": "20 min"}, oven="",
         ingredient_groups=[
             g("", ("250g", "pappardelle", ""), ("60g", "butter", ""), ("2 big handfuls", "spinach or chard", ""),
               ("1", "lemon", "zested"), ("40g", "parmesan", "grated, plus more to serve"), ("to taste", "black pepper", ""))],
         steps=[s("Cook the pappardelle in salted water until just tender.", 8),
                s("Meanwhile brown the butter in a wide pan until it smells nutty."),
                s("Add the greens and let them wilt, then add the pasta with a splash of its water."),
                s("Toss with the lemon zest and parmesan until glossy, and finish with pepper.")],
         tips=[], nutrition={}),
    dict(code="demo-smoothie", user="blend.example", photo="smoothie", title="Strawberry Banana Smoothie",
         summary="Thick and cold, with frozen fruit and yogurt.", kind="Drinks", cuisine="", tags=["5 minutes"], servings="2",
         time=NONE, oven="",
         ingredient_groups=[g("", ("1½ cups", "frozen strawberries", ""), ("1", "banana", ""), ("¾ cup", "yogurt", ""),
                              ("½ cup", "milk", ""), ("1 tsp", "honey", "optional"))],
         steps=[s("Blend everything until smooth, adding a splash more milk if it's too thick to move.")], tips=[], nutrition={}),
]


SHAKSHUKA_EN = dict(lang="en", translated_from="he", title="Shakshuka",
    summary="Eggs cooked in a sweet-and-spicy tomato and pepper sauce, all in one pan.", kind="Breakfast", cuisine="Israeli",
    tags=["breakfast", "one pan"], servings="4", time={"prep": "", "cook": "", "total": "35 minutes"}, oven="",
    ingredient_groups=[g("", ("2 tbsp", "olive oil", ""), ("1", "onion", "chopped"), ("1", "red pepper", "chopped"), ("3 cloves", "garlic", "sliced"),
                         ("1 tsp", "sweet paprika", ""), ("1 tsp", "cumin", ""), ("1 can (800g)", "crushed tomatoes", ""),
                         ("1 tsp", "sugar", ""), ("to taste", "salt and pepper", ""), ("6", "eggs", ""), ("a handful", "parsley", "chopped"))],
    steps=[s("Heat the oil in a wide pan and fry the onion and pepper until soft, about 8 minutes.", 8),
           s("Add the garlic, paprika and cumin and stir for a minute."),
           s("Add the tomatoes and sugar, season, and simmer over medium heat until the sauce thickens, about 15 minutes.", 15),
           s("Make six wells in the sauce and crack an egg into each one."),
           s("Cover and cook for 6 to 8 minutes, until the whites are set and the yolks still soft.", 6, 8),
           s("Scatter the parsley over it and serve with fresh bread.")],
    tips=["If the sauce gets too thick before the eggs go in, add a little water."], nutrition={}, missing=[])


def build(state):
    reels = state / "reels"
    reels.mkdir(parents=True)
    now = time.time()
    for n, r in enumerate(RECIPES):
        f = reels / r["code"]
        f.mkdir()
        src = PHOTOS / f"{r['photo']}.jpg"
        # a 9:16 still and a short clip, like a reel's
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src), "-vf",
                        f"scale=-2:1280,crop=720:1280:{r.get('crop_x', '(iw-ow)/2')}:0", "-q:v", "3", str(f / "photo.jpg")], check=True)
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-loop", "1", "-i", str(f / "photo.jpg"), "-t", "6",
                        "-vf", "zoompan=z='min(zoom+0.0008,1.08)':d=150:s=720x1280:fps=25", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(f / "video.mp4")], check=True)
        post = {"code": r["code"], "user": r["user"], "name": "", "caption": "", "found": now - n * 3600,
                "url": f"https://www.instagram.com/reel/{r['code']}/"}
        rec = {"is_recipe": True, "lang": r.get("lang", "en"), "complete": r.get("complete", True),
               "missing": r.get("missing", []), "main_ingredients": [], "from": {"caption": True, "speech": True, "screen": True},
               "photo": "photo.jpg", "photo_at": 1.0}
        rec.update({k: v for k, v in r.items() if k not in ("code", "user", "photo", "missing", "complete", "crop_x")})
        (f / "post.json").write_text(json.dumps(post, ensure_ascii=False))
        if r["code"] == "demo-shakshuka":
            (f / "recipe.en.json").write_text(json.dumps(SHAKSHUKA_EN, ensure_ascii=False))
        (f / "recipe.json").write_text(json.dumps(rec, ensure_ascii=False))


def remembered(state):
    """Two made-up accounts, Sam (the owner) and Alex, and what Sam has saved, cooked, rated and opened."""
    from matkon import accounts, memory
    import secrets as _s
    accounts.ensure()
    accounts.add("alex", "Alex", _s.token_urlsafe(12))
    for code in ("demo-hummus", "demo-smoothie"):
        p = state / "reels" / code / "post.json"
        post = json.loads(p.read_text())
        post["added_by"] = "alex"
        p.write_text(json.dumps(post))
    day = 86400
    m = memory.load("sam")
    m["saved"] = {"demo-salad": time.time() - 2 * day, "demo-pappardelle": time.time() - 9 * day, "demo-hummus": time.time() - day}
    m["ratings"] = {"demo-cookies": 9, "demo-pancakes": 8, "demo-soup": 7, "demo-ramen": 10}
    m["notes"] = {"demo-cookies": {"text": "Chilled the dough overnight: even better. 20g less sugar next time.", "at": time.time()}}
    m["cooked"] = [{"id": "a1", "code": "demo-cookies", "at": time.time() - 2 * day}, {"id": "a2", "code": "demo-ramen", "at": time.time() - 23 * day},
                   {"id": "a3", "code": "demo-pancakes", "at": time.time() - 6 * day}, {"id": "a4", "code": "demo-cookies", "at": time.time() - 30 * day},
                   {"id": "a5", "code": "demo-soup", "at": time.time() - 12 * day}]
    m["viewed"] = [[c, time.time() - i * 5400] for i, c in enumerate(["demo-cookies", "demo-shakshuka", "demo-salad", "demo-ramen", "demo-hummus"])]
    memory._save("sam", m)
    runs = [{"at": time.time() - 3 * 3600, "kind": "sync", "found": [{"code": "demo-ramen", "by": "sam"}, {"code": "demo-shakshuka", "by": "sam"}],
             "made": [{"code": "demo-ramen", "title": ""}, {"code": "demo-shakshuka", "title": ""}], "failed": []},
            {"at": time.time() - day, "kind": "add", "by": "alex", "made": [{"code": "demo-hummus", "title": ""}], "failed": []},
            {"at": time.time() - 2 * day, "kind": "sync", "found": [{"code": "demo-cookies", "by": "sam"}, {"code": "demo-smoothie", "by": "alex"}],
             "made": [{"code": "demo-cookies", "title": ""}, {"code": "demo-smoothie", "title": ""}], "failed": []}]
    (state / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in reversed(runs)))
    (state / "initial-password.txt").unlink(missing_ok=True)
    from matkon import config, kitchen                 # Sam's browser has the extension, and looked an hour ago
    st = config.settings()
    st.update(collection_id="17900000000000001", collection_name="Recipes")
    config.save_settings(st)
    kitchen.new_key("sam")
    kitchen.seen("sam", "0.1.0", None, checked=True)
    b = json.loads((state / "users" / "sam" / "browser.json").read_text())
    b["checked"] = int(time.time()) - 3600
    (state / "users" / "sam" / "browser.json").write_text(json.dumps(b))


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = sys.argv[2] if len(sys.argv) > 2 else "8519"
    state = Path(tempfile.mkdtemp(prefix="matkon-demo-"))
    build(state)
    os.environ.update({"MATKON_STATE": str(state), "MATKON_SETTINGS": str(state / "settings.json"),
                       "MATKON_HOSTS": host, "MATKON_PORT": port, "MATKON_OWNER": "sam", "MATKON_DEMO_ACCOUNT": "sam",
                       "MATKON_VAULT": "", "MATKON_NOTIFY": "", "MATKON_ENV": "/nonexistent"})
    sys.path.insert(0, str(ROOT))
    remembered(state)
    from matkon import server
    print("demo state:", state, flush=True)
    server.main()


if __name__ == "__main__":
    main()

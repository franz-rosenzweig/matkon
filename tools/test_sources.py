#!/usr/bin/env python3
"""Recipes from a link or from photos (sources.py), against a pretend recipe site on this machine: the
API and what it turns away, the codes, the road from page or photos to recipe, note and list, and that
none of them ever reaches the Instagram queue. A stand-in answers for Claude unless MATKON_TEST_CLAUDE=1.
Nothing here talks to Instagram or any other part of Meta.

  python3 tools/test_sources.py                         (a stand-in for Claude: seconds)
  MATKON_TEST_CLAUDE=1 python3 tools/test_sources.py    (the real Claude reads the pages and the card: minutes)
  python3 tools/test_sources.py --site [PORT]           only the pretend site (8563), to try the app by hand
                                                        (the server needs MATKON_PRIVATE_LINKS=1 to read it)
Needs Pillow, for the pictures.
"""
import base64
import http.client
import http.cookiejar
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILS = []
REAL = os.environ.get("MATKON_TEST_CLAUDE") == "1"
SITE_PORT, APP_PORT = 8563, 8562
SITE = f"http://127.0.0.1:{SITE_PORT}"


def ok(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what, flush=True)
    if not cond:
        FAILS.append(what)


# ---- the pictures: a dish for the brownie page, and a recipe card in two photos (made up here) ----

def _font(size, bold=False):
    from PIL import ImageFont
    for name in (("DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf"), "LiberationSerif-Regular.ttf"):
        for d in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation", "/Library/Fonts", "/System/Library/Fonts"):
            if Path(d, name).exists():
                return ImageFont.truetype(str(Path(d, name)), size)
    return ImageFont.load_default(size=size)


def _card(lines, size, rule=90):
    """An index card: cream, blue lines, the text in dark ink."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", size, (250, 244, 225))
    d = ImageDraw.Draw(im)
    for y in range(rule * 2, size[1], rule):
        d.line([(0, y), (size[0], y)], fill=(170, 195, 230), width=3)
    d.line([(int(size[0] * 0.08), 0), (int(size[0] * 0.08), size[1])], fill=(225, 140, 140), width=4)
    y = int(rule * 1.25)
    for text, big in lines:
        d.text((int(size[0] * 0.11), y), text, font=_font(int(rule * (1.35 if big else 0.72)), big), fill=(35, 45, 80))
        y += int(rule * (1.6 if big else 1.0))
    return im


def pictures():
    from PIL import Image, ImageDraw
    out = {}
    dish = Image.new("RGB", (1200, 800), (236, 230, 220))
    d = ImageDraw.Draw(dish)
    d.ellipse([150, 60, 1050, 760], fill=(250, 250, 248), outline=(200, 200, 200), width=6)
    for i, (x, y) in enumerate([(330, 220), (600, 220), (330, 450), (600, 450)]):
        d.rectangle([x, y, x + 240, y + 200], fill=(70 + i * 6, 40, 25))
        d.rectangle([x, y, x + 240, y + 30], fill=(95, 60, 40))
    buf = io.BytesIO()
    dish.save(buf, "JPEG", quality=88)
    out["brownies.jpg"] = buf.getvalue()
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, "PNG")
    out["pixel.png"] = buf.getvalue()
    front = _card([("Lemon Bars", True), ("", False), ("Crust", True), ("1 cup flour", False), ("1/2 cup butter, soft", False),
                   ("1/4 cup powdered sugar", False), ("", False), ("Filling", True), ("2 eggs", False), ("1 cup sugar", False),
                   ("3 tbsp lemon juice", False), ("zest of 1 lemon", False), ("2 tbsp flour", False), ("salt", False), ("", False),
                   ("Oven 350°F. Press the crust into an 8x8 pan", False), ("and bake 15-20 min, until just golden.", False),
                   ("Whisk the filling, pour it over the hot crust,", False), ("bake 20 min more. Cool, then cut.", False)],
                  (2400, 3200), rule=120)
    # the way a phone keeps a photo taken sideways: the pixels lie on their side, and EXIF says to turn them
    exif = Image.Exif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    front.transpose(Image.Transpose.ROTATE_90).save(buf, "JPEG", quality=85, exif=exif.tobytes())
    out["card-front.jpg"] = buf.getvalue()
    back = _card([("Makes 16 squares.", False), ("Dust with powdered sugar to serve.", False),
                  ("Fresh lemons only, not the bottled juice!", False)], (1600, 700))
    buf = io.BytesIO()
    back.save(buf, "PNG")
    out["card-back.png"] = buf.getvalue()
    return out


# ---- the pretend site ----

GRAPH = {"@context": "https://schema.org", "@graph": [
    {"@type": "WebSite", "@id": "/#website", "name": "The Test Kitchen"},
    {"@type": "ImageObject", "@id": "/brownies.html#primaryimage", "url": "/img/brownies.jpg", "width": 1200, "height": 800},
    {"@type": "Recipe", "name": "One-Bowl Fudgy Brownies", "image": ["/img/pixel.png", {"@id": "/brownies.html#primaryimage"}],
     "datePublished": "2024-03-05T09:00:00+00:00", "recipeYield": "16 brownies", "prepTime": "PT10M", "cookTime": "PT25M",
     "recipeIngredient": ["115g butter, melted", "200g sugar", "2 eggs", "1 tsp vanilla extract", "40g cocoa powder",
                          "65g plain flour", "a pinch of salt", "chocolate chips"],
     "recipeInstructions": [
         {"@type": "HowToStep", "text": "Heat the oven to 180°C and line a 20cm square tin with baking paper."},
         {"@type": "HowToStep", "text": "Whisk the melted butter with the sugar, then the eggs and vanilla, until glossy."},
         {"@type": "HowToStep", "text": "Sift in the cocoa, flour and salt and fold until there's no dry flour left. Stir in the chocolate chips."},
         {"@type": "HowToStep", "text": "Bake for 20 to 25 minutes, until the top is shiny and the middle just set."}]}]}

PAGES = {
    "/brownies.html": f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>One-Bowl Fudgy Brownies - The Test Kitchen</title>
<meta property="og:title" content="One-Bowl Fudgy Brownies">
<meta property="og:image" content="/img/brownies.jpg">
<script type="application/ld+json">{json.dumps(GRAPH)}</script></head>
<body><header><nav><a href="/">Home</a> <a href="/recipes">Recipes</a></nav></header>
<article><h1>One-Bowl Fudgy Brownies</h1>
<p>These are the brownies I make when friends drop by on short notice. Everything happens in one bowl, and they
come out dense and fudgy with a crackly top. My kids ask for them every week, and honestly so do I.</p>
<div class="recipe"><h2>Ingredients</h2><ul><li>115g butter, melted</li><li>200g sugar</li><li>2 eggs</li>
<li>1 tsp vanilla extract</li><li>40g cocoa powder</li><li>65g plain flour</li><li>a pinch of salt</li><li>chocolate chips</li></ul>
<h2>Method</h2><ol><li>Heat the oven to 180°C and line a 20cm square tin with baking paper.</li>
<li>Whisk the melted butter with the sugar, then the eggs and vanilla, until glossy.</li>
<li>Sift in the cocoa, flour and salt and fold until there's no dry flour left. Stir in the chocolate chips.</li>
<li>Bake for 20 to 25 minutes, until the top is shiny and the middle just set.</li></ol>
<h3>Notes</h3><p>Let them cool for at least an hour before you cut them, or they fall apart.</p>
<p>You can swap the chocolate chips for chopped walnuts.</p></div></article>
<section class="comments"><h2>Comments</h2><p>Pat: I added 2 cups of chocolate chips and they were amazing!</p></section>
<footer>All rights reserved.</footer></body></html>""",
    "/soup.html": """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Red Lentil Soup</title>
<meta property="article:published_time" content="2023-11-20"></head>
<body><main><h1>Weeknight Red Lentil Soup</h1>
<p>A quick, cheap soup for cold evenings. It thickens as it sits, so add a splash of water when you warm it up again.</p>
<h2>You need</h2><p>1 cup red lentils, rinsed<br>1 onion, chopped<br>2 carrots, diced<br>olive oil<br>1 tsp ground cumin<br>
4 cups vegetable stock<br>salt to taste<br>a squeeze of lemon</p>
<h2>Method</h2><p>Soften the onion and carrots in the olive oil for about 5 minutes. Stir in the cumin, then the lentils and the stock.
Simmer for 20 minutes, until the lentils fall apart. Blend half of it, season with salt, and finish with the lemon.</p></main></body></html>""",
    "/news.html": """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Council approves new bike lanes</title>
<meta property="og:site_name" content="Example Daily"></head>
<body><article><h1>Council approves new bike lanes on Main Street</h1>
<p>The city council voted 7 to 2 on Tuesday night to add protected bike lanes along Main Street, after months of public
meetings. Work is expected to start in the spring and take about four months, with one lane of traffic kept open throughout.</p>
<p>Shop owners on the street were split. Some worried about losing parking spaces in front of their stores, while others said
more people on bikes would mean more people stopping in. The council promised a review of the parking plan before work begins.</p>
</article></body></html>""",
}
PAGES["/shakshuka.html"] = """<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><title>שקשוקה של יום שישי</title>
<meta property="og:site_name" content="המטבח לדוגמה"></head>
<body><main><h1>שקשוקה של יום שישי</h1>
<p>השקשוקה הזאת היא ארוחת הבוקר הקבועה שלנו בימי שישי. היא פשוטה ומהירה, וכולם אוהבים לנגב אותה עם חלה טרייה.</p>
<h2>מצרכים</h2><p>2 כפות שמן זית<br>1 בצל קצוץ<br>2 פלפלים אדומים פרוסים<br>3 שיני שום<br>1 כפית פפריקה מתוקה<br>
קורט כמון<br>6 עגבניות בשלות מרוסקות<br>מלח<br>4 ביצים<br>פטרוזיליה</p>
<h2>אופן ההכנה</h2><p>מטגנים את הבצל והפלפלים בשמן כ-10 דקות. מוסיפים את השום והתבלינים, ואחריהם את העגבניות.
מבשלים 15 דקות, עד שהרוטב מסמיך. שוברים את הביצים לתוך הרוטב, מכסים ומבשלים עוד 5 עד 7 דקות. מפזרים פטרוזיליה ומגישים.</p>
</main></body></html>"""
REDIRECTS = {"/short/b":"/brownies.html?utm_source=short", "/to-instagram": "https://www.instagram.com/p/NOPE1234567/"}
LOG = []


class Site(BaseHTTPRequestHandler):
    pics = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        LOG.append(self.path)
        path = self.path.split("?", 1)[0]
        if path in REDIRECTS:
            self.send_response(302)
            self.send_header("Location", REDIRECTS[path])
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path in PAGES:
            return self.reply(PAGES[path].encode(), "text/html; charset=utf-8")
        if path.startswith("/img/") and path[5:] in self.pics:
            return self.reply(self.pics[path[5:]], "image/png" if path.endswith(".png") else "image/jpeg")
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def reply(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_site(port=SITE_PORT):
    Site.pics = pictures()
    s = ThreadingHTTPServer(("127.0.0.1", port), Site)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


# ---- a stand-in for Claude: it keeps each message it's sent, and answers from what it's about ----

BROWNIES = {"is_recipe": True, "lang": "en", "title": "One-Bowl Fudgy Brownies", "summary": "Dense chocolate brownies made in one bowl.",
            "kind": "Baking & sweets", "tags": ["brownies"], "servings": "16 brownies", "time": {"prep": "10 min", "cook": "25 min", "total": ""},
            "oven": "180°C", "ingredient_groups": [{"name": "", "items": [{"amount": "115g", "item": "butter", "note": "melted"},
                                                                          {"amount": "", "item": "chocolate chips", "note": ""}]}],
            "steps": [{"text": "Bake for 20 to 25 minutes.", "timers": [20, 25]}], "tips": ["Let them cool for an hour before cutting."],
            "main_ingredients": ["cocoa", "butter"], "complete": False, "missing": ["how many chocolate chips"]}
SOUP = {"is_recipe": True, "lang": "en", "title": "Weeknight Red Lentil Soup", "summary": "A quick red lentil soup.", "kind": "Soups",
        "ingredient_groups": [{"name": "", "items": [{"amount": "1 cup", "item": "red lentils", "note": "rinsed"}, {"amount": "", "item": "olive oil", "note": ""}]}],
        "steps": [{"text": "Simmer for 20 minutes.", "timers": [20]}], "complete": False, "missing": ["how much olive oil"]}
LEMON = {"is_recipe": True, "lang": "en", "title": "Lemon Bars", "summary": "Lemon bars on a shortbread crust.", "kind": "Baking & sweets",
         "servings": "16 squares", "oven": "350°F", "ingredient_groups": [{"name": "Crust", "items": [{"amount": "1 cup", "item": "flour", "note": ""}]},
                                                                           {"name": "Filling", "items": [{"amount": "", "item": "salt", "note": ""}]}],
         "steps": [{"text": "Bake 15-20 min.", "timers": [15, 20]}], "complete": False, "missing": ["how much salt"]}
NEWS = {"is_recipe": False, "lang": "en", "title": "Council approves new bike lanes", "summary": "A news story, not a recipe."}

FAKE = f"""#!{sys.executable} -I
import json, os, sys
msg = json.loads(sys.stdin.readline())
with open(os.environ["MATKON_TEST_LOG"], "a") as f:
    f.write(json.dumps(msg) + "\\n")
content = msg["message"]["content"]
text = "\\n".join(c.get("text", "") for c in content if c.get("type") == "text")
if any(c.get("type") == "image" for c in content):
    a = {LEMON!r}
elif "bike lanes" in text:
    a = {NEWS!r}
elif "Lentil" in text:
    a = {SOUP!r}
else:
    a = {BROWNIES!r}
print(json.dumps({{"type": "result", "is_error": False, "result": json.dumps(a)}}))
"""


def main():
    if "--site" in sys.argv:
        port = int(sys.argv[sys.argv.index("--site") + 1]) if len(sys.argv) > sys.argv.index("--site") + 1 else SITE_PORT
        serve_site(port)
        print(f"the pretend site: http://127.0.0.1:{port}/brownies.html, /soup.html, /news.html, /shakshuka.html, /short/b, /to-instagram", flush=True)
        while True:
            time.sleep(3600)

    state = Path(tempfile.mkdtemp(prefix="matkon-sources-test-"))
    env = state / "test.env"
    env.write_text("\n".join([f"MATKON_STATE={state}", f"MATKON_SETTINGS={state}/settings.json", "MATKON_OWNER=tester",
                              "MATKON_HOSTS=127.0.0.1", f"MATKON_PORT={APP_PORT}", f"MATKON_VAULT={state}/vault", "MATKON_NOTIFY=",
                              "MATKON_PY=/bin/false", "MATKON_PRIVATE_LINKS=1", "MATKON_COOKBOOK="]) + "\n")
    os.environ["MATKON_ENV"] = str(env)
    os.environ["MATKON_TEST_LOG"] = str(state / "claude-saw.jsonl")
    if not REAL:
        (state / "bin").mkdir()
        (state / "bin" / "claude").write_text(FAKE)
        (state / "bin" / "claude").chmod(0o755)
        os.environ["PATH"] = f"{state / 'bin'}:{os.environ['PATH']}"
    sys.path.insert(0, str(ROOT))
    from matkon import accounts, config, cookbook, linked, sources, store  # noqa: E402
    config.STATE.mkdir(parents=True, exist_ok=True)
    config.REELS.mkdir(exist_ok=True)
    (state / "vault").mkdir()
    accounts.ensure()
    accounts.update("tester", password="sources-test-password")
    site = serve_site()
    app = None
    try:
        app = run(state, accounts, config, cookbook, linked, sources, store)
    finally:
        if app:
            app.terminate()
        site.shutdown()
    if not FAILS:
        import shutil
        shutil.rmtree(state, ignore_errors=True)
    else:
        print("the test's state is kept:", state)
    print(f"{len(FAILS)} FAILED" if FAILS else "all good")
    return 1 if FAILS else 0


def run(state, accounts, config, cookbook, linked, sources, store):
    # ---- 1. addresses, Meta and private networks, without the app ----
    print("addresses", flush=True)
    url, key = sources.address("Look at these! https://WWW.Example.com/r/brownies/?utm_source=ig&fbclid=x&id=3#comments")
    ok(url == "https://www.example.com/r/brownies/?id=3", "an address is tidied: a lowercase host, no tracking, no #part")
    ok(sources.address("example.com/r/brownies?id=3")[1] == key, "the same page spelled another way has the same key")
    ok(sources.address("https://l.facebook.com/l.php?u=https%3A%2F%2Fpie.example%2Fpie&h=AT")[0] == "https://pie.example/pie",
       "Facebook's link redirect is unwrapped from the link itself")
    ok(sources.domain(sources.address("https://www.מתכונים.example/עוגה")[0]) == "מתכונים.example", "a Hebrew address keeps its Hebrew name as its site")
    meta = ["https://www.instagram.com/cook.example/", "https://instagr.am/p/ABCDE/", "https://www.facebook.com/page/posts/1",
            "https://m.facebook.com/story.php", "https://fb.me/x1", "https://www.threads.net/@cook/post/1", "https://www.threads.com/@cook",
            "https://scontent.cdninstagram.com/v/a.jpg", "https://video.fbcdn.net/a.mp4", "https://wa.me/123",
            "https://l.instagram.com/?u=https%3A%2F%2Fwww.instagram.com%2Fp%2FABC%2F"]
    ok(all(linked.is_meta(sources.address(u)[0]) for u in meta), "Instagram, Facebook, Threads and the rest of Meta are all Meta")
    ok(not linked.is_meta("https://notinstagram.example/") and not linked.is_meta("https://example.com/instagram.com"), "and nothing else is")
    os.environ["MATKON_PRIVATE_LINKS"] = "0"
    ok(not linked.public(SITE) and not linked.public("http://localhost/") and not linked.public("http://100.100.1.1/")
       and not linked.public("http://192.168.1.10/") and not linked.public("http://[::1]/"), "this machine, a LAN and a tailnet aren't public")
    n = len(LOG)
    lk = linked.fetch(SITE + "/brownies.html")
    ok(lk.get("kind") == "error" and "private" in lk.get("error", "") and len(LOG) == n, "a private address isn't even asked")
    os.environ["MATKON_PRIVATE_LINKS"] = "1"
    lk = linked.fetch(SITE + "/to-instagram")
    ok(lk.get("kind") == "error" and "Instagram" in lk.get("error", ""), "a redirect to Instagram is refused, not followed")
    lk = linked.fetch(SITE + "/brownies.html", keep_text=True)
    page = lk.get("page") or {}
    ok(lk.get("kind") == "recipe" and "chocolate chips" in lk["recipe"]["ingredients"], "the page's schema.org recipe is read")
    ok("Let them cool" in (lk.get("text") or "") and "Ingredients" in lk["text"], "and its text, beside it, for a page added by its link")
    ok(page.get("site") == "The Test Kitchen" and page.get("published") == 1709629200, "the site's name (its WebSite) and the date it was published")
    ok(page.get("images", [None])[0] == SITE + "/img/pixel.png" and SITE + "/img/brownies.jpg" in page.get("images", []),
       "the recipe's photos, in the page's order, as full addresses")

    # ---- 2. the app ----
    print("the app", flush=True)
    app = subprocess.Popen([sys.executable, "-I", str(ROOT / "run.py"), "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    M = f"http://127.0.0.1:{APP_PORT}"
    for _ in range(50):
        try:
            urllib.request.urlopen(M + "/", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(path, body=None, headers=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(M + path, data=data, headers={"Content-Type": "application/json", "X-Matkon": "1", **(headers or {})})
        try:
            with opener.open(req, timeout=30) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")

    def dataurl(b, kind):
        return f"data:image/{kind};base64," + base64.b64encode(b).decode()

    code, d = call("/api/add-link", {"url": SITE + "/brownies.html"})
    code2, _ = call("/api/add-photo", {"images": []})
    ok(code == 401 and code2 == 401 and not list(config.REELS.iterdir()), "signed out: no, and nothing is kept")
    req = urllib.request.Request(M + "/api/add-link", data=b'{"url": "https://example.com/"}', headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
        ok(False, "a POST without X-Matkon is refused")
    except urllib.error.HTTPError as e:
        ok(e.code == 403, "a POST without X-Matkon is refused")
    call("/api/signin", {"username": "tester", "password": "sources-test-password"})

    code, d = call("/api/add-link", {"url": "https://www.instagram.com/reel/DAbcdEFgh12/?igsh=xyz"})
    ok(code == 200 and d == {"ok": True, "code": "DAbcdEFgh12", "new": True, "done": False}, "a reel's link goes to Add a reel")
    ok("DAbcdEFgh12" in store.wanted(), "and waits for the browser like any reel")
    for bad, why in [("https://www.instagram.com/cook.example/", "Instagram"), ("https://www.facebook.com/somepage/posts/1", "Facebook"),
                     ("https://www.threads.net/@cook/post/1", "Threads"), ("https://fb.me/abc", "Instagram"),
                     ("ftp://example.com/x", "http"), ("javascript:alert(1)", "http"), ("", "isn't a web link"), ("just some words", "isn't a web link")]:
        code, d = call("/api/add-link", {"url": bad})
        ok(code == 400 and why in (d or {}).get("error", ""), f"turned away, 400: {bad or '(nothing)'} → {(d or {}).get('error')}")

    code, web = call("/api/add-link", {"url": SITE + "/brownies.html"})
    ok(code == 200 and re.fullmatch(r"web-[0-9a-f]{10}", web.get("code", "")) and web["new"] is True and web["done"] is False,
       f"a recipe page: {web}")
    code, again = call("/api/add-link", {"url": "Brownies! " + SITE + "/brownies.html?utm_source=share#top"})
    ok(code == 200 and again["code"] == web["code"] and again["new"] is False, "the same page again is the same recipe, not new")
    _, soup = call("/api/add-link", {"url": SITE + "/soup.html"})
    _, news = call("/api/add-link", {"url": SITE + "/news.html"})
    p = store.read(config.REELS / web["code"] / "post.json")
    ok(p and p["source"] == "web" and p["url"] == SITE + "/brownies.html" and p["user"] == "127.0.0.1" and p["added_by"] == "tester",
       "its post: source web, the page's address, the site as its user, who added it")

    pics = Site.pics
    code, d = call("/api/add-photo", {"images": []})
    ok(code == 400 and "one to 4" in d.get("error", ""), "no photos: 400")
    code, d = call("/api/add-photo", {"images": [dataurl(pics["pixel.png"], "png")] * 5})
    ok(code == 400, "five photos: 400")
    code, d = call("/api/add-photo", {"images": ["data:image/gif;base64,R0lGODlhAQABAAAAACw="]})
    ok(code == 400 and "JPEG, PNG or WebP" in d.get("error", ""), "a GIF: 400")
    code, d = call("/api/add-photo", {"images": [dataurl(b"<svg>not a picture</svg>", "png")]})
    ok(code == 400 and "isn't a JPEG" in d.get("error", ""), "something that only says it's a PNG: 400")
    code, d = call("/api/add-photo", {"images": ["data:image/jpeg;base64,/9j/4AAQ!!!"]})
    ok(code == 400 and "whole" in d.get("error", ""), "broken base64: 400")
    code, d = call("/api/add-photo", {"images": [dataurl(b"\x89PNG\r\n\x1a\n" + b"\x00" * 6_000_000, "png")]})
    ok(code == 400 and "couldn't be read" in d.get("error", "") and not any(config.REELS.glob("pic-*")),
       "6 MB is fine for photos (the PNG inside is broken: 400, and nothing is left behind)")
    c = http.client.HTTPConnection("127.0.0.1", APP_PORT, timeout=10)
    c.putrequest("POST", "/api/add-photo")
    for k, v in (("X-Matkon", "1"), ("Content-Type", "application/json"), ("Content-Length", str(31_000_000)),
                 ("Cookie", "; ".join(f"{x.name}={x.value}" for x in jar))):
        c.putheader(k, v)
    c.endheaders()
    r = c.getresponse()
    ok(r.status == 400 and b"too big" in r.read(), "over 30 MB: too big")
    c.close()
    code, d = call("/api/me", raw=json.dumps({"op": "x", "pad": "x" * 2_500_000}).encode())
    ok(code == 400 and d.get("error") == "too big", "everything else still stops at 2 MB")

    code, pic = call("/api/add-photo", {"images": [dataurl(pics["card-front.jpg"], "jpeg"), dataurl(pics["card-back.png"], "png")]})
    ok(code == 200 and re.fullmatch(r"pic-[0-9a-f]{10}", pic.get("code", "")) and pic["new"] is True and pic["done"] is False,
       f"photos of a recipe card: {pic}")
    f = config.REELS / pic["code"]
    p = store.read(f / "post.json")
    ok(p and p["source"] == "photo" and p["user"] == "" and p["photos"] == 2 and "url" not in p and p["added_by"] == "tester",
       "its post: source photo, no user, no address")
    size = sources._size(f / "image1.jpg")
    ok(size == (1500, 2000), f"the sideways phone photo is kept upright and at most 2000 on its long side ({size[0]}x{size[1]})")
    ok(sources._size(f / "image2.jpg") == (1600, 700) and not list(f.glob(".upload*")), "the PNG is kept as a JPEG, nothing else left")
    code, d = call("/api/add-photo", {"images": [dataurl(pics["card-front.jpg"], "jpeg"), dataurl(pics["card-back.png"], "png")]})
    ok(code == 200 and d["code"] == pic["code"] and d["new"] is False, "the same photos again are the same recipe")

    # the browser extension and the server's own look at Instagram never hear of them
    _, h = call("/api/ext/hello", {"version": "test"}, {"X-Matkon-Key": key_for(accounts)})
    ok(h and not any(c.startswith(("web-", "pic-")) for c in h.get("wanted", [])), "the extension's queue has no pages or photos")
    _, s = call("/api/ext/seen", {"codes": [web["code"], pic["code"]]}, {"X-Matkon-Key": key_for(accounts)})
    ok(s and s.get("want") == [], "and it's never asked to bring them")
    ok(not any(c.startswith(("web-", "pic-")) for c in store.wanted(10000)), "store.wanted (the server's look too) leaves them out")

    # ---- 3. the road to a recipe (the app started a run; this one picks up whatever's left) ----
    codes = {"brownies": web["code"], "soup": soup["code"], "news": news["code"], "card": pic["code"]}
    print("the runs", "(the real Claude: a few minutes)" if REAL else "(a stand-in for Claude)", flush=True)
    t0 = time.time()
    while time.time() - t0 < (900 if REAL else 120):
        if all(store.finished(config.REELS / c) or store.status_of(config.REELS / c).get("tries", 0) >= store.MAX_TRIES for c in codes.values()):
            break
        subprocess.run([sys.executable, "-I", str(ROOT / "run.py"), "sync", "--no-instagram", "--quiet"], capture_output=True, timeout=1200)
        time.sleep(1)
    for name, c in codes.items():
        ok(store.finished(config.REELS / c), f"{name} ({c}) went the whole way: {store.status_of(config.REELS / c).get('error') or 'done'}")
    ok(not (config.REELS / codes["brownies"] / "video.mp4").exists() and not (config.REELS / codes["brownies"] / "transcript.json").exists(),
       "no video, no transcript, no frames for a page")

    R = {name: store.read(config.REELS / c / "recipe.json", {}) for name, c in codes.items()}
    keys = {"is_recipe", "lang", "title", "summary", "kind", "cuisine", "tags", "servings", "time", "oven", "ingredient_groups", "steps",
            "tips", "nutrition", "main_ingredients", "complete", "missing", "from", "photo_at", "made", "model"}
    ok(all(keys <= set(r) for r in R.values()), "every recipe has a reel recipe's shape")
    b = config.REELS / codes["brownies"]
    p = store.read(b / "post.json")
    ok(p["name"] == "The Test Kitchen" and p["taken_at"] == 1709629200, "after reading it: the site's name and the date it was published")
    ok(R["brownies"].get("photo") == "photo.jpg" and sources._size(b / "photo.jpg") == (1200, 800),
       "the page's photo: the recipe's own, past a 1-pixel one")
    sp = store.read(config.REELS / codes["soup"] / "post.json")
    ok(sp["name"] == "" and sp["taken_at"] == 1700438400 and not R["soup"].get("photo"), "a page with no name and no photo: name empty, no photo")
    ok(R["news"].get("is_recipe") is False, "a page that isn't a recipe is is_recipe: false")
    ok(R["card"].get("photo") == "photo.jpg" and (f / "photo.jpg").read_bytes() == (f / "image1.jpg").read_bytes(), "the card's first photo is its photo")

    saw = [json.loads(x) for x in (state / "claude-saw.jsonl").read_text().splitlines()] if (state / "claude-saw.jsonl").exists() else []
    if not REAL:
        texts = ["\n".join(c.get("text", "") for c in m["message"]["content"]) for m in saw]
        w = next((t for t in texts if "One-Bowl" in t), "")
        ok("recipe page from the web" in w and "Readers' comments don't count" in w and "chocolate chips" in w and "Let them cool" in w,
           "the page's prompt: its own wording, the recipe data and the writer's notes")
        ok("reel" not in w.lower(), "and no talk of a reel")
        ph = next((m for m in saw if any(c.get("type") == "image" for c in m["message"]["content"])), None)
        cont = ph["message"]["content"] if ph else []
        ok([c.get("text") for c in cont if c.get("type") == "text"][:2] == ["Photo 1", "Photo 2"] and sum(c.get("type") == "image" for c in cont) == 2
           and "You have 2 photos" in cont[-1]["text"] and "reel" not in cont[-1]["text"].lower(), "the photos' prompt: both photos, in order, its own wording")
    else:
        br, so, card = R["brownies"], R["soup"], R["card"]
        items = {i["item"].lower(): i for g in br.get("ingredient_groups", []) for i in g["items"]}
        chips = next((i for k, i in items.items() if "chocolate" in k), None)
        ok(br.get("is_recipe") and "brownie" in br.get("title", "").lower(), f"Claude: the brownie page is a recipe: {br.get('title')}")
        ok(chips is not None and chips["amount"] == "", "the chocolate chips keep no amount (a reader's 2 cups don't count)")
        ok(not br.get("complete") and any("chocolate" in m.lower() for m in br.get("missing", [])), f"and are missing: {br.get('missing')}")
        ok(any(s.get("timers") and 20 in s["timers"] for s in br.get("steps", [])), "the bake time is a timer")
        oil = next((i for g in so.get("ingredient_groups", []) for i in g["items"] if "oil" in i["item"].lower()), None)
        ok(so.get("is_recipe") and oil is not None and oil["amount"] == "", f"the lentil soup: olive oil with no amount ({so.get('title')})")
        ok(card.get("is_recipe") and "lemon" in card.get("title", "").lower(), f"Claude reads the card: {card.get('title')}")
        names = [i["item"].lower() for g in card.get("ingredient_groups", []) for i in g["items"]]
        ok(len(names) >= 8 and any("lemon" in n for n in names), f"its ingredients: {names}")
        ok(any(s.get("timers") for s in card.get("steps", [])) and card.get("oven"), f"its oven and timers: {card.get('oven')}")
        ok("16" in card.get("servings", ""), f"and the back of the card: {card.get('servings')}")

    # ---- 4. the list, the recipe page, the note, Cookbook, the log ----
    _, idx = call("/api/recipes")
    by = {r["code"]: r for r in idx["recipes"]}
    ok(by.get(codes["brownies"], {}).get("source") == "web" and by.get(codes["card"], {}).get("source") == "photo", "the list says each one's source")
    _, rw = call("/api/r/" + codes["brownies"])
    ok(rw["source"] == "web" and rw["reel"] == SITE + "/brownies.html" and rw["video"] is None and rw["user"] == "127.0.0.1"
       and rw["name"] == "The Test Kitchen" and rw["posted"] == 1709629200 and rw["photo"].startswith(f"m/{codes['brownies']}/photo.jpg"),
       "a page's recipe: reel is the page's address, no video, the site as user and name, its date, its photo")
    _, rp = call("/api/r/" + codes["card"])
    ok(rp["source"] == "photo" and rp["reel"] is None and rp["video"] is None and rp["user"] == "" and rp["photo"], "the card's: no reel, no video, a photo")
    try:
        with opener.open(urllib.request.Request(M + "/" + rp["photo"]), timeout=10) as r:
            ok(r.status == 200 and r.headers["Content-Type"] == "image/jpeg", "its photo is served")
    except urllib.error.HTTPError as e:
        ok(False, f"its photo is served ({e.code})")

    notes = {p.read_text().split("matkon: ")[1].split("\n")[0]: p.read_text() for p in (state / "vault").rglob("*.md")}
    nb, nc = notes.get(codes["brownies"], ""), notes.get(codes["card"], "")
    ok(nb and "instagram-reels" not in nb and "  - The Test Kitchen" in nb and f"[The Test Kitchen]({SITE}/brownies.html)" in nb,
       "the page's note: the site as author and as its source link, not tagged as a reel")
    ok(nb and ("## Not on the page" in nb or not R["brownies"].get("missing")), "and what's missing is \"Not on the page\"")
    ok(nc and "url:\n" in nc and "on Instagram" not in nc and ("## Not in the photos" in nc or not R["card"].get("missing")),
       "the card's note: no address, no Instagram, \"Not in the photos\"")
    ok(codes["news"] not in notes, "no note for the page that isn't a recipe")
    sb = cookbook.schema(b, R["brownies"], store.read(b / "post.json"), "x")
    sc = cookbook.schema(f, R["card"], store.read(f / "post.json"), "x")
    ok(sb["author"] == {"@type": "Person", "name": "The Test Kitchen"} and sb["url"] == SITE + "/brownies.html", "Cookbook's copy: the site, the page")
    ok(sc["author"] is None and sc["url"] == "" and ("Not in the photos" in sc["description"] or not R["card"].get("missing")),
       "the card's copy: nobody, no address")
    runs = [json.loads(x) for x in (state / "runs.jsonl").read_text().splitlines()] if (state / "runs.jsonl").exists() else []
    found = {x["code"] for r in runs for x in r.get("found", [])}
    ok(set(codes.values()) <= found, "History's Imported log has them")
    st = subprocess.run([sys.executable, "-I", str(ROOT / "run.py"), "status"], capture_output=True, text=True, timeout=60)
    ok(st.returncode == 0 and re.search(re.escape(codes["brownies"]) + r"\s+done", st.stdout), "run.py status: the page is done")

    # ---- 5. a short link, and redo ----
    if not REAL:
        short = sources.add_link(SITE + "/short/b", "tester")         # by hand, so no run picks it up meanwhile
        s = config.REELS / short["code"]
        sources.stage_page(s, store.read(s / "post.json"))
        sp = store.read(s / "post.json")
        ok(sp["url"] == SITE + "/brownies.html" and sp["sent"] == SITE + "/short/b", "a short link: the page it leads to, and the link as sent")
        import shutil
        shutil.rmtree(s)
        before = R["card"]["made"]
        time.sleep(1.1)
        rd = subprocess.run([sys.executable, "-I", str(ROOT / "run.py"), "redo", pic["code"], "--from", "frames"], capture_output=True, text=True, timeout=120)
        ok(rd.returncode == 0 and store.read(f / "recipe.json", {}).get("made", 0) > before, "redo from a video's stage starts photos at their recipe")
    return app


def key_for(accounts):
    from matkon import kitchen
    if not hasattr(key_for, "key"):
        key_for.key = kitchen.new_key(accounts.owner())
    return key_for.key


if __name__ == "__main__":
    sys.exit(main())

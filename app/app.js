/* Matkon: recipe reels as recipe pages.
   Plain JS. Everything comes from the server and needs an account (api/me, api/recipes, api/r/<code>…).
   Routes:  #/  home  ·  #/r/<code>  a recipe  ·  #/edit/<code>  fixing it  ·  #/cook/<code>/<n>  cooking  ·  #/week  ·  #/list
            #/pantry  what can I make  ·  #/add  a reel, a recipe page or photos  ·  #/history[/<tab>]  ·  #/settings
   Memory (saved, ticks, the cooking step, notes, ratings, what was cooked and opened, the week plan and the
   shopping list) lives on the server, so every device of an account sees the same, the Android app too.
   The kitchen timer and the ½×–3× amounts stay on the device. */
(function () {
  "use strict";

  const app = document.getElementById("app");
  const timerbar = document.getElementById("timerbar");
  let LIST = null, ME = null, SUGGEST = null;
  const FULL = {};
  let query = "";
  let emailPending = null, lastInvite = null, browserKey = null, shareResult = null;
  let kind = "All";
  let creator = null;                                  // #/from/<user>: one creator's recipes
  let sortBy = "added";                                // Added, Posted or A–Z (remembered on this device)

  /* ---------- helpers ---------- */
  const store = {
    get(k, d) { try { const v = localStorage.getItem("mk." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("mk." + k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
  };
  if (["posted", "az"].includes(store.get("sort"))) sortBy = store.get("sort");
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const norm = (s) => String(s || "").toLowerCase().normalize("NFKD").replace(/\p{M}+/gu, "").replace(/[^\p{L}\p{N} ]+/gu, " ").replace(/\s+/g, " ").trim();
  const fmtMin = (m) => (m < 60 ? `${m} min` : `${Math.floor(m / 60)} hr${m % 60 ? ` ${m % 60} min` : ""}`);
  const fmtClock = (ms) => {
    const s = Math.max(0, Math.ceil(ms / 1000));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(x).padStart(2, "0");
  };
  const day = (t, lang) => new Date(t * 1000).toLocaleDateString(lang === "he" ? "he-IL" : undefined, { day: "numeric", month: "short", year: new Date(t * 1000).getFullYear() === new Date().getFullYear() ? undefined : "numeric" });
  const dayTime = (t) => new Date(t * 1000).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
  const ico = (d, extra) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${extra || ""}>${d}</svg>`;
  const I = {
    back: ico('<path d="M15 5l-7 7 7 7"/>', 'class="flip"'),
    search: ico('<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>'),
    x: ico('<path d="M6 6l12 12M18 6L6 18"/>'),
    sort: ico('<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>'),
    play: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>',
    check: ico('<path d="M5 12.5l4.5 4.5L19 7.5"/>', 'stroke="#fff" stroke-width="3.2"'),
    clock: ico('<circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2M10 2h4"/>'),
    oven: ico('<rect x="3" y="3" width="18" height="18" rx="2"/><rect x="6" y="9" width="12" height="8" rx="1"/>'),
    people: ico('<circle cx="9" cy="8" r="3.2"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0M16 5.2a3 3 0 0 1 0 5.6M17.5 14.2A5.5 5.5 0 0 1 20.5 19"/>'),
    speak: ico('<path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>'),
    stop: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
    list: ico('<path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01"/>'),
    cook: ico('<path d="M4 11h16v3a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6v-3zM2 11h20M9 4c0 1.5 1 1.5 1 3M13 4c0 1.5 1 1.5 1 3"/>'),
    mark: ico('<path d="M7 4h10v16l-5-3.5L7 20z"/>'),
    markOn: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" aria-hidden="true"><path d="M7 4h10v16l-5-3.5L7 20z"/></svg>',
    history: ico('<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1M3.5 4v4h4"/><path d="M12 8v4.5l3 1.8"/>'),
    gear: ico('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>'),
    done: ico('<circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.8 2.8L16.5 9.5"/>'),
    trash: ico('<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>'),
    cal: ico('<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>'),
    cart: ico('<path d="M2.5 4h2.6l2.3 11.2h10.8l2.1-8.2H6.2"/><circle cx="9.5" cy="19.6" r="1.3"/><circle cx="17" cy="19.6" r="1.3"/>'),
    plus: ico('<path d="M12 5v14M5 12h14"/>'),
    share: ico('<path d="M12 3.5v11M7.5 8L12 3.5 16.5 8"/><path d="M5 12.5V19a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6.5"/>'),
    fwd: ico('<path d="M9 5l7 7-7 7"/>', 'class="flip"'),
    more: ico('<circle cx="5.5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="18.5" cy="12" r="1.3"/>'),
    edit: ico('<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4z"/><path d="M13.5 6.5l4 4"/>'),
    print: ico('<path d="M7 9V3.5h10V9"/><rect x="3.5" y="9" width="17" height="8" rx="2"/><path d="M7 14h10v6.5H7z"/>'),
    link: ico('<path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1"/><path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1"/>'),
    folder: ico('<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>'),
    send: ico('<path d="M4 12l16-8-6 16-2.5-6.5z"/><path d="M11.5 13.5L20 4"/>'),
    dice: ico('<rect x="4" y="4" width="16" height="16" rx="3.5"/><circle cx="9" cy="9" r="1.1"/><circle cx="15" cy="15" r="1.1"/><circle cx="15" cy="9" r="1.1"/><circle cx="9" cy="15" r="1.1"/>'),
    basket: ico('<path d="M3 10h18l-1.8 9.2a2 2 0 0 1-2 1.8H6.8a2 2 0 0 1-2-1.8z"/><path d="M8 10l3-6M16 10l-3-6M9 14v3M15 14v3"/>'),
    tag: ico('<path d="M3.5 12.2V4.5a1 1 0 0 1 1-1h7.7l8.3 8.3a1.5 1.5 0 0 1 0 2.1l-6.1 6.1a1.5 1.5 0 0 1-2.1 0z"/><circle cx="8" cy="8" r="1.4"/>'),
    grip: ico('<circle cx="9" cy="6" r="1.1"/><circle cx="15" cy="6" r="1.1"/><circle cx="9" cy="12" r="1.1"/><circle cx="15" cy="12" r="1.1"/><circle cx="9" cy="18" r="1.1"/><circle cx="15" cy="18" r="1.1"/>'),
    camera: ico('<path d="M4 8h3l1.6-2.5h6.8L17 8h3a1 1 0 0 1 1 1v9.5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.6"/>'),
    download: ico('<path d="M12 3.5v12M7.5 11l4.5 4.5 4.5-4.5"/><path d="M4.5 19.5h15"/>'),
  };

  /* ---------- amounts: ½× to 3×, and added up on the shopping list (the same rules as the Android app) ---------- */
  const Amt = (() => {
    const GLYPHS = { "½": 0.5, "⅓": 1 / 3, "⅔": 2 / 3, "¼": 0.25, "¾": 0.75, "⅕": 0.2, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875 };
    const G = "½⅓⅔¼¾⅕⅛⅜⅝⅞";
    const Q = `(?:\\d+\\s+\\d+\\s*/\\s*\\d+|\\d+\\s*/\\s*\\d+|\\d+(?:[.,]\\d+)?\\s*[${G}]?|[${G}])`;
    const HEBREW = [["חצי", 0.5], ["רבע", 0.25], ["שליש", 1 / 3]];
    const NICE = [[0, ""], [0.125, "⅛"], [0.25, "¼"], [1 / 3, "⅓"], [0.5, "½"], [2 / 3, "⅔"], [0.75, "¾"], [1, ""]];
    const SIMPLE = new RegExp(`^(\\d+(?:\\.\\d+)?)?\\s*([${G}])?$`);
    function value(q) {
      const s = q.trim().replace(/,/g, ".");
      let m = s.match(/^(\d+)\s+(\d+)\s*\/\s*(\d+)$/);
      if (m) return +m[3] ? +m[1] + m[2] / m[3] : null;
      if ((m = s.match(/^(\d+)\s*\/\s*(\d+)$/))) return +m[2] ? m[1] / m[2] : null;
      if ((m = s.match(SIMPLE))) {
        if (!m[1] && !m[2]) return null;
        return (m[1] ? parseFloat(m[1]) : 0) + (m[2] ? GLYPHS[m[2]] : 0);
      }
      return null;
    }
    function fmt(x) {
      if (x >= 20) return String(Math.round(x));
      const whole = Math.floor(x), frac = x - whole;
      const near = NICE.reduce((a, b) => (Math.abs(b[0] - frac) < Math.abs(a[0] - frac) ? b : a));
      if (Math.abs(near[0] - frac) < 0.04) {
        const w = near[0] === 1 ? whole + 1 : whole;
        return !near[1] ? String(w) : w === 0 ? near[1] : w + near[1];
      }
      return String(Math.round(x * 10) / 10);
    }
    const UNITS = [["cup", "cups"], ["clove", "cloves"], ["can", "cans"], ["tablespoon", "tablespoons"], ["teaspoon", "teaspoons"],
      ["pound", "pounds"], ["ounce", "ounces"], ["slice", "slices"], ["piece", "pieces"], ["stick", "sticks"], ["bunch", "bunches"],
      ["pinch", "pinches"], ["handful", "handfuls"], ["sprig", "sprigs"], ["package", "packages"], ["jar", "jars"], ["bag", "bags"],
      ["head", "heads"], ["lb", "lbs"], ["egg", "eggs"], ["sheet", "sheets"], ["thumb", "thumbs"], ["portion", "portions"],
      ["fillet", "fillets"], ["bowl", "bowls"]];
    function agree(rest, x) {                          // "2 cup" → "2 cups" after the first number
      const m = rest.match(/^(\s*)([A-Za-z]+)([\s\S]*)$/);
      if (!m) return rest;
      const pair = UNITS.find((p) => p[0] === m[2].toLowerCase() || p[1] === m[2].toLowerCase());
      if (!pair) return rest;
      const want = x > 1 ? pair[1] : pair[0];
      return m[1] + (/[A-Z]/.test(m[2][0]) ? want[0].toUpperCase() + want.slice(1) : want) + m[3];
    }
    const COMBO = new RegExp(`(${Q})(?:(\\s*(?:-|–|—|to|עד)\\s*)(${Q}))?`, "g");
    const ws = (x) => x.match(/ *$/)[0];
    // every number in the amount × factor ("2 cups (480ml)" → "4 cups (960ml)"); "to taste" stays as it is
    function scale(amount, factor) {
      amount = amount || "";
      if (factor === 1 || !amount.trim()) return amount;
      let out = "", last = 0, first = null, firstEnd = 0;
      for (const m of amount.matchAll(COMBO)) {
        const a = value(m[1]);
        if (a == null) continue;
        const sep = m[2] || "", to = m[3] || "";
        const b = to ? value(to) : null;
        out += amount.slice(last, m.index) + fmt(a * factor) + ws(m[1]);
        if (b != null) out += sep + fmt(b * factor) + ws(to);
        else if (to) out += sep + to;
        last = m.index + m[0].length;
        if (first == null) { first = (b != null ? b : a) * factor; firstEnd = out.length; }
      }
      if (first == null) {
        for (const [w, v] of HEBREW) if (new RegExp(`(^|\\s)${w}(\\s|$)`).test(amount)) return amount.replace(w, fmt(v * factor));
        return amount;
      }
      out += amount.slice(last);
      return out.slice(0, firstEnd) + agree(out.slice(firstEnd), first);
    }
    const UNIT_KEY = new Map(Object.entries({
      cup: "cup", cups: "cup", c: "cup", tbsp: "tbsp", tbs: "tbsp", tablespoon: "tbsp", tablespoons: "tbsp", "כף": "tbsp", "כפות": "tbsp",
      tsp: "tsp", teaspoon: "tsp", teaspoons: "tsp", "כפית": "tsp", "כפיות": "tsp", g: "g", gr: "g", gram: "g", grams: "g", "גרם": "g",
      kg: "kg", ml: "ml", l: "l", liter: "l", liters: "l", litre: "l", lb: "lb", lbs: "lb", pound: "lb", pounds: "lb", oz: "oz",
      ounce: "oz", ounces: "oz", clove: "clove", cloves: "clove", can: "can", cans: "can", "כוס": "cup", "כוסות": "cup" }));
    const UNIT_SHOW = { cup: ["cup", "cups"], clove: ["clove", "cloves"], can: ["can", "cans"] };
    // the same thing from two recipes is one line: "Eggs" and "egg" both buy eggs
    const key = (item) => norm(item).split(" ").map((w) =>
      w.length > 4 && w.endsWith("ies") ? w.slice(0, -3) + "y" : w.length > 4 && w.endsWith("oes") ? w.slice(0, -2)
        : w.length > 3 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w).join(" ");
    const LEAD = new RegExp(`^\\s*(${Q})\\s*(.*)$`);
    function total(amounts) {                          // added up where the units agree, the rest after a +
      if (amounts.length <= 1) return amounts[0] || "";
      const sums = new Map(), other = [];
      for (const a of amounts) {
        const m = a.match(LEAD);
        const v = m ? value(m[1]) : null;
        const rest = m ? m[2].trim().toLowerCase() : "";
        const unit = rest ? UNIT_KEY.get(rest.split(" ")[0]) : "";
        if (v == null || unit == null || (unit && rest.includes(" "))) { if (!other.includes(a)) other.push(a); }
        else sums.set(unit, (sums.get(unit) || 0) + v);
      }
      const parts = [...sums].map(([u, v]) => (u ? `${fmt(v)} ${UNIT_SHOW[u] ? UNIT_SHOW[u][v > 1 ? 1 : 0] : u}` : fmt(v)));
      return parts.concat(other).join(" + ");
    }
    function merge(items) {
      const groups = new Map();
      items.forEach((i) => { const k = key(i.item); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(i); });
      return [...groups].map(([k, xs]) => ({ key: k, item: xs[0].item, amount: total(xs.map((x) => (x.amount || "").trim()).filter(Boolean)),
        ids: xs.map((x) => x.id), done: xs.every((x) => x.done), codes: [...new Set(xs.map((x) => x.code).filter(Boolean))] }));
    }
    return { scale, merge, total, key, fmt };
  })();
  const FACTORS = [[0.5, "½×"], [1, "1×"], [1.5, "1½×"], [2, "2×"], [3, "3×"]];
  const factors = {};                                  // code → the amounts picked on this visit
  const factor = (code) => factors[code] || 1;

  /* ---------- days (weeks start on Sunday) ---------- */
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const fromIso = (k) => { const [y, m, d] = k.split("-").map(Number); return new Date(y, m - 1, d); };
  const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
  const today0 = () => { const n = new Date(); return new Date(n.getFullYear(), n.getMonth(), n.getDate()); };
  const weekStart = (d) => addDays(d, -d.getDay());
  const dayName = (d) => { const t = iso(today0()); return iso(d) === t ? "Today" : iso(addDays(d, -1)) === t ? "Tomorrow" : d.toLocaleDateString(undefined, { weekday: "long" }); };
  const shortDate = (d) => d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const newId = () => {
    const a = new Uint8Array(4);
    try { crypto.getRandomValues(a); } catch (e) { a.forEach((_, i) => { a[i] = Math.floor(Math.random() * 256); }); }
    return [...a].map((x) => x.toString(16).padStart(2, "0")).join("");
  };

  /* Labels on a recipe page follow the recipe's language. */
  const L = {
    en: { ing: "Ingredients", steps: "Steps", tips: "Tips", nut: "Nutrition", miss: "Not in the reel", serves: "Serves", makes: "Makes",
      prep: "Prep", cook: "Cook", total: "Total", oven: "Oven", start: "Start cooking", cont: (n) => `Continue · step ${n}`,
      watch: "Watch the reel", page: "Recipe page", read: "Read aloud", stopRead: "Stop", awake: "Keep the screen on",
      step: (k, n) => `Step ${k} of ${n}`, next: "Next", backStep: "Back", done: "Done", finished: "Made it", again: "Start again",
      toRecipe: "Back to the recipe", uses: "Uses", timer: (m) => `Timer ${fmtMin(m)}`, noAmt: "no amount", calories: "Calories",
      protein: "Protein", carbs: "Carbs", fat: "Fat", close: "Close", notRecipe: "Not a recipe", mine: "Mine", rating: "Rating",
      notes: "Notes", madeIt: "I made it", made: (n, d) => `Made ${n === 1 ? "once" : n + " times"} · ${d}`,
      posted: (d) => `Posted ${d}`, added: (d, who) => `Added ${d}` + (who ? ` by ${who}` : ""), insta: "Instagram",
      amounts: "Amounts", plan: "Plan", list: "Add to list", onList: "On the list",
      more: "More", edit: "Fix this recipe", print: "Print", share: "Share a link", collections: "Collections", ask: "Ask",
      askPh: "Ask about this recipe", asking: "…", again2: "Again, like last time", edited: (d) => `Edited ${d}`, noteLbl: "Note",
      title: "Title", summary: "Summary", servings: "Serves", group: "Group", amount: "Amount", item: "Ingredient", note: "Note",
      addIng: "Ingredient", addGroup: "Group", addStep: "Step", save: "Save", cancel: "Cancel", revert: "Undo my changes" },
    he: { ing: "מצרכים", steps: "אופן ההכנה", tips: "טיפים", nut: "ערכים תזונתיים", miss: "חסר בסרטון", serves: "מנות", makes: "כמות",
      prep: "הכנה", cook: "בישול", total: "סה״כ", oven: "תנור", start: "מתחילים לבשל", cont: (n) => `ממשיכים · שלב ${n}`,
      watch: "לצפייה בסרטון", page: "דף המתכון", read: "הקראה", stopRead: "עצירה", awake: "המסך נשאר דולק",
      step: (k, n) => `שלב ${k} מתוך ${n}`, next: "הבא", backStep: "הקודם", done: "סיימתי", finished: "בתיאבון", again: "מההתחלה",
      toRecipe: "חזרה למתכון", uses: "צריך", timer: (m) => `טיימר ${m} דק׳`, noAmt: "בלי כמות", calories: "קלוריות", protein: "חלבון",
      carbs: "פחמימות", fat: "שומן", close: "סגירה", notRecipe: "לא מתכון", mine: "שלי", rating: "דירוג", notes: "הערות",
      madeIt: "הכנתי", made: (n, d) => `הוכן ${n === 1 ? "פעם אחת" : n + " פעמים"} · ${d}`,
      posted: (d) => `פורסם ${d}`, added: (d, who) => `נוסף ${d}` + (who ? ` על ידי ${who}` : ""), insta: "אינסטגרם",
      amounts: "כמויות", plan: "לתכנן", list: "לרשימת הקניות", onList: "ברשימה",
      more: "עוד", edit: "תיקון המתכון", print: "הדפסה", share: "קישור לשיתוף", collections: "אוספים", ask: "שאלה",
      askPh: "שאלה על המתכון", asking: "…", again2: "שוב, כמו בפעם הקודמת", edited: (d) => `נערך ${d}`, noteLbl: "הערה",
      title: "שם", summary: "תקציר", servings: "מנות", group: "קבוצה", amount: "כמות", item: "מצרך", note: "הערה",
      addIng: "מצרך", addGroup: "קבוצה", addStep: "שלב", save: "שמירה", cancel: "ביטול", revert: "ביטול השינויים שלי" },
  };
  const lab = (r) => L[r && r.lang === "he" ? "he" : "en"];
  // what the source didn't give: a reel, a page or photos
  const missLabel = (r) => (r && r.source === "web" ? (r.lang === "he" ? "חסר בדף" : "Not on the page")
    : r && r.source === "photo" ? (r.lang === "he" ? "חסר בתמונות" : "Not in the photos") : lab(r).miss);
  const dirOf = (r) => (r && r.lang === "he" ? ' dir="rtl" lang="he"' : ' dir="ltr" lang="en"');
  const WHY = { saved: () => "Saved", again: (a) => "Not made since " + day(a), like: (a) => "Like " + a, new: () => "New" };

  /* ---------- talking to the server ---------- */
  class SignedOut extends Error {}
  async function getJSON(u) {
    const r = await fetch(u, { cache: "no-store", credentials: "same-origin" });
    if (r.status === 401) throw new SignedOut();
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }
  async function post(u, body) {
    const r = await fetch(u, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-Matkon": "1" }, body: JSON.stringify(body || {}) });
    const d = await r.json().catch(() => ({}));
    if (r.status === 401 && u !== "api/signin") throw new SignedOut();
    if (!r.ok) throw new Error(d.error || "Something went wrong.");
    return d;
  }
  async function remember(op, args) {
    try {
      const d = await post("api/me", Object.assign({ op }, args));
      ME.memory = d.memory;
      SUGGEST = null;
    } catch (e) { if (e instanceof SignedOut) signInPage(); }
  }
  // the week plan and the shopping list: changed on the page at once, then on the server one at a time, in order
  const queue = [];
  let sending = false;
  function change(op, args, local) {
    if (local) local(M());
    paint();
    queue.push(Object.assign({ op }, args));
    if (!sending) send();
  }
  async function send() {
    sending = true;
    let last = null, lost = false;
    while (queue.length) {
      try { last = await post("api/me", queue[0]); }
      catch (e) {
        if (e instanceof SignedOut) { queue.length = 0; sending = false; signInPage(); return; }
        lost = true;
      }
      queue.shift();
    }
    sending = false;
    if (lost) { try { ME = await getJSON("api/me"); } catch (e) { /* the next visit catches up */ } }
    else if (last) ME.memory = last.memory;
    SUGGEST = null;
    if (!queue.length) paint();
  }
  async function loadAll(force) {
    if (!ME || force) ME = await getJSON("api/me");
    if (!LIST || force) LIST = await getJSON("api/recipes");
  }
  // a recipe in the language picked for it on this visit (the account's default otherwise)
  const langChoice = {};
  const key = (code) => code + "|" + (langChoice[code] || "");
  const cur = (code) => FULL[key(code)];
  async function loadOne(code) {
    const k = key(code);
    if (!FULL[k]) FULL[k] = await getJSON("api/r/" + encodeURIComponent(code) + (langChoice[code] ? "?lang=" + langChoice[code] : ""));
    return FULL[k];
  }
  // what a card shows: the English title of a Hebrew recipe for an account that reads them in English
  const english = () => ME && ME.memory.settings.english;
  const shown = (r) => (english() && r.title_en ? { title: r.title_en, lang: "en" } : { title: r.title, lang: r.lang });
  const M = () => ME.memory;
  const nameOf = (id) => (ME.names && ME.names[id]) || id;
  const isOwner = () => ME.account && ME.account.admin;

  /* ---------- units: as written, metric or US (units.js), for this account ---------- */
  const units = () => (ME && ME.memory.settings && ME.memory.settings.units) || "";
  const UA = (a, lang) => (window.MatkonUnits && units() ? MatkonUnits.amount(a || "", units(), lang) : a);
  const UT = (t, lang) => (window.MatkonUnits && units() ? MatkonUnits.text(t || "", units(), lang) : t);
  const heText = (x) => /[\u0590-\u05FF]/.test(x || "");

  /* ---------- where a recipe came from: a reel, a recipe page or photos ---------- */
  const byline = (r) => (r.source === "photo" ? nameOf(r.added_by) : r.source === "web" ? r.user || "" : r.user ? "@" + r.user : "");
  function sourceLinks(r, l) {
    if (r.source === "photo") return "";
    if (r.source === "web") return `${r.user ? `<a href="#/from/${encodeURIComponent(r.user)}">${esc(r.user)}</a>` : ""}${r.reel ? `<a href="${esc(r.reel)}" target="_blank" rel="noopener">${esc(l.page)}</a>` : ""}`;
    return `${r.user ? `<a href="#/from/${encodeURIComponent(r.user)}">@${esc(r.user)}</a>` : ""}${r.reel ? `<a href="${esc(r.reel)}" target="_blank" rel="noopener">${esc(l.insta)}</a>` : ""}${r.link ? `<a href="${esc(r.link)}" target="_blank" rel="noopener">${esc(l.page)}</a>` : ""}`;
  }

  /* ---------- search: every word must be there, in the steps too, and a typo is forgiven ---------- */
  const HAY = new WeakMap();
  function hayOf(r) {
    let h = HAY.get(r);
    if (!h) {
      const s = norm([r.title, r.title_en, r.user, r.cuisine, r.kind, nameOf(r.added_by), (r.tags || []).join(" "), (r.items || []).join(" "),
        (r.items_en || []).join(" "), r.text || "", r.text_en || ""].join(" "));
      h = { s, words: [...new Set(s.split(" "))] };
      HAY.set(r, h);
    }
    return h;
  }
  function near(a, b, max) {                          // at most `max` letters different (Levenshtein)
    if (Math.abs(a.length - b.length) > max) return false;
    let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i++) {
      const row = [i];
      let best = i;
      for (let j = 1; j <= b.length; j++) {
        row[j] = Math.min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
        best = Math.min(best, row[j]);
      }
      if (best > max) return false;
      prev = row;
    }
    return prev[b.length] <= max;
  }
  function wordHit(w, h) {
    if (h.s.includes(w)) return true;
    if (w.length < 4) return false;
    const max = w.length >= 7 ? 2 : 1;
    return h.words.some((x) => x.length >= 3 && (near(w, x, max) || (x.length > w.length && near(w, x.slice(0, w.length), max))));
  }
  const matches = (r, words) => { const h = hayOf(r); return words.every((w) => wordHit(w, h)); };

  /* ---------- ticked ingredients and the cooking step (kept on the server) ---------- */
  const ticked = (code) => new Set(M().ticks[code] || []);
  let tickTimer = null;
  function saveTicks(code, set) {
    M().ticks[code] = [...set];
    clearTimeout(tickTimer);
    tickTimer = setTimeout(() => remember("ticks", { code, keys: [...set] }), 600);
  }

  /* ---------- reading aloud ---------- */
  const canSpeak = "speechSynthesis" in window;
  let speaking = null;
  function speak(parts, key, lang, onEnd) {
    if (!canSpeak) return;
    speechSynthesis.cancel();
    if (speaking === key) { speaking = null; onEnd && onEnd(); return; }
    speaking = key;
    const he = lang === "he";
    const vs = speechSynthesis.getVoices().filter((v) => (he ? /^he|^iw/i : /^en/i).test(v.lang));
    const voice = vs.find((v) => /natural|samantha|aria|jenny|google/i.test(v.name)) || vs[0] || null;
    parts.filter(Boolean).forEach((text, i, all) => {
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 0.95; u.lang = he ? "he-IL" : "en-US";
      if (voice) u.voice = voice;
      if (i === all.length - 1) u.onend = u.onerror = () => { if (speaking === key) speaking = null; onEnd && onEnd(); };
      speechSynthesis.speak(u);
    });
  }
  function stopSpeaking() { if (canSpeak) speechSynthesis.cancel(); speaking = null; }

  /* ---------- keep the screen on ---------- */
  let wakeLock = null, wantWake = false;
  async function setWake(on) {
    wantWake = on;
    if (!("wakeLock" in navigator)) return;
    try {
      if (on && !wakeLock && document.visibilityState === "visible") {
        wakeLock = await navigator.wakeLock.request("screen");
        wakeLock.addEventListener("release", () => { wakeLock = null; });
      } else if (!on && wakeLock) { await wakeLock.release(); wakeLock = null; }
    } catch (e) { wakeLock = null; }
  }
  document.addEventListener("visibilitychange", () => { if (wantWake) setWake(true); });

  /* ---------- kitchen timer (on this device; survives page changes and reloads) ---------- */
  let timer = store.get("timer", null); // {end, label, code, min}
  let ringing = false, audio = null, beepAt = 0;
  function unlockAudio() {
    try {
      if (!audio) audio = new (window.AudioContext || window.webkitAudioContext)();
      if (audio.state === "suspended") audio.resume();
    } catch (e) { audio = null; }
  }
  const UNLOCK_ON = ["pointerdown", "pointerup", "click", "keydown"];
  function onFirstTap() {
    unlockAudio();
    if (ringing && Date.now() - beepAt > 1000) { beepAt = Date.now(); beep(); }
    if (audio && audio.state === "running") UNLOCK_ON.forEach((t) => document.removeEventListener(t, onFirstTap, true));
  }
  UNLOCK_ON.forEach((t) => document.addEventListener(t, onFirstTap, true));
  function beep() {
    if (!audio) return;
    const t0 = audio.currentTime;
    [0, 0.35, 0.7].forEach((d) => {
      const o = audio.createOscillator(), g = audio.createGain();
      o.type = "square"; o.frequency.value = 880;
      g.gain.setValueAtTime(0.0001, t0 + d);
      g.gain.exponentialRampToValueAtTime(0.25, t0 + d + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + d + 0.25);
      o.connect(g).connect(audio.destination);
      o.start(t0 + d); o.stop(t0 + d + 0.27);
    });
  }
  let timeup = null;
  function showTimeup() {
    if (!timeup) { timeup = document.createElement("div"); timeup.id = "timeup"; timeup.setAttribute("role", "alertdialog"); document.body.appendChild(timeup); }
    timeup.innerHTML = `<div class="box">${I.clock}<h2>Time's up</h2><p>${esc(timer.label)}${timer.min ? " · " + esc(fmtMin(timer.min)) : ""}</p>
      <button type="button" class="btn btn-accent btn-big" data-action="timer-stop">OK</button></div>`;
    timeup.hidden = false;
    const ok = timeup.querySelector("button"); ok && ok.focus({ preventScroll: true });
  }
  function startTimer(min, code, label) {
    unlockAudio();
    timer = { end: Date.now() + min * 60000, label, code, min };
    ringing = false; store.set("timer", timer); tick(); render(true);
  }
  function stopTimer() {
    timer = null; ringing = false; store.set("timer", null);
    if (navigator.vibrate) { try { navigator.vibrate(0); } catch (e) { /* ok */ } }
    if (timeup) timeup.hidden = true;
    tick(); render(true);
  }
  function tick() {
    document.body.classList.toggle("has-timer", !!timer);
    if (!timer) { timerbar.hidden = true; timerbar.classList.remove("ring"); if (timeup) timeup.hidden = true; return; }
    const left = timer.end - Date.now();
    timerbar.hidden = false;
    if (left <= 0) {
      if (!ringing) {
        ringing = true; showTimeup();
        if (navigator.vibrate) { try { navigator.vibrate([500, 250, 500, 250, 500]); } catch (e) { /* ok */ } }
      }
      timerbar.classList.add("ring");
      timerbar.innerHTML = `<span class="t">Time's up · ${esc(timer.label)}</span><button type="button" data-action="timer-stop">OK</button>`;
      if (audio && audio.state === "running" && Date.now() - beepAt > 2400) { beepAt = Date.now(); beep(); }
    } else {
      timerbar.classList.remove("ring");
      timerbar.innerHTML = `<span class="t" role="timer">${esc(fmtClock(left))} · ${esc(timer.label)}</span><button type="button" data-action="timer-stop">Stop</button>`;
    }
    document.querySelectorAll("[data-countdown]").forEach((el) => { el.textContent = left > 0 ? fmtClock(left) : "0:00"; });
  }
  setInterval(() => { if (timer) tick(); }, 500);

  /* ---------- sign in ---------- */
  const inp = (name, label, extra, value) => `<label>${esc(label)}<input name="${name}" ${extra || ""} value="${esc(value || "")}"></label>`;
  const EMAIL_IN = 'type="email" autocomplete="email" autocapitalize="none" spellcheck="false" required';
  function signInPage(error, mode, pre) {
    ME = null; LIST = null;
    mode = mode || "signin"; pre = pre || {};
    let form;
    if (mode === "join") {
      form = `<form class="signin-box" data-form="join"><div class="mark"><img src="icon.svg" alt=""><h1>Matkon</h1></div>
        ${inp("email", "Email", EMAIL_IN, pre.email)}${inp("code", "Code", 'autocomplete="one-time-code" autocapitalize="characters" spellcheck="false" required', pre.code)}
        ${inp("name", "Name", 'autocomplete="name"')}${inp("username", "Username", 'autocomplete="username" autocapitalize="none" spellcheck="false" required minlength="2"')}
        ${inp("password", "Password", 'type="password" autocomplete="new-password" required minlength="8"')}
        ${error ? `<p class="err" role="alert">${esc(error)}</p>` : ""}
        <button class="btn btn-accent btn-big" type="submit">Join</button>
        <button class="link" type="button" data-action="mode" data-mode="signin">Sign in</button></form>`;
    } else if (mode === "forgot") {
      form = `<form class="signin-box" data-form="forgot"><div class="mark"><img src="icon.svg" alt=""><h1>Matkon</h1></div>
        ${inp("email", "Email", EMAIL_IN, pre.email)}${error ? `<p class="err" role="alert">${esc(error)}</p>` : ""}
        <button class="btn btn-accent btn-big" type="submit">Send a code</button>
        <button class="link" type="button" data-action="mode" data-mode="signin">Sign in</button></form>`;
    } else if (mode === "reset") {
      form = `<form class="signin-box" data-form="reset-pw"><div class="mark"><img src="icon.svg" alt=""><h1>Matkon</h1></div>
        ${inp("email", "Email", EMAIL_IN, pre.email)}${inp("code", "Code", 'inputmode="numeric" autocomplete="one-time-code" required')}
        ${inp("password", "New password", 'type="password" autocomplete="new-password" required minlength="8"')}
        ${error ? `<p class="err" role="alert">${esc(error)}</p>` : ""}
        <button class="btn btn-accent btn-big" type="submit">Set password</button>
        <button class="link" type="button" data-action="mode" data-mode="signin">Sign in</button></form>`;
    } else {
      form = `<form class="signin-box" data-form="signin"><div class="mark"><img src="icon.svg" alt=""><h1>Matkon</h1></div>
        ${inp("username", "Username or email", 'autocomplete="username" autocapitalize="none" spellcheck="false" required')}
        ${inp("password", "Password", 'type="password" autocomplete="current-password" required')}
        ${error ? `<p class="err" role="alert">${esc(error)}</p>` : ""}
        <button class="btn btn-accent btn-big" type="submit">Sign in</button>
        <div class="links"><button class="link" type="button" data-action="mode" data-mode="join">I have a code</button>
          <button class="link" type="button" data-action="mode" data-mode="forgot">Forgot password</button></div></form>`;
    }
    app.innerHTML = `<div class="signin">${form}</div>`;
    document.title = "Matkon";
    const first = [...app.querySelectorAll("input")].find((i) => !i.value); (first || app.querySelector("input")) && (first || app.querySelector("input")).focus();
  }

  /* ---------- the top bar ---------- */
  function topBar(title) {
    const here = route()[0];
    const nav = [["add", "Add", I.plus], ["week", "Week", I.cal], ["list", "List", I.cart], ["history", "History", I.history], ["settings", "Settings", I.gear]];
    return `<header class="top"><a class="mark" href="#/"><img src="icon.svg" alt=""><h1>${esc(title || "Matkon")}</h1></a>
      <nav class="topnav">${nav.map(([k, n, i]) => `<a class="btn btn-icon" href="#/${k}" aria-label="${n}"${k === here ? ' aria-current="page"' : ""}>${i}</a>`).join("")}</nav></header>`;
  }

  /* ---------- a bottom sheet, and a line at the bottom with Open ---------- */
  function sheet(label, inner, onClick) {
    const el = document.createElement("div");
    el.className = "sheet";
    el.innerHTML = `<div class="panel" role="dialog" aria-modal="true" aria-label="${esc(label)}"><div class="grip"></div>
      <div class="bar"><h2>${esc(label)}</h2><button type="button" class="btn" data-close>Close</button></div>${inner}</div>`;
    const close = () => { el.remove(); document.removeEventListener("keydown", onKey); window.removeEventListener("hashchange", close); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    el.addEventListener("click", (e) => { if (e.target === el || e.target.closest("[data-close]")) close(); else onClick(e, close); });
    document.addEventListener("keydown", onKey);
    window.addEventListener("hashchange", close);
    document.body.appendChild(el);
    el.querySelector("[data-close]").focus();
    return el;
  }
  function pickDay(label, onPick) {
    const t = today0();
    const days = Array.from({ length: 14 }, (_, i) => addDays(t, i));
    sheet(label, `<ul class="days">${days.map((d) => `<li><button type="button" class="dayrow" data-day="${iso(d)}"><span>${esc(dayName(d))}</span><span class="sub">${esc(shortDate(d))}</span></button></li>`).join("")}</ul>`,
      (e, close) => { const b = e.target.closest("[data-day]"); if (b) { close(); onPick(b.dataset.day); } });
  }
  let toastEl = null;
  function toast(text, href) {
    if (!toastEl) { toastEl = document.createElement("div"); toastEl.className = "toast"; toastEl.setAttribute("role", "status"); document.body.appendChild(toastEl); }
    toastEl.innerHTML = `<span dir="auto">${esc(text)}</span>${href ? `<a href="${href}">Open</a>` : ""}`;
    toastEl.classList.toggle("plain", !href);
    toastEl.hidden = false;
    clearTimeout(toast.t);
    toast.t = setTimeout(() => { toastEl.hidden = true; }, 5000);
  }

  /* ---------- home ---------- */
  const recipesOnly = () => LIST.recipes.filter((r) => r.is_recipe !== false);
  const byCode = (c) => LIST.recipes.find((r) => r.code === c);
  function haystack(r) { return norm([r.title, r.title_en, r.user, r.cuisine, r.kind, nameOf(r.added_by), (r.tags || []).join(" "), (r.items || []).join(" "), (r.items_en || []).join(" ")].join(" ")); }
  function visible() {
    const words = norm(query).split(" ").filter(Boolean);
    return recipesOnly()
      .filter((r) => !creator || r.user === creator)
      .filter((r) => kind === "All" || (kind === "Saved" ? M().saved[r.code] : kind === "Made" ? M().cooked_count[r.code]
        : kind.startsWith("c:") ? (collOf(kind.slice(2)) || { codes: [] }).codes.includes(r.code) : r.kind === kind))
      .filter((r) => matches(r, words))
      .sort(SORTS[sortBy] || SORTS.added);
  }
  const SORTS = {
    added: (a, b) => (b.found || 0) - (a.found || 0),
    posted: (a, b) => (b.posted || 0) - (a.posted || 0),
    az: (a, b) => shown(a).title.localeCompare(shown(b).title),
  };
  function creators() {                               // every creator in the kitchen, most recipes first
    const n = {};
    recipesOnly().forEach((r) => { if (r.user) n[r.user] = (n[r.user] || 0) + 1; });
    return Object.entries(n).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }
  function filterHTML() {
    const sorts = [["added", "Added"], ["posted", "Posted"], ["az", "A–Z"]];
    return `<h3>Sort</h3><div class="chips">${sorts.map(([k, n]) => `<button type="button" data-action="sort" data-sort="${k}" aria-pressed="${k === sortBy}">${n}</button>`).join("")}</div>
      <h3>Creator</h3><div class="chips"><button type="button" data-action="creator" data-user="" aria-pressed="${!creator}">All</button>${creators().map(([u, n]) =>
        `<button type="button" data-action="creator" data-user="${esc(u)}" aria-pressed="${u === creator}" dir="ltr">@${esc(u)}<span class="n">${n}</span></button>`).join("")}</div>`;
  }
  function openFilter() {
    const el = document.createElement("div");
    el.className = "sheet";
    el.innerHTML = `<div class="panel filter" role="dialog" aria-modal="true" aria-label="Sort and filter"><div class="grip"></div>
      <div class="bar"><h2>Sort and filter</h2><button type="button" class="btn" data-close>Done</button></div><div class="fbody">${filterHTML()}</div></div>`;
    const close = () => { el.remove(); document.removeEventListener("keydown", onKey); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    el.addEventListener("click", (e) => {
      const b = e.target.closest("[data-action]");
      if (b && b.dataset.action === "sort") {
        sortBy = b.dataset.sort; store.set("sort", sortBy);
        el.querySelector(".fbody").innerHTML = filterHTML();
        const g = document.getElementById("grid"); if (g) g.innerHTML = gridHTML();
        const t = document.querySelector('[data-action="filter"]'); if (t) t.setAttribute("aria-pressed", filtered());
      } else if (b && b.dataset.action === "creator") {
        close();
        location.hash = b.dataset.user ? "#/from/" + encodeURIComponent(b.dataset.user) : "#/";
      } else if (e.target === el || e.target.closest("[data-close]")) close();
    });
    document.addEventListener("keydown", onKey);
    document.body.appendChild(el);
    el.querySelector("[data-close]").focus();
  }
  const filtered = () => !!creator || sortBy !== "added";
  function cardHTML(r) {
    const saved = M().saved[r.code], made = M().cooked_count[r.code], rating = M().ratings[r.code];
    return `<li><a class="card" href="#/r/${esc(r.code)}">
      <div class="pic">${r.photo ? `<img src="${esc(r.photo)}" alt="" loading="lazy">` : ""}${r.complete ? "" : `<span class="flag">${r.lang === "he" ? "חסרות כמויות" : "Missing amounts"}</span>`}
        ${saved || made || rating ? `<span class="marks">${saved ? `<span>${I.markOn}</span>` : ""}${made ? `<span>${I.done}</span>` : ""}${rating ? `<span class="r">${rating}</span>` : ""}</span>` : ""}</div>
      <div class="txt"${dirOf(shown(r))}><div class="t">${esc(shown(r).title)}</div><div class="by" dir="auto">${esc(byline(r))}</div>${sortBy === "posted" && r.posted ? `<div class="by">${esc(day(r.posted, shown(r).lang))}</div>` : ""}</div></a></li>`;
  }
  function gridHTML() {
    const list = visible();
    return list.length ? `<ul class="grid">${list.map(cardHTML).join("")}</ul>` : `<p class="empty">No recipes</p>`;
  }
  function kindsHTML() {
    const recipes = recipesOnly().filter((r) => !creator || r.user === creator);
    const counts = {};
    recipes.forEach((r) => { counts[r.kind] = (counts[r.kind] || 0) + 1; });
    const order = ["Breakfast", "Mains", "Salads & sides", "Soups", "Bread & dough", "Baking & sweets", "Snacks", "Sauces & dips", "Drinks"];
    const saved = recipes.filter((r) => M().saved[r.code]).length, made = recipes.filter((r) => M().cooked_count[r.code]).length;
    const kinds = [["All", recipes.length]].concat(saved ? [["Saved", saved]] : [], made ? [["Made", made]] : [], order.filter((k) => counts[k]).map((k) => [k, counts[k]]));
    const codes = new Set(recipes.map((r) => r.code));
    return kinds.map(([k, n]) => `<button type="button" data-action="kind" data-kind="${esc(k)}" aria-pressed="${k === kind}">${esc(k)}<span class="n">${n}</span></button>`).join("") +
      colls().map((c) => `<button type="button" class="coll" data-action="kind" data-kind="c:${esc(c.id)}" aria-pressed="${"c:" + c.id === kind}" dir="auto">${I.folder}${esc(c.name)}<span class="n">${c.codes.filter((x) => codes.has(x)).length}</span></button>`).join("");
  }
  /* ---------- collections: your own groups of recipes ---------- */
  const colls = () => M().collections || [];
  const collOf = (id) => colls().find((c) => c.id === id);
  function collBarHTML() {
    const c = kind.startsWith("c:") ? collOf(kind.slice(2)) : null;
    if (!c) return "";
    return `<div class="creator collbar"><span dir="auto">${I.folder}${esc(c.name)}</span><span class="grow"></span>
      <button type="button" class="btn" data-action="coll-rename" data-id="${esc(c.id)}">Rename</button>
      <button type="button" class="btn btn-icon" data-action="coll-delete" data-id="${esc(c.id)}" aria-label="Delete">${I.trash}</button></div>`;
  }
  function collSheet(code) {
    const body = () => `<ul class="days">${colls().map((c) => { const on = c.codes.includes(code);
        return `<li><button type="button" class="dayrow" data-coll="${esc(c.id)}" aria-pressed="${on}"><span dir="auto">${esc(c.name)}</span><span class="tick${on ? " on" : ""}">${I.check}</span></button></li>`; }).join("")}</ul>
      <form class="addrow" data-sheet="coll-new"><input name="name" type="text" placeholder="New collection" aria-label="New collection" maxlength="60" dir="auto" autocomplete="off">
        <button class="btn btn-icon" type="submit" aria-label="Add">${I.plus}</button></form>`;
    const el = sheet("Collections", `<div class="cbody">${body()}</div>`, (e) => {
      const b = e.target.closest("[data-coll]");
      if (!b) return;
      const id = b.dataset.coll, c = collOf(id), on = !c.codes.includes(code);
      change(on ? "coll-add" : "coll-remove", { id, code }, (m) => { const x = (m.collections || []).find((y) => y.id === id); if (x) x.codes = on ? x.codes.concat([code]) : x.codes.filter((k) => k !== code); });
      el.querySelector(".cbody").innerHTML = body();
    });
    el.addEventListener("submit", (e) => {
      e.preventDefault(); e.stopPropagation();
      const name = e.target.elements.name.value.trim();
      if (!name) return;
      const id = newId();
      change("coll-new", { id, name }, (m) => { m.collections = (m.collections || []).concat([{ id, name, codes: [] }]); });
      change("coll-add", { id, code }, (m) => { const x = m.collections.find((y) => y.id === id); if (x) x.codes = x.codes.concat([code]); });
      el.querySelector(".cbody").innerHTML = body();
      const i = el.querySelector("input[name=name]"); if (i) i.focus();
    });
  }

  /* ---------- Surprise me: one recipe for tonight, from Up next, nothing made in the last five days ---------- */
  async function surprise() {
    try { if (!SUGGEST) SUGGEST = (await getJSON("api/suggest")).suggest; } catch (e) { /* the whole kitchen then */ }
    const recent = (c) => (M().cooked_last[c] || 0) > Date.now() / 1000 - 5 * 86400;
    let pool = (SUGGEST || []).map((x) => x.code).filter((c) => byCode(c) && !recent(c));
    if (!pool.length) pool = recipesOnly().map((r) => r.code).filter((c) => !recent(c));
    if (pool.length) location.hash = "#/r/" + encodeURIComponent(pool[Math.floor(Math.random() * pool.length)]);
  }

  function nextHTML() {
    if (!SUGGEST || !SUGGEST.length || query || kind !== "All" || creator) return "";
    const items = SUGGEST.map((s) => [s, byCode(s.code)]).filter(([, r]) => r);
    if (!items.length) return "";
    return `<section class="next" aria-label="Up next"><h2>Up next</h2><ul class="next-row">${items.map(([s, r]) => `<li><a class="mini" href="#/r/${esc(r.code)}">
      <span class="pic">${r.photo ? `<img src="${esc(r.photo)}" alt="" loading="lazy">` : ""}</span>
      <span class="why">${esc((WHY[s.why] || WHY.new)(s.about))}</span><span class="t"${dirOf(shown(r))}>${esc(shown(r).title)}</span></a></li>`).join("")}</ul></section>`;
  }
  function home() {
    const notes = [];
    if (ME.instagram && ME.instagram.signin && ME.instagram.signin.error === "signed-out") notes.push(`<a class="note-bar" href="#/settings">Instagram sign-in needed</a>`);
    else if (ME.instagram && ME.instagram.browser && ME.instagram.browser.error === "signed-out") notes.push(`<a class="note-bar" href="#/settings">Instagram sign-in needed in the browser</a>`);
    if (LIST.waiting) notes.push(`<div class="note-bar">${LIST.waiting} more on the way</div>`);
    return `<div class="wrap">
      ${topBar()}
      <div class="searchrow"><div class="search" role="search">${I.search}<input id="q" type="search" placeholder="Search" value="${esc(query)}" autocomplete="off" enterkeyhint="search" aria-label="Search">
        <button type="button" class="clear" data-action="clear" aria-label="Clear"${query ? "" : " hidden"}>${I.x}</button></div>
        <button type="button" class="btn btn-icon filter" data-action="filter" aria-label="Sort and filter" aria-pressed="${filtered()}">${I.sort}</button></div>
      ${creator ? `<div class="creator"><span dir="ltr">@${esc(creator)}</span><a class="btn btn-icon" href="#/" aria-label="All creators">${I.x}</a></div>` : ""}
      <nav class="kinds" aria-label="Kinds">${kindsHTML()}</nav>
      <div id="collbar">${collBarHTML()}</div>
      <div class="homeacts"><button type="button" class="btn" data-action="surprise">${I.dice}Surprise me</button><a class="btn" href="#/pantry">${I.basket}What can I make?</a></div>
      ${notes.join("")}
      <div id="next">${nextHTML()}</div>
      <div id="grid">${gridHTML()}</div>
    </div>`;
  }

  /* ---------- recipe ---------- */
  function factsHTML(r, l) {
    const c = [];
    if (r.servings) c.push(`<span class="chip">${I.people}${esc(/^\d+([–-]\d+)?( |$)(as\b|people|servings?\b|$)/.test(r.servings.trim()) ? l.serves : l.makes)} ${esc(r.servings)}</span>`);
    [["prep", l.prep], ["cook", l.cook], ["total", l.total]].forEach(([k, name]) => { if (r.time && r.time[k]) c.push(`<span class="chip">${I.clock}${esc(name)} ${esc(r.time[k])}</span>`); });
    if (r.oven) c.push(`<span class="chip">${I.oven}${esc(l.oven)} ${esc(UT(r.oven, r.lang))}</span>`);
    return c.length ? `<div class="chips facts">${c.join("")}</div>` : "";
  }
  function ingHTML(i, key, done, l, f, lang) {
    const amount = UA(Amt.scale(i.amount, f), lang);
    const what = `${amount ? `<span class="amt">${esc(amount)}</span> ` : ""}${esc(i.item)}${i.note ? `<span class="nt">, ${esc(i.note)}</span>` : ""}`;
    return `<li><button type="button" class="ing${done ? " done" : ""}" data-action="tick" data-k="${key}" aria-pressed="${done}">
      <span class="box">${I.check}</span><span class="what">${what}${i.amount ? "" : ` <span class="none">· ${esc(l.noAmt)}</span>`}</span></button></li>`;
  }
  function ingredientsHTML(r, l) {
    const t = ticked(r.code), f = factor(r.code);
    return r.ingredient_groups.map((g, gi) => `${g.name ? `<h3>${esc(g.name)}</h3>` : ""}<ul class="ings">${g.items.map((i, ii) => ingHTML(i, gi + "." + ii, t.has(gi + "." + ii), l, f, r.lang)).join("")}</ul>`).join("");
  }
  const hasIngs = (r) => r.ingredient_groups.some((g) => g.items.some((i) => i.item && i.item.trim()));
  function amountsHTML(r, l) {
    return `<div class="amounts" id="amounts"><span class="lbl">${esc(l.amounts)}</span><div class="chips" dir="ltr">${FACTORS.map(([f, n]) =>
      `<button type="button" data-action="factor" data-f="${f}" aria-pressed="${f === factor(r.code)}">${n}</button>`).join("")}</div></div>`;
  }
  // a recipe's ingredients onto the shopping list, at the amounts on the page
  function addToList(r) {
    const f = factor(r.code), at = Math.floor(Date.now() / 1000);
    const items = r.ingredient_groups.flatMap((g) => g.items).filter((i) => i.item && i.item.trim())
      .map((i) => ({ id: newId(), item: i.item.trim(), amount: Amt.scale(i.amount, f) }));
    if (!items.length) return false;
    change("shop-add", { code: r.code, items }, (m) => { m.shop = (m.shop || []).concat(items.map((i) => Object.assign({ code: r.code, done: false, at }, i))); });
    return true;
  }
  function planAdd(code, day) {
    const id = newId(), at = Math.floor(Date.now() / 1000);
    change("plan-add", { id, code, day }, (m) => { m.plan = (m.plan || []).concat([{ id, code, day, at }]); });
  }
  function timerChips(r, s, l) {
    if (!s.timers || !s.timers.length) return "";
    const running = timer && timer.code === r.code && timer.end > Date.now();
    if (running) return `<div class="chips"><span class="chip">${I.clock}<span data-countdown>${esc(fmtClock(timer.end - Date.now()))}</span></span><button type="button" class="chip" data-action="timer-stop">${esc(l.stopRead)}</button></div>`;
    return `<div class="chips">${s.timers.map((m) => `<button type="button" class="chip" data-action="timer" data-min="${m}">${I.clock}${esc(l.timer(m))}</button>`).join("")}</div>`;
  }
  function nutritionHTML(r, l) {
    const n = r.nutrition || {};
    const c = [["calories", l.calories], ["protein", l.protein], ["carbs", l.carbs], ["fat", l.fat]].filter(([k]) => n[k]).map(([k, name]) => `<span class="chip">${esc(name)} ${esc(n[k])}</span>`);
    if (n.other) c.push(`<span class="chip">${esc(n.other)}</span>`);
    if (!c.length) return "";
    return `<section class="sec"><h2>${esc(l.nut)}${n.per ? ` <span class="sub">· ${esc(n.per)}</span>` : ""}</h2><div class="nut">${c.join("")}</div></section>`;
  }
  function mediaHTML(r, l, playing) {
    if (playing && r.video) return `<div class="media"><video src="${esc(r.video)}" controls playsinline autoplay preload="auto"${r.photo ? ` poster="${esc(r.photo)}"` : ""}></video></div>`;
    return `<div class="media">${r.photo ? `<img src="${esc(r.photo)}" alt="${esc(r.title)}">` : ""}${r.video ? `<button type="button" class="play" data-action="play">${I.play}${esc(l.watch)}</button>` : ""}</div>`;
  }
  function ratingHTML(code) {
    const cur = M().ratings[code] || 0;
    return `<div class="rating" role="group">${[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => `<button type="button" data-action="rate" data-n="${n}" aria-pressed="${n === cur}" class="${n <= cur ? "on" : ""}">${n}</button>`).join("")}</div>`;
  }
  const factorName = (f) => (FACTORS.find(([x]) => x === f) || [f, f + "×"])[1];
  function mineHTML(r, l) {
    const n = M().cooked_count[r.code], last = M().cooked_last[r.code];
    const log = (M().cooked || []).filter((e) => e.code === r.code).sort((a, b) => b.at - a.at);
    const prev = log.find((e) => e.factor && e.factor !== 1);
    return `<section class="sec mine"><h2>${esc(l.mine)}</h2>
      <div class="made"><button type="button" class="btn" data-action="made">${I.done}${esc(l.madeIt)}</button>${n ? `<span class="sub">${esc(l.made(n, day(last)))}</span>` : ""}</div>
      ${prev && r.steps && r.steps.length ? `<button type="button" class="btn" data-action="again" data-f="${prev.factor}">${I.cook}${esc(l.again2)} · ${esc(factorName(prev.factor))}</button>` : ""}
      ${log.some((e) => e.note || (e.factor && e.factor !== 1)) ? `<ul class="log">${log.filter((e) => e.note || (e.factor && e.factor !== 1)).slice(0, 8).map((e) =>
        `<li><span class="when">${esc(day(e.at, r.lang))}${e.factor && e.factor !== 1 ? " · " + esc(factorName(e.factor)) : ""}</span>${e.note ? `<span class="nt" dir="auto">${esc(e.note)}</span>` : ""}</li>`).join("")}</ul>` : ""}
      <h3>${esc(l.rating)}</h3>${ratingHTML(r.code)}
      <h3>${esc(l.notes)}</h3><textarea id="note" rows="3" data-code="${esc(r.code)}">${esc(M().notes[r.code] || "")}</textarea></section>`;
  }
  let playing = null;
  function recipePage(r) {
    const l = lab(r);
    const reading = speaking === "r:" + r.code;
    const steps = r.steps || [];
    const awake = store.get("awake", true);
    const saved = !!M().saved[r.code];
    const at = M().steps[r.code];
    const others = Object.keys(ME.names || {}).length > 1;
    return `<div class="wrap"${dirOf(r)}>
      <div class="bar"><a class="btn btn-icon" href="#/" aria-label="Back">${I.back}</a><span class="grow"></span>
        ${(r.langs || []).length > 1 ? `<button type="button" class="btn lang" data-action="lang" data-to="${r.lang === "he" ? "en" : "he"}" lang="${r.lang === "he" ? "en" : "he"}">${r.lang === "he" ? "English" : "עברית"}</button>` : ""}
        ${canSpeak && steps.length ? `<button type="button" class="btn" data-action="read" aria-pressed="${reading}">${reading ? I.stop + esc(l.stopRead) : I.speak + esc(l.read)}</button>` : ""}
        <button type="button" class="btn btn-icon save${saved ? " on" : ""}" data-action="save" aria-pressed="${saved}" aria-label="Save">${saved ? I.markOn : I.mark}</button>
        <button type="button" class="btn btn-icon" data-action="more" aria-label="${esc(l.more)}">${I.more}</button></div>
      <article class="recipe">
        <div class="pic-col">${mediaHTML(r, l, playing === r.code)}
          ${"wakeLock" in navigator ? `<button type="button" class="switch" role="switch" aria-checked="${awake}" data-action="awake"><span>${esc(l.awake)}</span><span class="track"><span class="knob"></span></span></button>` : ""}</div>
        <div class="body">
          <header class="head">
            <h1 tabindex="-1">${esc(r.title)}</h1>
            ${r.summary ? `<p class="sum">${esc(r.summary)}</p>` : ""}
            <div class="by" dir="ltr">${sourceLinks(r, l)}</div>
            <p class="dates">${[r.posted ? l.posted(day(r.posted, r.lang)) : "", r.found ? l.added(day(r.found, r.lang), others && r.added_by ? nameOf(r.added_by) : "") : "",
              r.edited && r.edited.at ? l.edited(day(r.edited.at, r.lang)) : ""].filter(Boolean).map(esc).join(" · ")}</p>
            ${factsHTML(r, l)}
            ${r.is_recipe !== false && steps.length ? `<div class="actions"><a class="btn btn-accent btn-big" href="#/cook/${esc(r.code)}/${at || 1}">${I.cook}${esc(at ? l.cont(at) : l.start)}</a></div>` : ""}
            ${r.is_recipe !== false ? `<div class="actions more"><button type="button" class="btn" data-action="plan">${I.cal}${esc(l.plan)}</button>${hasIngs(r) ? `<button type="button" class="btn" data-action="to-list">${I.cart}${esc(l.list)}</button>` : ""}</div>
            ${hasIngs(r) ? amountsHTML(r, l) : ""}` : ""}
          </header>
          ${r.is_recipe === false ? `<p class="empty">${esc(l.notRecipe)}</p>` : `
          <div class="two">
            ${r.ingredient_groups.length ? `<section class="sec"><h2>${esc(l.ing)}</h2><div id="ing-list">${ingredientsHTML(r, l)}</div></section>` : ""}
            ${steps.length ? `<section class="sec"><h2>${esc(l.steps)}</h2><ol class="steps">${steps.map((s, i) => `<li><div class="step"><span class="n">${i + 1}</span><div>${esc(UT(s.text, r.lang))}${timerChips(r, s, l)}</div></div></li>`).join("")}</ol></section>` : ""}
          </div>
          ${r.tips && r.tips.length ? `<section class="sec"><h2>${esc(l.tips)}</h2><ul class="list">${r.tips.map((t) => `<li>${esc(UT(t, r.lang))}</li>`).join("")}</ul></section>` : ""}
          ${nutritionHTML(r, l)}
          ${r.missing && r.missing.length ? `<section class="sec miss"><h2>${esc(missLabel(r))}</h2><ul class="list">${r.missing.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></section>` : ""}
          ${mineHTML(r, l)}
          ${askHTML(r, l)}`}
        </div>
      </article>
    </div>`;
  }

  /* ---------- cook mode ---------- */
  function stem(w) { return w.replace(/(es|s)$/i, ""); }
  const reEsc = (x) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  function usesOf(r, s) {
    // the ingredients a step names, with their amounts, so the amounts are there while cooking. A name
    // counts at the start of a word ("oil" isn't in "boil"); Hebrew words can carry a prefix (ה, ו, ב…).
    const text = norm(s.text);
    const pre = r.lang === "he" ? "[והבלמשכ]{0,2}" : "";
    const out = [];
    r.ingredient_groups.forEach((g) => g.items.forEach((i) => {
      if (!i.amount) return;
      const words = norm(i.item).split(" ").filter((w) => w.length > 2);
      if (!words.length) return;
      const key = stem(words[words.length - 1]);
      if (key.length > 2 && new RegExp("(^| )" + pre + reEsc(key), "u").test(text) && !out.some((o) => stem(norm(o.item).split(" ").pop()) === key)) out.push(i);
    }));
    return out.slice(0, 6);
  }
  function cookPage(r, n) {
    const l = lab(r);
    const steps = r.steps || [];
    if (n === "done") {
      return `<div class="cook"${dirOf(r)}>
        <div class="bar"><a class="btn" href="#/r/${esc(r.code)}">${esc(l.close)}</a><span class="name">${esc(r.title)}</span><span style="width:70px"></span></div>
        <div class="body cook-done"><h1 tabindex="-1">${esc(l.finished)}</h1>
          <div class="sec mine"><h3>${esc(l.rating)}</h3>${ratingHTML(r.code)}<h3>${esc(l.notes)}</h3><textarea id="note" rows="3" data-code="${esc(r.code)}">${esc(M().notes[r.code] || "")}</textarea></div>
          <div class="actions"><a class="btn btn-accent btn-big" href="#/r/${esc(r.code)}">${esc(l.toRecipe)}</a><a class="btn btn-big" href="#/cook/${esc(r.code)}/1">${esc(l.again)}</a></div></div>
      </div>`;
    }
    const k = Math.max(1, Math.min(steps.length, n || 1));
    const s = steps[k - 1];
    const uses = usesOf(r, s);
    const last = k === steps.length;
    return `<div class="cook"${dirOf(r)}>
      <div class="bar"><a class="btn" href="#/r/${esc(r.code)}">${esc(l.close)}</a><span class="name">${esc(r.title)}</span>
        <button type="button" class="btn btn-icon" data-action="sheet" aria-label="${esc(l.ing)}">${I.list}</button></div>
      <div class="progress" aria-hidden="true"><span style="width:${Math.round((k / steps.length) * 100)}%"></span></div>
      <div class="count">${esc(l.step(k, steps.length))}</div>
      <div class="body" aria-live="polite">
        <p class="said" tabindex="-1">${esc(UT(s.text, r.lang))}</p>
        <div class="side">
        ${uses.length ? `<div class="uses"><span class="lbl">${esc(l.uses)}</span><ul>${uses.map((i) => `<li><b>${esc(UA(Amt.scale(i.amount, factor(r.code)), r.lang))}</b> ${esc(i.item)}</li>`).join("")}</ul></div>` : ""}
        <div class="tools">${timerChips(r, s, l).replace(/class="chip"/g, 'class="btn"').replace('<div class="chips">', "").replace(/<\/div>$/, "")}
          ${canSpeak ? `<button type="button" class="btn" data-action="read-step" data-i="${k - 1}">${I.speak}${esc(l.read)}</button>` : ""}</div>
        </div>
      </div>
      <div class="nav">
        <a class="btn" href="${k === 1 ? `#/r/${esc(r.code)}` : `#/cook/${esc(r.code)}/${k - 1}`}">${esc(l.backStep)}</a>
        ${last ? `<button type="button" class="btn btn-accent" data-action="finish">${esc(l.done)}</button>` : `<a class="btn btn-accent" href="#/cook/${esc(r.code)}/${k + 1}">${esc(l.next)}</a>`}
      </div>
    </div>`;
  }
  function openSheet(r) {
    const l = lab(r);
    const el = document.createElement("div");
    el.className = "sheet";
    el.innerHTML = `<div class="panel"${dirOf(r)} role="dialog" aria-modal="true" aria-label="${esc(l.ing)}"><div class="grip"></div>
      <div class="bar"><h2>${esc(l.ing)}</h2><button type="button" class="btn" data-close>${esc(l.close)}</button></div>${ingredientsHTML(r, l)}</div>`;
    const close = () => { el.remove(); document.removeEventListener("keydown", onKey); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    el.addEventListener("click", (e) => { if (e.target === el || e.target.closest("[data-close]")) close(); });
    document.addEventListener("keydown", onKey);
    document.body.appendChild(el);
    el.querySelector("[data-close]").focus();
  }

  /* ---------- history ---------- */
  function rowHTML(r, right) {
    return `<li><a class="hrow" href="#/r/${esc(r.code)}"><span class="pic">${r.photo ? `<img src="${esc(r.photo)}" alt="" loading="lazy">` : ""}</span>
      <span class="t"${dirOf(shown(r))}>${esc(shown(r).title)}</span>${right || ""}</a></li>`;
  }
  let calOff = 0;
  function calendarHTML(cooked) {
    const t = today0(), first = new Date(t.getFullYear(), t.getMonth() + calOff, 1), start = weekStart(first);
    const byDay = {};
    cooked.forEach((e) => { const k = iso(new Date(e.at * 1000)); (byDay[k] = byDay[k] || []).push(e); });
    let cells = Array.from({ length: 42 }, (_, i) => addDays(start, i));
    if (cells.slice(35).every((d) => d.getMonth() !== first.getMonth())) cells = cells.slice(0, 35);
    const dow = Array.from({ length: 7 }, (_, i) => addDays(start, i).toLocaleDateString(undefined, { weekday: "narrow" }));
    return `<div class="cal"><div class="calhead"><button type="button" class="btn btn-icon" data-action="cal" data-d="-1" aria-label="Earlier">${I.back}</button>
        <b>${esc(first.toLocaleDateString(undefined, { month: "long", year: "numeric" }))}</b>
        <button type="button" class="btn btn-icon" data-action="cal" data-d="1" aria-label="Later"${calOff >= 0 ? " disabled" : ""}>${I.fwd}</button></div>
      <div class="calgrid">${dow.map((d) => `<span class="dow">${esc(d)}</span>`).join("")}${cells.map((d) => {
        const k = iso(d), rs = (byDay[k] || []).map((e) => byCode(e.code)).filter(Boolean);
        return `<div class="cday${d.getMonth() !== first.getMonth() ? " out" : ""}${k === iso(t) ? " today" : ""}"><span class="dn">${d.getDate()}</span>
          ${rs.slice(0, 2).map((r) => `<a class="cpic" href="#/r/${esc(r.code)}" aria-label="${esc(shown(r).title)}">${r.photo ? `<img src="${esc(r.photo)}" alt="" loading="lazy">` : ""}</a>`).join("")}${rs.length > 2 ? `<span class="more">+${rs.length - 2}</span>` : ""}</div>`;
      }).join("")}</div></div>`;
  }
  async function historyPage(tab) {
    const h = await getJSON("api/history");
    tab = tab || "cooked";
    const tabs = [["cooked", "Cooked"], ["viewed", "Viewed"], ["imported", "Imported"]];
    let body = "";
    if (tab === "cooked") {
      const rows = h.cooked.map((e) => [e, byCode(e.code)]).filter(([, r]) => r);
      body = calendarHTML(h.cooked) + (rows.length ? `<ul class="hlist log">${rows.map(([e, r]) => `<li><a class="hrow" href="#/r/${esc(r.code)}"><span class="pic">${r.photo ? `<img src="${esc(r.photo)}" alt="" loading="lazy">` : ""}</span>
          <span class="t"><span${dirOf(shown(r))}>${esc(shown(r).title)}</span>${e.note ? `<span class="nt" dir="auto">${esc(e.note)}</span>` : ""}</span>
          <span class="when">${esc(day(e.at))}${e.factor && e.factor !== 1 ? " · " + esc(factorName(e.factor)) : ""}</span></a>
        <button type="button" class="btn btn-icon del" data-action="cook-note" data-id="${esc(e.id)}" aria-label="Note">${I.edit}</button>
        <button type="button" class="btn btn-icon del" data-action="uncook" data-id="${esc(e.id)}" aria-label="Remove">${I.trash}</button></li>`).join("")}</ul>` : `<p class="empty">Nothing yet</p>`);
    } else if (tab === "viewed") {
      const rows = h.viewed.map(([c, t]) => [byCode(c), t]).filter(([r]) => r);
      body = rows.length ? `<ul class="hlist">${rows.map(([r, t]) => rowHTML(r, `<span class="when">${esc(dayTime(t))}</span>`)).join("")}</ul>` : `<p class="empty">Nothing yet</p>`;
    } else {
      body = h.runs.length ? h.runs.map((run) => {
        const made = (run.made || []).map((m) => byCode(m.code)).filter(Boolean);
        const by = run.kind === "add" ? nameOf(run.by) : [...new Set((run.found || []).map((f) => nameOf(f.by)))].join(", ");
        return `<section class="run"><h3>${esc(dayTime(run.at))}${by ? ` <span class="sub">· ${esc(by)}</span>` : ""}</h3>
          ${made.length ? `<ul class="hlist">${made.map((r) => rowHTML(r)).join("")}</ul>` : ""}
          ${(run.failed || []).map((f) => `<p class="fail">${esc((byCode(f.code) || {}).title || f.code)} · ${esc(f.error.split(":")[0])}</p>`).join("")}
          ${(run.signed_out || []).map((a) => `<p class="fail">Instagram sign-in lapsed · ${esc(nameOf(a))}</p>`).join("")}</section>`;
      }).join("") : `<p class="empty">Nothing yet</p>`;
    }
    return `<div class="wrap narrow">${topBar("History")}
      <nav class="tabs">${tabs.map(([k, n]) => `<a href="#/history/${k}" aria-current="${k === tab ? "page" : "false"}">${n}</a>`).join("")}</nav>${body}</div>`;
  }

  /* ---------- the week: this week and next, from Sunday ---------- */
  const withLine = () => { const h = M().household || []; return h.length ? `<span class="with">With ${esc(h.map(nameOf).join(", "))}</span>` : ""; };
  function weekPage() {
    return `<div class="wrap">${topBar("Week")}<div class="pagebar">${withLine()}<span class="grow"></span><button type="button" class="btn" data-action="print">${I.print}Print</button></div>
      <div id="live">${weekBody()}</div></div>`;
  }
  function weekBody() {
    const t = today0(), ti = iso(t), start = weekStart(t), end = iso(addDays(start, 7));
    const plan = {};
    (M().plan || []).forEach((p) => { (plan[p.day] = plan[p.day] || []).push(p); });
    const coming = (M().plan || []).some((p) => p.day >= ti && p.day < end && byCode(p.code));
    const week = (w) => `<section class="sec wk"><div class="wkhead"><h2>${w ? "Next week" : "This week"}</h2>
        ${!w && coming ? `<button type="button" class="btn" data-action="week-list">${I.cart}Add to list</button>` : ""}</div>
      ${[0, 1, 2, 3, 4, 5, 6].map((i) => {
        const d = addDays(start, w * 7 + i), k = iso(d);
        const rows = (plan[k] || []).map((p) => [p, byCode(p.code)]).filter(([, r]) => r);
        return `<div class="day${k < ti ? " past" : ""}${k === ti ? " today" : ""}" data-day="${k}"><div class="dayhead"><b>${esc(dayName(d))}</b><span class="sub">${esc(shortDate(d))}</span>
            <button type="button" class="btn btn-icon add" data-action="plan-pick" data-day="${k}" aria-label="Add">${I.plus}</button></div>
          ${rows.length ? `<ul class="hlist">${rows.map(([p, r]) => `<li><span class="grip" data-drag="${esc(p.id)}" aria-hidden="true">${I.grip}</span><a class="hrow" href="#/r/${esc(r.code)}"><span class="pic">${r.photo ? `<img src="${esc(r.photo)}" alt="" loading="lazy">` : ""}</span>
            <span class="t"${dirOf(shown(r))}>${esc(shown(r).title)}</span></a>
            <button type="button" class="btn btn-icon del" data-action="plan-move" data-id="${esc(p.id)}" aria-label="Move">${I.cal}</button>
            <button type="button" class="btn btn-icon del" data-action="plan-remove" data-id="${esc(p.id)}" aria-label="Remove">${I.x}</button></li>`).join("")}</ul>` : ""}</div>`;
      }).join("")}</section>`;
    return `<div class="weeks">${week(0)}${week(1)}</div>`;
  }
  function pickRecipe(day) {
    const saved = M().saved;
    const all = recipesOnly().slice().sort((a, b) => (saved[b.code] ? 1 : 0) - (saved[a.code] ? 1 : 0) || (b.found || 0) - (a.found || 0));
    const rows = (q) => {
      const words = norm(q).split(" ").filter(Boolean);
      const list = all.filter((r) => matches(r, words));
      return list.length ? list.map((r) => `<li><button type="button" class="hrow" data-pick="${esc(r.code)}"><span class="pic">${r.photo ? `<img src="${esc(r.photo)}" alt="" loading="lazy">` : ""}</span>
        <span class="t"${dirOf(shown(r))}>${esc(shown(r).title)}</span></button></li>`).join("") : `<li class="empty">No recipes</li>`;
    };
    const d = fromIso(day);
    const el = sheet(`${dayName(d)} · ${shortDate(d)}`, `<div class="pickq"><div class="search">${I.search}<input type="search" placeholder="Search" aria-label="Search" autocomplete="off" enterkeyhint="search"></div></div>
      <ul class="hlist picks">${rows("")}</ul>`, (e, close) => { const b = e.target.closest("[data-pick]"); if (b) { close(); planAdd(b.dataset.pick, day); } });
    el.querySelector("input").addEventListener("input", (e) => { el.querySelector(".picks").innerHTML = rows(e.target.value); });
  }
  async function weekToList() {
    const ti = iso(today0()), end = iso(addDays(weekStart(today0()), 7));
    const coming = (M().plan || []).filter((p) => p.day >= ti && p.day < end && byCode(p.code));
    let n = 0;
    for (const p of coming) {
      try { if (addToList(await loadOne(p.code))) n++; } catch (e) { if (e instanceof SignedOut) return signInPage(); }
    }
    if (n) toast("On the list", "#/list");
  }

  /* ---------- the shopping list ---------- */
  function listPage() {
    return `<div class="wrap narrow">${topBar("List")}
      <form data-form="shop-add" class="addrow"><input name="item" type="text" placeholder="Add" aria-label="Add" autocomplete="off" autocapitalize="sentences" enterkeyhint="done" dir="auto" maxlength="200">
        <button class="btn btn-icon" type="submit" aria-label="Add">${I.plus}</button></form>
      <div id="live">${listBody()}</div></div>`;
  }
  const shopLines = () => Amt.merge(M().shop || []);
  const aisleOf = (x) => (M().aisles || {})[x.key] || (window.MatkonAisles ? MatkonAisles.of(x.item) : "other");
  function lineHTML(x) {
    const from = x.codes.map(byCode).filter(Boolean).map((r) => shown(r).title);
    const ids = esc(x.ids.join(","));
    const amount = x.amount ? UA(x.amount, heText(x.amount + x.item) ? "he" : "en") : "";
    return `<li class="line"><button type="button" class="ing${x.done ? " done" : ""}" data-action="shop-tick" data-ids="${ids}" aria-pressed="${x.done}">
        <span class="box">${I.check}</span><span class="txt"><span class="it" dir="auto">${amount ? `<span class="amt">${esc(amount)}</span> ` : ""}${esc(x.item)}</span>
        ${from.length ? `<span class="from" dir="auto">${esc(from.join(" · "))}</span>` : ""}</span></button>
      ${x.done ? "" : `<button type="button" class="btn btn-icon del" data-action="aisle" data-key="${esc(x.key)}" data-item="${esc(x.item)}" aria-label="Aisle">${I.tag}</button>`}
      <button type="button" class="btn btn-icon del" data-action="shop-remove" data-ids="${ids}" aria-label="Remove">${I.x}</button></li>`;
  }
  function listBody() {
    const lines = shopLines();
    if (!lines.length) return `<p class="empty">Nothing on the list</p>`;
    const open = lines.filter((x) => !x.done), done = lines.filter((x) => x.done);
    const groups = {};
    open.forEach((x) => { const a = aisleOf(x); (groups[a] = groups[a] || []).push(x); });
    const order = window.MatkonAisles ? MatkonAisles.ORDER : ["other"];
    const names = window.MatkonAisles ? MatkonAisles.NAMES : { other: "" };
    return `<div class="listbar">${withLine()}${open.length ? `<button type="button" class="btn" data-action="shop-share">${I.share}${navigator.share ? "Share" : "Copy"}</button>` : ""}
        <button type="button" class="btn" data-action="print">${I.print}Print</button>
        <button type="button" class="btn" data-action="shop-clear-done"${done.length ? "" : " disabled"}>Clear done</button>
        <button type="button" class="btn" data-action="shop-clear-all">Clear all</button></div>
      ${order.filter((a) => groups[a]).map((a) => `<section class="sec shop"><h3 class="aisle">${esc(names[a] || a)}</h3><ul class="ings">${groups[a].map(lineHTML).join("")}</ul></section>`).join("")}
      ${done.length ? `<section class="sec shop"><h2>Done</h2><ul class="ings">${done.map(lineHTML).join("")}</ul></section>` : ""}`;
  }
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); }
    catch (e) {                                        // no clipboard over plain http: the old way
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); } catch (e2) { /* nothing more to try */ }
      ta.remove();
    }
  }
  async function shareList() {
    const text = shopLines().filter((x) => !x.done).map((x) => "• " + (x.amount ? UA(x.amount, heText(x.amount + x.item) ? "he" : "en") + " " : "") + x.item).join("\n");
    if (navigator.share) { try { await navigator.share({ text }); } catch (e) { /* closed */ } return; }
    await copyText(text);
    toast("Copied");
  }
  function aisleSheet(key, item) {
    const names = MatkonAisles.NAMES, cur = (M().aisles || {})[key] || MatkonAisles.of(item);
    sheet(item, `<ul class="days">${MatkonAisles.ORDER.map((a) => `<li><button type="button" class="dayrow" data-aisle="${a}" aria-pressed="${a === cur}"><span>${esc(names[a])}</span><span class="tick${a === cur ? " on" : ""}">${I.check}</span></button></li>`).join("")}</ul>`,
      (e, close) => {
        const b = e.target.closest("[data-aisle]");
        if (!b) return;
        close();
        const aisle = b.dataset.aisle === MatkonAisles.of(item) ? "" : b.dataset.aisle;
        change("aisle", { key, aisle }, (m) => { m.aisles = m.aisles || {}; if (aisle) m.aisles[key] = aisle; else delete m.aisles[key]; });
      });
  }
  // what's on the page now, redrawn after a change here or on another device
  function paint() {
    const el = document.getElementById("live");
    if (!el || !ME) return;
    const page = route()[0];
    if (page === "week") el.innerHTML = weekBody();
    else if (page === "list") el.innerHTML = listBody();
    else if (page === "pantry") el.innerHTML = pantryBody();
  }

  /* ---------- What can I make? (what's in the kitchen, kept for the account) ---------- */
  const STAPLE = new Set(["salt", "pepper", "black pepper", "salt and pepper", "water", "oil", "olive oil", "vegetable oil", "sugar", "ice",
    "מלח", "פלפל שחור", "מים", "שמן", "שמן זית", "סוכר"].map(norm));
  const pantry = () => M().pantry || [];
  function needsOf(r) {                               // the main things a recipe needs, not salt and spices
    const useEn = english() && r.lang !== "en" && r.items_en && r.items_en.length;
    const list = useEn ? r.items_en : r.main_ingredients && r.main_ingredients.length ? r.main_ingredients : r.items || [];
    const out = [...new Set(list.map((x) => String(x || "").trim()).filter(Boolean))]
      .filter((x) => !STAPLE.has(norm(x)) && !(window.MatkonAisles && MatkonAisles.of(x) === "spices"));
    return useEn ? out.slice(0, 8) : out;
  }
  function haveIt(x, have) {
    const kx = " " + Amt.key(x) + " ";
    return have.some((p) => { const kp = Amt.key(p); return kp && (kx.includes(" " + kp + " ") || (" " + kp + " ").includes(kx)); });
  }
  function pantryPage() {
    return `<div class="wrap">${topBar()}<h1 class="pagetitle" tabindex="-1">What can I make?</h1>
      <form data-form="pantry-add" class="addrow"><input name="item" type="text" placeholder="Add" aria-label="Add" autocomplete="off" autocapitalize="none" enterkeyhint="done" dir="auto" maxlength="60">
        <button class="btn btn-icon" type="submit" aria-label="Add">${I.plus}</button></form>
      <div id="live">${pantryBody()}</div></div>`;
  }
  function pantryBody() {
    const have = pantry();
    const common = new Map();
    recipesOnly().forEach((r) => needsOf(r).forEach((x) => { const k = Amt.key(x); const c = common.get(k) || { n: 0, name: x }; c.n++; common.set(k, c); }));
    const offer = [...common.values()].sort((a, b) => b.n - a.n).map((c) => c.name).filter((x) => !haveIt(x, have)).slice(0, 20);
    const ranked = recipesOnly().map((r) => { const need = needsOf(r); const got = need.filter((x) => haveIt(x, have)); return { r, got, miss: need.filter((x) => !haveIt(x, have)) }; })
      .filter((x) => x.got.length).sort((a, b) => a.miss.length - b.miss.length || b.got.length - a.got.length).slice(0, 40);
    return `<section class="sec pantry">
        ${have.length ? `<h3>In the kitchen</h3><div class="chips">${have.map((x) => `<button type="button" class="have" data-action="pantry-del" data-p="${esc(x)}" dir="auto">${esc(x)}${I.x}</button>`).join("")}</div>` : ""}
        ${offer.length ? `<h3>From your recipes</h3><div class="chips">${offer.map((x) => `<button type="button" data-action="pantry-add" data-p="${esc(x)}" dir="auto">${I.plus}${esc(x)}</button>`).join("")}</div>` : ""}</section>
      ${have.length ? (ranked.length ? `<section class="sec"><h2>You can make</h2><ul class="hlist can">${ranked.map(({ r, miss }) => `<li><a class="hrow" href="#/r/${esc(r.code)}"><span class="pic">${r.photo ? `<img src="${esc(r.photo)}" alt="" loading="lazy">` : ""}</span>
          <span class="t"><span${dirOf(shown(r))}>${esc(shown(r).title)}</span><span class="nt" dir="auto">${miss.length ? "Missing: " + esc(miss.slice(0, 6).join(", ")) + (miss.length > 6 ? "…" : "") : "Everything"}</span></span></a></li>`).join("")}</ul></section>`
        : `<p class="empty">Nothing yet</p>`) : ""}`;
  }
  function pantrySet(items) { change("pantry", { items }, (m) => { m.pantry = items; }); }

  /* ---------- Add: a reel, a recipe page, or photos of a recipe ---------- */
  let addResult = null;
  function addPage() {
    const d = addResult;
    const r = d && d.code ? byCode(d.code) : null;
    return `<div class="wrap narrow">${topBar("Add")}
      <section class="sec set"><h2>Link</h2>
        <form data-form="add-link" class="row">${field("url", "Reel or recipe page", "", "url", 'required inputmode="url" autocomplete="off"')}<button class="btn btn-accent" type="submit">Add</button></form></section>
      <section class="sec set"><h2>Photos</h2>
        <label class="btn btn-big filebtn">${I.camera}Choose photos<input type="file" accept="image/*" multiple hidden data-photos></label></section>
      ${d ? `<section class="shared"><h2>${esc(d.error ? d.error : r && d.done ? "Already in Matkon" : d.new === false ? "Already on the way" : "Added")}</h2>${r && d.done ? `<ul class="hlist">${rowHTML(r)}</ul>` : ""}</section>` : ""}
      <p class="msg" id="msg" role="status"></p></div>`;
  }
  const isInsta = (u) => /(^|\.)(instagram\.com|instagr\.am)\//i.test(u.replace(/^https?:\/\//i, ""));
  async function addLink(text) {
    const url = (String(text).match(/https?:\/\/\S+/) || [String(text).trim()])[0];
    if (isInsta(url) || /instagram\.com|instagr\.am/i.test(text)) return post("api/settings", { op: "add-reel", url: text });
    return post("api/add-link", { url: /^https?:\/\//i.test(url) ? url : "https://" + url });
  }
  async function shrink(file) {                        // a phone photo, down to 2000 px and a JPEG, before it goes up
    const img = await createImageBitmap(file);
    const k = Math.min(1, 2000 / Math.max(img.width, img.height));
    const c = document.createElement("canvas");
    c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    return c.toDataURL("image/jpeg", 0.85);
  }
  async function addPhotos(files) {
    files = [...files].filter((f) => /^image\//.test(f.type)).slice(0, 4);
    if (!files.length) return;
    say("Sending…");
    try {
      const images = [];
      for (const f of files) images.push(await shrink(f));
      addResult = await post("api/add-photo", { images });
      LIST = await getJSON("api/recipes");
    } catch (e) {
      if (e instanceof SignedOut) return signInPage();
      addResult = { error: e.message };
    }
    render(true);
  }

  /* ---------- fixing a recipe (in the language it's shown in) ---------- */
  const edIng = (l, i) => `<div class="ei"><input name="amount" value="${esc(i.amount || "")}" placeholder="${esc(l.amount)}" aria-label="${esc(l.amount)}" dir="auto">
    <input name="item" value="${esc(i.item || "")}" placeholder="${esc(l.item)}" aria-label="${esc(l.item)}" dir="auto">
    <input name="note" value="${esc(i.note || "")}" placeholder="${esc(l.note)}" aria-label="${esc(l.note)}" dir="auto">
    <button type="button" class="btn btn-icon" data-action="ed-del" aria-label="Remove">${I.x}</button></div>`;
  const edGroup = (l, g) => `<div class="eg"><div class="eghead"><input name="gname" value="${esc(g.name || "")}" placeholder="${esc(l.group)}" aria-label="${esc(l.group)}" dir="auto">
    <button type="button" class="btn btn-icon" data-action="ed-del-group" aria-label="Remove">${I.trash}</button></div>
    <div class="eis">${(g.items && g.items.length ? g.items : [{}]).map((i) => edIng(l, i)).join("")}</div>
    <button type="button" class="btn" data-action="ed-add-ing">${I.plus}${esc(l.addIng)}</button></div>`;
  const edStep = (l, st, i) => `<div class="es"><span class="n">${i + 1}</span><textarea name="step" rows="3" dir="auto" aria-label="${i + 1}"
    data-timers="${esc((st.timers || []).join(","))}" data-orig="${esc(st.text || "")}">${esc(st.text || "")}</textarea>
    <button type="button" class="btn btn-icon" data-action="ed-del" aria-label="Remove">${I.x}</button></div>`;
  function editPage(r) {
    const l = lab(r);
    const box = (name, label, value) => `<label class="field"><span>${esc(label)}</span><input name="${name}" value="${esc(value || "")}" dir="auto" maxlength="120"></label>`;
    return `<div class="wrap narrow"${dirOf(r)}>
      <div class="bar"><a class="btn" href="#/r/${esc(r.code)}">${esc(l.cancel)}</a><span class="grow"></span>
        ${r.edited ? `<button type="button" class="btn" data-action="ed-revert">${esc(l.revert)}</button>` : ""}
        <button type="button" class="btn btn-accent" data-action="ed-save">${esc(l.save)}</button></div>
      <form class="editor" data-form="edit" id="editor">
        <label class="field"><span>${esc(l.title)}</span><input name="title" value="${esc(r.title)}" dir="auto" required maxlength="200"></label>
        <label class="field"><span>${esc(l.summary)}</span><textarea name="summary" rows="2" dir="auto">${esc(r.summary || "")}</textarea></label>
        <div class="edfacts">${box("servings", l.servings, r.servings)}${box("prep", l.prep, r.time && r.time.prep)}${box("cook", l.cook, r.time && r.time.cook)}${box("total", l.total, r.time && r.time.total)}${box("oven", l.oven, r.oven)}</div>
        <h2>${esc(l.ing)}</h2><div id="ed-groups">${(r.ingredient_groups.length ? r.ingredient_groups : [{ name: "", items: [] }]).map((g) => edGroup(l, g)).join("")}</div>
        <button type="button" class="btn" data-action="ed-add-group">${I.plus}${esc(l.addGroup)}</button>
        <h2>${esc(l.steps)}</h2><div id="ed-steps">${(r.steps.length ? r.steps : [{}]).map((st, i) => edStep(l, st, i)).join("")}</div>
        <button type="button" class="btn" data-action="ed-add-step">${I.plus}${esc(l.addStep)}</button>
        <h2>${esc(l.tips)}</h2><textarea name="tips" rows="4" dir="auto">${esc((r.tips || []).join("\n"))}</textarea>
        <h2>${esc(missLabel(r))}</h2><textarea name="missing" rows="3" dir="auto">${esc((r.missing || []).join("\n"))}</textarea>
      </form></div>`;
  }
  function timersIn(text) {                           // "bake 20 to 25 minutes" → [20, 25], the same as Matkon's own reading
    const out = [];
    const re = /(\d+(?:[.,]\d+)?)(?:\s*(?:-|–|to|עד|או)\s*(\d+(?:[.,]\d+)?))?\s*(minutes?|mins?|דקות|דק׳|דקה|hours?|hrs?|שעות)/giu;
    for (const m of String(text).matchAll(re)) {
      const h = /^(h|שע)/i.test(m[3]) ? 60 : 1;
      [m[1], m[2]].filter(Boolean).forEach((x) => { const v = Math.round(parseFloat(x.replace(",", ".")) * h); if (v > 0 && v <= 1440 && !out.includes(v)) out.push(v); });
    }
    return out.slice(0, 3);
  }
  function renumber() { document.querySelectorAll("#ed-steps .es .n").forEach((n, i) => { n.textContent = i + 1; }); }
  async function saveEdit(r, revert) {
    const f = document.getElementById("editor");
    let body;
    if (revert) {
      if (!confirm(lab(r).revert + "?")) return;
      body = { lang: r.lang, revert: true };
    } else {
      const val = (n) => (f.elements[n] ? f.elements[n].value.trim() : "");
      const lines = (n) => val(n).split("\n").map((x) => x.trim()).filter(Boolean);
      const groups = [...f.querySelectorAll(".eg")].map((g) => ({ name: g.querySelector("[name=gname]").value.trim(),
        items: [...g.querySelectorAll(".ei")].map((e) => ({ amount: e.querySelector("[name=amount]").value.trim(), item: e.querySelector("[name=item]").value.trim(), note: e.querySelector("[name=note]").value.trim() })).filter((i) => i.item) }))
        .filter((g) => g.items.length);
      const steps = [...f.querySelectorAll("[name=step]")].map((t) => { const text = t.value.trim();
        return { text, timers: text === t.dataset.orig ? (t.dataset.timers ? t.dataset.timers.split(",").map(Number).filter(Boolean) : []) : timersIn(text) }; }).filter((x) => x.text);
      if (!val("title")) { f.elements.title.focus(); return; }
      body = { lang: r.lang, recipe: { title: val("title"), summary: val("summary"), servings: val("servings"),
        time: { prep: val("prep"), cook: val("cook"), total: val("total") }, oven: val("oven"), ingredient_groups: groups, steps, tips: lines("tips"), missing: lines("missing") } };
    }
    try {
      const d = await post("api/r/" + encodeURIComponent(r.code) + "/edit", body);
      Object.keys(FULL).forEach((k) => { if (k.startsWith(r.code + "|")) delete FULL[k]; });
      FULL[key(r.code)] = d;
      LIST = await getJSON("api/recipes");
      location.hash = "#/r/" + encodeURIComponent(r.code);
    } catch (e) { if (e instanceof SignedOut) signInPage(); else toast(e.message); }
  }

  /* ---------- the recipe's More: collections, a link to share, print, fixing it ---------- */
  function moreSheet(r) {
    const l = lab(r);
    const items = [["coll", I.folder, l.collections], ["share-link", I.link, l.share], ["print", I.print, l.print]].concat(r.can_edit ? [["edit", I.edit, l.edit]] : []);
    sheet(l.more, `<ul class="days more"${dirOf(r)}>${items.map(([a, i, n]) => `<li><button type="button" class="dayrow" data-more="${a}"><span class="mi">${i}${esc(n)}</span></button></li>`).join("")}</ul>`, (e, close) => {
      const b = e.target.closest("[data-more]");
      if (!b) return;
      close();
      const a = b.dataset.more;
      if (a === "coll") collSheet(r.code);
      else if (a === "share-link") shareSheet(r);
      else if (a === "print") setTimeout(() => window.print(), 80);
      else if (a === "edit") location.hash = "#/edit/" + encodeURIComponent(r.code);
    });
  }
  function shareSheet(r) {
    let url = r.share || null;
    const body = () => (url ? `<div class="sharebox"><input class="conn" type="text" readonly value="${esc(url)}" aria-label="Link">
        <div class="row">${navigator.share ? `<button type="button" class="btn btn-accent" data-sh="send">${I.share}Share</button>` : ""}<button type="button" class="btn" data-sh="copy">Copy</button>
        <button type="button" class="btn" data-sh="stop">Stop sharing</button></div></div>`
      : `<div class="sharebox"><button type="button" class="btn btn-accent btn-big" data-sh="make">${I.link}Make a link</button></div>`);
    const el = sheet(lab(r).share, `<div class="shbody">${body()}</div>`, async (e) => {
      const b = e.target.closest("[data-sh]");
      if (!b) return;
      const a = b.dataset.sh;
      try {
        if (a === "make") url = (await post("api/settings", { op: "share", code: r.code })).url;
        else if (a === "stop") { await post("api/settings", { op: "unshare", code: r.code }); url = null; }
        else if (a === "copy") { await copyText(url); toast("Copied"); return; }
        else if (a === "send") { try { await navigator.share({ title: r.title, url }); } catch (x) { /* closed */ } return; }
      } catch (err) { if (err instanceof SignedOut) return signInPage(); toast(err.message); return; }
      Object.keys(FULL).forEach((k) => { if (k.startsWith(r.code + "|")) FULL[k].share = url; });
      el.querySelector(".shbody").innerHTML = body();
    });
  }
  function madeSheet(r) {                             // "I made it": the amounts used and a note, for the cooking log
    const l = lab(r), f = factor(r.code);
    sheet(l.madeIt, `<form data-form="made" class="stack madeform"${dirOf(r)} data-code="${esc(r.code)}">
        ${hasIngs(r) ? `<div class="amounts"><span class="lbl">${esc(l.amounts)}</span><div class="chips" dir="ltr">${FACTORS.map(([x, n]) => `<button type="button" data-mf="${x}" aria-pressed="${x === f}">${n}</button>`).join("")}</div></div>` : ""}
        <label class="field"><span>${esc(l.noteLbl)}</span><textarea name="note" rows="3" maxlength="500" dir="auto"></textarea></label>
        <button class="btn btn-accent btn-big" type="submit">${I.done}${esc(l.madeIt)}</button></form>`,
    (e) => { const b = e.target.closest("[data-mf]"); if (b) b.parentNode.querySelectorAll("[data-mf]").forEach((x) => x.setAttribute("aria-pressed", x === b)); });
  }
  function noteSheet(entry) {
    const el = sheet("Note", `<form class="stack madeform" data-sheet="cook-note"><label class="field"><span>Note</span><textarea name="note" rows="3" maxlength="500" dir="auto">${esc(entry.note || "")}</textarea></label>
      <button class="btn btn-accent" type="submit">Save</button></form>`, () => {});
    el.addEventListener("submit", async (e) => {
      e.preventDefault(); e.stopPropagation();
      await remember("cook-note", { id: entry.id, note: e.target.elements.note.value.trim() });
      el.remove(); render(true);
    });
    const t = el.querySelector("textarea"); if (t) t.focus();
  }

  /* ---------- Ask about this recipe (Claude, with the recipe in front of it) ---------- */
  const asks = {};
  function askHTML(r, l) {
    const t = asks[r.code] || [];
    return `<section class="sec ask"><h2>${esc(l.ask)}</h2><div class="thread">${t.map((x) => `<p class="q" dir="auto">${esc(x.q)}</p><p class="a${x.a == null ? " wait" : x.bad ? " bad" : ""}" dir="auto">${esc(x.a == null ? l.asking : x.a)}</p>`).join("")}</div>
      <form data-form="ask" class="addrow"><input name="q" type="text" placeholder="${esc(l.askPh)}" aria-label="${esc(l.ask)}" autocomplete="off" dir="auto" maxlength="1000" enterkeyhint="send">
        <button class="btn btn-icon" type="submit" aria-label="${esc(l.ask)}">${I.send}</button></form></section>`;
  }
  function paintAsk(r) { const s = document.querySelector("section.ask"); if (s && r) s.outerHTML = askHTML(r, lab(r)); }
  async function ask(r, q) {
    const t = (asks[r.code] = asks[r.code] || []);
    const history = t.filter((x) => x.a && !x.bad).slice(-6).map((x) => ({ q: x.q, a: x.a }));
    const item = { q, a: null };
    t.push(item);
    paintAsk(r);
    try { item.a = (await post("api/ask", { code: r.code, lang: r.lang, question: q, history })).answer; }
    catch (e) { if (e instanceof SignedOut) return signInPage(); item.a = e.message; item.bad = true; }
    if (cur(r.code) === r) paintAsk(r);
  }

  /* ---------- settings ---------- */
  function field(name, label, value, type, extra) {
    return `<label class="field"><span>${esc(label)}</span><input name="${name}" type="${type || "text"}" value="${esc(value == null ? "" : value)}" ${extra || ""}></label>`;
  }
  async function settingsPage() {
    const s = await getJSON("api/settings");
    const ig = s.instagram;
    const br = ig.browser, si = ig.signin;
    const said = { "signed-out": "Instagram sign-in needed", busy: "Instagram asked for a break", instagram: "Instagram didn't answer" };
    const status = [si ? (si.error && said[si.error] ? said[si.error] : si.checked ? "Checked " + dayTime(si.checked) : "Waiting for the first check")
      : !br ? "No browser connected" : !br.seen ? "Waiting for the browser" : br.error && said[br.error] ? said[br.error] : br.checked ? "Checked " + dayTime(br.checked) : "Browser connected",
      ig.paused ? "Paused" : "", ig.collection_id ? ig.collection_name || "Collection " + ig.collection_id : ""].filter(Boolean).join(" · ");
    const k = s.kitchen;
    return `<div class="wrap narrow">${topBar("Settings")}
      ${s.initial_password ? `<button type="button" class="note-bar" data-action="to-password">Change your first password</button>` : ""}
      <section class="sec set"><h2>Account</h2>
        <form data-form="name" class="row">${field("name", "Name", s.account.name)}<button class="btn" type="submit">Save</button></form>
        <p class="sub">Username · ${esc(s.account.id)}</p>
        <form data-form="email" class="stack"><div class="row">${field("email", "Email", emailPending || s.account.email || "", "email", 'autocomplete="email"')}<button class="btn" type="submit">${emailPending ? "Send again" : "Save"}</button></div>
          ${emailPending ? `<div class="row">${field("code", "Code from the email", "", "text", 'inputmode="numeric" autocomplete="one-time-code"')}<button class="btn btn-accent" type="button" data-action="email-set">Confirm</button></div>` : ""}</form>
        <form data-form="password" id="password" class="stack"><h3>Password</h3>${field("old", "Current password", "", "password", 'autocomplete="current-password"')}${field("new", "New password", "", "password", 'autocomplete="new-password" minlength="8"')}<button class="btn" type="submit">Change password</button></form>
        <button type="button" class="btn" data-action="signout">Sign out</button></section>
      <section class="sec set"><h2>Display</h2>
        <button type="button" class="switch" role="switch" aria-checked="${s.settings.nutrition}" data-action="nutrition"><span>Calories and protein</span><span class="track"><span class="knob"></span></span></button>
        <button type="button" class="switch" role="switch" aria-checked="${!!s.settings.english}" data-action="english"><span>Hebrew recipes in English</span><span class="track"><span class="knob"></span></span></button>
        <h3>Units</h3><div class="chips units">${[["", "As written"], ["metric", "Metric"], ["us", "US"]].map(([u, n]) => `<button type="button" data-action="units" data-u="${u}" aria-pressed="${(s.settings.units || "") === u}">${n}</button>`).join("")}</div></section>
      ${householdHTML(s)}
      <section class="sec set"><h2>Instagram</h2>
        <p class="status">${esc(status)}</p>
        <form data-form="collection" class="row">${field("value", "Collection", "", "text", 'autocomplete="off" spellcheck="false" autocapitalize="off"')}<button class="btn" type="submit">Save</button></form>
        <h3>Sign-in</h3>
        ${si ? `<div class="row"><span class="sub">Added ${esc(day(si.added))}</span><button type="button" class="btn" data-action="signin-forget">Forget</button></div>` : ""}
        <form data-form="ig-cookies" class="stack"><label class="field"><span>Cookies</span><textarea name="cookies" class="cookies" spellcheck="false" autocomplete="off" autocapitalize="off" required></textarea></label>
          <button class="btn" type="submit">${si ? "Replace" : "Save"}</button></form>
        <h3>Extension</h3>
        <div class="row">${ig.downloads.firefox ? `<a class="btn" href="api/ext/firefox">Firefox or Zen</a>` : ""}${ig.downloads.chrome ? `<a class="btn" href="api/ext/chrome" download>Chrome</a>` : ""}</div>
        <div class="row"><button type="button" class="btn" data-action="browser-key"${br ? ' data-connected="1"' : ""}>${br ? "New connection" : "Connect a browser"}</button>${br ? `<button type="button" class="btn" data-action="browser-forget">Disconnect</button>` : ""}</div>
        ${browserKey ? `<div class="invite-code"><span class="sub">Connection</span><input class="conn" type="text" readonly value="${esc(browserKey)}"><button type="button" class="btn" data-action="copy-key">Copy</button></div>` : ""}</section>
      <section class="sec set"><h2>Your recipes</h2>
        <div class="row"><a class="btn" href="#/add">${I.plus}Add</a><a class="btn" href="api/export" download>${I.download}Download all</a></div></section>
      ${k ? `<section class="sec set"><h2>Kitchen</h2>
        <button type="button" class="switch" role="switch" aria-checked="${!k.paused}" data-action="pause"><span>Check Instagram</span><span class="track"><span class="knob"></span></span></button>
        <form data-form="kitchen" class="stack">
          ${field("check_hours", "Check every (hours)", k.check_hours, "number", 'min="1" max="168"')}
          ${field("scan_pages", "Pages each check", k.scan_pages, "number", 'min="1" max="5"')}
          ${field("per_hour", "Reels an hour", k.per_hour, "number", 'min="1" max="10"')}
          ${field("per_run", "Reels each run", k.per_run, "number", 'min="1" max="100"')}
          ${field("notes_dir", "Notes folder", k.notes_dir)}${field("photos_dir", "Photos folder", k.photos_dir)}${field("note_tag", "Note tag", k.note_tag)}
          ${field("app_url", "App address", k.app_url, "url")}
          <button class="btn" type="submit">Save</button></form></section>
      <section class="sec set"><h2>Accounts</h2>
        <ul class="accts">${s.accounts.map((a) => `<li><span class="t">${esc(a.name)}</span><span class="sub">${esc(a.id)}${a.admin ? " · owner" : ""}</span>
          ${a.id === s.account.id ? "" : `<form data-form="reset" data-id="${esc(a.id)}" class="row mini-form"><input name="password" type="password" placeholder="New password" minlength="8" autocomplete="new-password"><button class="btn" type="submit">Set</button><button type="button" class="btn btn-icon" data-action="remove-account" data-id="${esc(a.id)}" aria-label="Remove">${I.trash}</button></form>`}</li>`).join("")}</ul>
        <form data-form="invite" class="stack"><h3>Invite</h3>${field("email", "Email", "", "email")}${field("name", "Name", "")}<button class="btn btn-accent" type="submit">Send invite</button></form>
        ${lastInvite ? `<div class="invite-code"><span class="sub">Code for ${esc(lastInvite.email)}</span><b>${esc(lastInvite.code)}</b><span class="cap">${esc(lastInvite.link)}</span></div>` : ""}
        ${s.invites && s.invites.length ? `<ul class="accts">${s.invites.map((i) => `<li><span class="t">${esc(i.name || i.email)}</span><span class="sub">${esc(i.email)} · invited · until ${esc(day(i.expires))}</span>
          <button type="button" class="btn btn-icon" data-action="invite-cancel" data-email="${esc(i.email)}" aria-label="Cancel">${I.x}</button></li>`).join("")}</ul>` : ""}
        <form data-form="account" class="stack"><h3>New account</h3>${field("name", "Name", "")}${field("id", "Username", "", "text", 'autocapitalize="none" spellcheck="false"')}${field("password", "Password", "", "password", 'minlength="8" autocomplete="new-password"')}<button class="btn" type="submit">Add account</button></form></section>` : ""}
      <p class="msg" id="msg" role="status"></p>
    </div>`;
  }
  function householdHTML(s) {                         // one week and one shopping list for two or more accounts
    const mine = (ME.memory.household || []);
    const all = s.accounts || [];
    const hs = s.households || [];
    if (!mine.length && !(s.kitchen && all.length > 1)) return "";
    const inOne = new Set(hs.flatMap((h) => h.members));
    return `<section class="sec set"><h2>Week and list</h2>
      ${mine.length ? `<div class="row"><span class="status">With ${esc(mine.map(nameOf).join(", "))}</span><button type="button" class="btn" data-action="hh-leave" data-aid="${esc(s.account.id)}">Stop sharing</button></div>` : ""}
      ${s.kitchen ? `${hs.filter((h) => !h.members.includes(s.account.id)).map((h) => `<div class="row"><span class="status">${esc(h.members.map(nameOf).join(" · "))}</span>
          ${h.members.map((m) => `<button type="button" class="btn" data-action="hh-leave" data-aid="${esc(m)}">${esc(nameOf(m))} ${I.x}</button>`).join("")}</div>`).join("")}
        ${all.filter((a) => !inOne.has(a.id)).length >= 2 ? `<form data-form="household" class="stack"><h3>Share between</h3><div class="checks">${all.filter((a) => !inOne.has(a.id)).map((a) =>
          `<label class="check"><input type="checkbox" name="m" value="${esc(a.id)}"> ${esc(a.name)}</label>`).join("")}</div><button class="btn" type="submit">Share the week and list</button></form>` : ""}` : ""}
      </section>`;
  }
  function say(text, bad) {
    const m = document.getElementById("msg");
    if (m) { m.textContent = text; m.classList.toggle("bad", !!bad); clearTimeout(say.t); say.t = setTimeout(() => { m.textContent = ""; }, bad ? 6000 : 2500); }
  }
  async function setting(op, args, ok) {
    try {
      await post("api/settings", Object.assign({ op }, args));
      if (ok) say(ok);
      return true;
    } catch (e) {
      if (e instanceof SignedOut) signInPage(); else say(e.message, true);
      return false;
    }
  }

  /* ---------- a reel shared from the phone (the manifest's share_target opens ./?title=&text=&url=) ---------- */
  async function sharedPage() {
    const text = sessionStorage.getItem("mk.share");
    if (text != null) {
      try {
        shareResult = await addLink(text);
        LIST = await getJSON("api/recipes");
      } catch (e) {
        if (e instanceof SignedOut) throw e;          // kept for after signing in
        shareResult = { error: e.message };
      }
      sessionStorage.removeItem("mk.share");
    }
    const d = shareResult;
    const r = d.code ? byCode(d.code) : null;
    const head = d.error ? "Not a recipe link" : r && d.done ? "Already in Matkon" : d.new ? "Added" : "Already on the way";
    return `<div class="wrap narrow">${topBar()}
      <section class="shared"><h2>${esc(head)}</h2>${r && d.done ? `<ul class="hlist">${rowHTML(r)}</ul>` : ""}
        <a class="btn" href="#/">Done</a></section></div>`;
  }

  /* ---------- router ---------- */
  let lastRoute = "";
  function route() {
    return location.hash.replace(/^#\/?/, "").split("/").map((p) => { try { return decodeURIComponent(p); } catch (e) { return p; } });
  }
  async function render(keepScroll) {
    const [page, code, n] = route();
    const key = location.hash;
    const same = key === lastRoute;
    if (!same) { stopSpeaking(); if (!keepScroll) playing = null; if (page !== "settings") browserKey = null; if (page !== "add") addResult = null; if (toastEl) toastEl.hidden = true; }
    if (!same && page && lastRoute && !lastRoute.replace(/^#\/?/, "")) sessionStorage.setItem("mk.homeY", String(window.scrollY));
    let html, r = null;
    if (page === "join") { signInPage("", "join", { email: code || "", code: n || "" }); lastRoute = key; return; }
    if (page === "shared" && !shareResult && sessionStorage.getItem("mk.share") == null) { location.replace("#/"); return; }
    try {
      await loadAll();
      if (page === "r" || page === "cook" || page === "edit") r = await loadOne(code);
      if (!page && !SUGGEST) getJSON("api/suggest").then((d) => { SUGGEST = d.suggest; const el = document.getElementById("next"); if (el) el.innerHTML = nextHTML(); }).catch(() => {});
      if (page === "r") html = recipePage(r);
      else if (page === "cook") html = cookPage(r, n === "done" ? "done" : parseInt(n, 10) || 1);
      else if (page === "edit") html = r.can_edit ? editPage(r) : recipePage(r);
      else if (page === "pantry") html = pantryPage();
      else if (page === "add") html = addPage();
      else if (page === "week") html = weekPage();
      else if (page === "list") html = listPage();
      else if (page === "history") html = await historyPage(code);
      else if (page === "settings") html = await settingsPage();
      else if (page === "shared") html = await sharedPage();
      else { creator = page === "from" && code ? code : null; html = home(); }
    } catch (e) {
      if (e instanceof SignedOut) { signInPage(); return; }
      app.innerHTML = `<div class="wrap"><header class="top"><a class="mark" href="#/"><img src="icon.svg" alt=""><h1>Matkon</h1></a></header><p class="empty">Can't reach Matkon</p><p style="text-align:center"><button class="btn" type="button" onclick="location.reload()">Try again</button></p></div>`;
      return;
    }
    const y = window.scrollY;
    app.innerHTML = html;
    const titles = { week: "Week", list: "List", history: "History", settings: "Settings", pantry: "What can I make?", add: "Add" };
    document.title = r ? `${r.title} · Matkon` : titles[page] ? `${titles[page]} · Matkon` : "Matkon";
    setWake(page === "cook" || (page === "r" && store.get("awake", true)));
    if (!same && page === "r") remember("view", { code });
    if (!same && page === "cook" && n !== "done") remember("step", { code, n: parseInt(n, 10) || 1 });
    if (same && keepScroll) window.scrollTo(0, y);
    else if (!page) window.scrollTo(0, +(sessionStorage.getItem("mk.homeY") || 0));
    else {
      window.scrollTo(0, 0);
      const h = app.querySelector("h1[tabindex], .said[tabindex]");
      if (h && lastRoute) h.focus({ preventScroll: true });
    }
    lastRoute = key;
    tick();
  }

  /* ---------- events ---------- */
  let noteTimer = null;
  document.addEventListener("input", (e) => {
    if (e.target.id === "q") {
      query = e.target.value;
      document.getElementById("grid").innerHTML = gridHTML();
      document.getElementById("next").innerHTML = nextHTML();
      const c = document.querySelector("[data-action=clear]"); if (c) c.hidden = !query;
    } else if (e.target.id === "note") {
      const code = e.target.dataset.code, text = e.target.value;
      M().notes[code] = text;
      clearTimeout(noteTimer);
      noteTimer = setTimeout(() => remember("note", { code, text }), 800);
    }
  });
  document.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-action]");
    if (!b) return;
    const act = b.dataset.action;
    const [page, code, n] = route();
    const r = cur(code);
    if (act === "lang") { langChoice[code] = b.dataset.to; render(true); return; }
    if (act === "filter") openFilter();
    else if (act === "more" && r) moreSheet(r);
    else if (act === "print") window.print();
    else if (act === "surprise") surprise();
    else if (act === "coll-rename") {
      const c = collOf(b.dataset.id);
      const name = c && (prompt("Name", c.name) || "").trim();
      if (name) { change("coll-rename", { id: c.id, name }, (m) => { const x = m.collections.find((y) => y.id === c.id); if (x) x.name = name; }); render(true); }
    }
    else if (act === "coll-delete") {
      const c = collOf(b.dataset.id);
      if (c && confirm(`Delete "${c.name}"?`)) { kind = "All"; change("coll-delete", { id: c.id }, (m) => { m.collections = m.collections.filter((y) => y.id !== c.id); }); render(true); }
    }
    else if (act === "units") { const u = b.dataset.u; ME.memory.settings.units = u; await remember("setting", { key: "units", value: u }); render(true); }
    else if (act === "again" && r) { const f = +b.dataset.f; if (f === 1) delete factors[code]; else factors[code] = f; location.hash = `#/cook/${code}/1`; }
    else if (act === "pantry-add") pantrySet(pantry().concat([b.dataset.p]));
    else if (act === "pantry-del") pantrySet(pantry().filter((x) => x !== b.dataset.p));
    else if (act === "aisle" && window.MatkonAisles) aisleSheet(b.dataset.key, b.dataset.item);
    else if (act === "cal") { calOff = Math.min(0, calOff + +b.dataset.d); render(true); }
    else if (act === "cook-note") {
      const e2 = (M().cooked || []).find((x) => x.id === b.dataset.id);
      if (e2) noteSheet(e2);
    }
    else if (act === "hh-leave") { if (confirm("Stop sharing the week and list?") && await setting("household-leave", { aid: b.dataset.aid }, "Done")) { ME = null; render(true); } }
    else if (act === "ed-save" && r) saveEdit(r, false);
    else if (act === "ed-revert" && r) saveEdit(r, true);
    else if (act === "ed-add-ing" && r) b.previousElementSibling.insertAdjacentHTML("beforeend", edIng(lab(r), {}));
    else if (act === "ed-add-group" && r) document.getElementById("ed-groups").insertAdjacentHTML("beforeend", edGroup(lab(r), { name: "", items: [] }));
    else if (act === "ed-add-step" && r) { const box = document.getElementById("ed-steps"); box.insertAdjacentHTML("beforeend", edStep(lab(r), {}, box.children.length)); box.lastElementChild.querySelector("textarea").focus(); }
    else if (act === "ed-del") { const x = b.closest(".ei, .es"); if (x) { x.remove(); renumber(); } }
    else if (act === "ed-del-group") { const x = b.closest(".eg"); if (x) x.remove(); }
    else if (act === "kind") { kind = b.dataset.kind; document.querySelector(".kinds").innerHTML = kindsHTML(); document.getElementById("grid").innerHTML = gridHTML(); document.getElementById("next").innerHTML = nextHTML(); document.getElementById("collbar").innerHTML = collBarHTML(); }
    else if (act === "clear") { query = ""; const q = document.getElementById("q"); q.value = ""; q.focus(); document.getElementById("grid").innerHTML = gridHTML(); document.getElementById("next").innerHTML = nextHTML(); b.hidden = true; }
    else if (act === "play") { playing = code; render(true); }
    else if (act === "factor" && r) {
      const f = +b.dataset.f;
      if (f === 1) delete factors[code]; else factors[code] = f;
      const l = lab(r);
      const a = document.getElementById("amounts"); if (a) a.outerHTML = amountsHTML(r, l);
      const g = document.getElementById("ing-list"); if (g) g.innerHTML = ingredientsHTML(r, l);
    }
    else if (act === "plan" && r) pickDay("Plan", (day) => { planAdd(code, day); const d = fromIso(day); toast(dayName(d) + " · " + shortDate(d), "#/week"); });
    else if (act === "to-list" && r) { if (addToList(r)) toast(lab(r).onList, "#/list"); }
    else if (act === "plan-pick") pickRecipe(b.dataset.day);
    else if (act === "plan-move") {
      const id = b.dataset.id;
      pickDay("Move", (day) => change("plan-move", { id, day }, (m) => m.plan.forEach((p) => { if (p.id === id) p.day = day; })));
    }
    else if (act === "plan-remove") { const id = b.dataset.id; change("plan-remove", { id }, (m) => { m.plan = m.plan.filter((p) => p.id !== id); }); }
    else if (act === "week-list") weekToList();
    else if (act === "shop-tick") {
      const ids = b.dataset.ids.split(","), done = b.getAttribute("aria-pressed") !== "true";
      change("shop-tick", { ids, done }, (m) => m.shop.forEach((i) => { if (ids.includes(i.id)) i.done = done; }));
    }
    else if (act === "shop-remove") { const ids = b.dataset.ids.split(","); change("shop-remove", { ids }, (m) => { m.shop = m.shop.filter((i) => !ids.includes(i.id)); }); }
    else if (act === "shop-clear-done") change("shop-clear", { done: true }, (m) => { m.shop = m.shop.filter((i) => !i.done); });
    else if (act === "shop-clear-all") { if (confirm("Clear the whole list?")) change("shop-clear", { done: false }, (m) => { m.shop = []; }); }
    else if (act === "shop-share") shareList();
    else if (act === "tick") {
      const t = ticked(code), k = b.dataset.k;
      if (t.has(k)) t.delete(k); else t.add(k);
      saveTicks(code, t);
      document.querySelectorAll(`[data-action=tick][data-k="${k}"]`).forEach((x) => { x.classList.toggle("done", t.has(k)); x.setAttribute("aria-pressed", t.has(k)); });
    }
    else if (act === "save") { const on = !M().saved[code]; if (on) M().saved[code] = 1; else delete M().saved[code]; render(true); remember("save", { code, on }); }
    else if (act === "rate") {
      const v = +b.dataset.n === (M().ratings[code] || 0) ? 0 : +b.dataset.n;
      if (v) M().ratings[code] = v; else delete M().ratings[code];
      document.querySelectorAll(".rating").forEach((g) => { g.outerHTML = ratingHTML(code); });
      remember("rate", { code, rating: v });
    }
    else if (act === "made" && r) madeSheet(r);
    else if (act === "finish") { await remember("cooked", { code, id: newId(), factor: factor(code) }); location.hash = `#/cook/${code}/done`; }
    else if (act === "uncook") { await remember("uncook", { id: b.dataset.id }); render(true); }
    else if (act === "read" && r) {
      const l = lab(r);
      const ings = r.ingredient_groups.flatMap((g) => g.items.map((i) => [UA(Amt.scale(i.amount, factor(code)), r.lang), i.item].filter(Boolean).join(" ")));
      speak([r.title + ".", l.ing + ".", ...ings, l.steps + ".", ...r.steps.map((s) => UT(s.text, r.lang))], "r:" + code, r.lang, () => render(true));
      render(true);
    }
    else if (act === "read-step" && r) { const s = r.steps[+b.dataset.i]; if (s) { speaking = null; speak([UT(s.text, r.lang)], "s:" + code, r.lang); } }
    else if (act === "awake") { const on = !store.get("awake", true); store.set("awake", on); setWake(on); b.setAttribute("aria-checked", on); }
    else if (act === "timer" && r) startTimer(+b.dataset.min, code, r.title);
    else if (act === "timer-stop") stopTimer();
    else if (act === "sheet" && r) openSheet(r);
    else if (act === "signout") { await post("api/signout").catch(() => {}); signInPage(); }
    else if (act === "english") { const on = b.getAttribute("aria-checked") !== "true"; if (await setting("english", { value: on })) { b.setAttribute("aria-checked", on); Object.keys(FULL).forEach((c) => delete FULL[c]); Object.keys(langChoice).forEach((c) => delete langChoice[c]); ME.memory.settings.english = on; } }
    else if (act === "nutrition") { const on = b.getAttribute("aria-checked") !== "true"; if (await setting("nutrition", { value: on })) { b.setAttribute("aria-checked", on); Object.keys(FULL).forEach((c) => delete FULL[c]); } }
    else if (act === "browser-key") {
      if (b.dataset.connected && !confirm("A new connection stops the old one. Make one?")) return;
      try { const d = await post("api/settings", { op: "browser-key" }); browserKey = location.origin + location.pathname.replace(/\/+$/, "") + "/#/key/" + d.key; ME = null; render(true); }
      catch (err) { if (err instanceof SignedOut) signInPage(); else say(err.message, true); }
    }
    else if (act === "signin-forget") { if (confirm("Forget the Instagram sign-in?") && await setting("signin-forget", {}, "Forgotten")) { ME = null; render(true); } }
    else if (act === "browser-forget") { if (confirm("Disconnect the browser?") && await setting("browser-forget", {}, "Disconnected")) { browserKey = null; ME = null; render(true); } }
    else if (act === "copy-key") {
      const i = document.querySelector("input.conn");
      try { await navigator.clipboard.writeText(i.value); say("Copied"); } catch (err) { i.select(); }
    }
    else if (act === "pause") { const on = b.getAttribute("aria-checked") === "true"; if (await setting("pause", { value: on }, on ? "Paused" : "Checking Instagram again")) render(true); }
    else if (act === "mode") signInPage("", b.dataset.mode);
    else if (act === "invite-cancel") { if (await setting("invite-cancel", { email: b.dataset.email }, "Invite cancelled")) render(true); }
    else if (act === "email-set") {
      const c = document.querySelector("form[data-form=email] input[name=code]");
      if (await setting("email-set", { email: emailPending, code: c ? c.value : "" }, "Email saved")) { emailPending = null; ME = null; render(true); }
    }
    else if (act === "to-password") { const p = document.getElementById("password"); p.scrollIntoView({ behavior: "smooth", block: "center" }); p.querySelector("input").focus({ preventScroll: true }); }
    else if (act === "remove-account") { if (confirm("Remove this account?") && await setting("account-remove", { id: b.dataset.id })) { ME = null; render(true); } }
  });
  document.addEventListener("submit", async (e) => {
    const f = e.target.closest("form[data-form]");
    if (!f) return;
    e.preventDefault();
    const v = Object.fromEntries(new FormData(f).entries());
    const kindOf = f.dataset.form;
    if (kindOf === "signin") {
      try { await post("api/signin", { username: v.username, password: v.password }); ME = null; LIST = null; render(false); }
      catch (err) { signInPage(err.message); }
      return;
    }
    if (kindOf === "join" || kindOf === "reset-pw") {
      try {
        await post(kindOf === "join" ? "api/join" : "api/reset", v);
        ME = null; LIST = null;
        if (route()[0] === "join") location.hash = "#/"; else render(false);
      } catch (err) { signInPage(err.message, kindOf === "join" ? "join" : "reset", v); }
      return;
    }
    if (kindOf === "forgot") {
      try { await post("api/forgot", { email: v.email }); signInPage("", "reset", { email: v.email }); }
      catch (err) { signInPage(err.message, "forgot", v); }
      return;
    }
    if (kindOf === "email") {
      try {
        const d = await post("api/settings", { op: "email-code", email: v.email });
        if (d.set) { emailPending = null; say("Email saved"); ME = null; } else { emailPending = v.email; say("Code sent"); }
        render(true);
      } catch (err) { if (err instanceof SignedOut) signInPage(); else say(err.message, true); }
      return;
    }
    if (kindOf === "invite") {
      try {
        const d = await post("api/settings", { op: "invite", email: v.email, name: v.name });
        lastInvite = d.sent ? null : { email: v.email, code: d.code, link: d.link };
        say(d.sent ? "Invite sent to " + v.email : "The email didn't go out: pass on the code", !d.sent);
        render(true);
      } catch (err) { if (err instanceof SignedOut) signInPage(); else say(err.message, true); }
      return;
    }
    if (kindOf === "ask") {
      const r = cur(route()[1]), q = (v.q || "").trim();
      if (r && q) ask(r, q);
      return;
    }
    if (kindOf === "made") {
      const code = f.dataset.code, pick = f.querySelector("[data-mf][aria-pressed=true]");
      await remember("cooked", { code, id: newId(), factor: pick ? +pick.dataset.mf : 1, note: (v.note || "").trim() });
      const sh = f.closest(".sheet"); if (sh) sh.remove();
      render(true);
      return;
    }
    if (kindOf === "pantry-add") {
      const item = (v.item || "").trim();
      if (item && !pantry().some((x) => x.toLowerCase() === item.toLowerCase())) pantrySet(pantry().concat([item]));
      f.reset();
      const i = f.querySelector("input"); if (i) i.focus();
      return;
    }
    if (kindOf === "add-link") {
      say("Adding…");
      try { addResult = await addLink(v.url); LIST = await getJSON("api/recipes"); }
      catch (err) { if (err instanceof SignedOut) return signInPage(); addResult = { error: err.message }; }
      render(true);
      return;
    }
    if (kindOf === "household") {
      const members = new FormData(f).getAll("m");
      if (members.length < 2) return say("Pick two or more", true);
      if (await setting("household", { members }, "Shared")) { ME = null; render(true); }
      return;
    }
    if (kindOf === "shop-add") {
      const item = (v.item || "").trim();
      if (item) {
        const i = { id: newId(), item, amount: "" };
        change("shop-add", { items: [i] }, (m) => { m.shop = (m.shop || []).concat([Object.assign({ code: null, done: false, at: Math.floor(Date.now() / 1000) }, i)]); });
      }
      f.reset();
      return;
    }
    if (kindOf === "name") { if (await setting("name", { name: v.name }, "Saved")) ME = null; }
    else if (kindOf === "password") { if (await setting("password", { old: v.old, new: v.new }, "Password changed")) f.reset(); }
    else if (kindOf === "collection") { if (await setting("collection", { value: v.value }, "Saved")) { ME = null; render(true); } }
    else if (kindOf === "ig-cookies") {
      // the browser it's pasted in is the one the server dresses as: its User-Agent and languages go along
      if (await setting("signin", { cookies: v.cookies, ua: navigator.userAgent, langs: (navigator.languages || [navigator.language]).join(",") }, "Saved")) { ME = null; render(true); }
    }
    else if (kindOf === "kitchen") setting("kitchen", v, "Saved");
    else if (kindOf === "account") { if (await setting("account-add", v, "Account added")) { ME = null; render(true); } }
    else if (kindOf === "reset") { if (await setting("account-password", { id: f.dataset.id, password: v.password }, "Password set")) f.reset(); }
  });
  document.addEventListener("change", (e) => {
    if (e.target.matches("input[data-photos]")) addPhotos(e.target.files);
  });

  /* ---------- dragging a planned recipe to another day (mouse, finger or pen) ---------- */
  let drag = null;
  document.addEventListener("pointerdown", (e) => {
    const g = e.target.closest("[data-drag]");
    if (!g) return;
    e.preventDefault();
    const li = g.closest("li"), rect = li.getBoundingClientRect();
    const ghost = li.cloneNode(true);
    ghost.className = "ghost";
    Object.assign(ghost.style, { width: rect.width + "px", left: rect.left + "px", top: rect.top + "px" });
    document.body.appendChild(ghost);
    li.classList.add("dragging");
    drag = { id: g.dataset.drag, li, ghost, dy: e.clientY - rect.top, over: null, from: g.closest("[data-day]").dataset.day };
    try { g.setPointerCapture(e.pointerId); } catch (x) { /* fine without */ }
  });
  document.addEventListener("pointermove", (e) => {
    if (!drag) return;
    drag.ghost.style.top = e.clientY - drag.dy + "px";
    const el = document.elementFromPoint(e.clientX, e.clientY);
    const d = el && el.closest("[data-day]");
    if (drag.over !== d) { if (drag.over) drag.over.classList.remove("drop"); drag.over = d; if (d) d.classList.add("drop"); }
    if (e.clientY < 70) window.scrollBy(0, -14); else if (e.clientY > window.innerHeight - 70) window.scrollBy(0, 14);
  });
  const endDrag = () => {
    if (!drag) return;
    const { id, from, over, ghost, li } = drag;
    drag = null;
    ghost.remove(); li.classList.remove("dragging");
    if (over) over.classList.remove("drop");
    if (over && over.dataset.day !== from) { const day = over.dataset.day; change("plan-move", { id, day }, (m) => m.plan.forEach((x) => { if (x.id === id) x.day = day; })); }
  };
  document.addEventListener("pointerup", endDrag);
  document.addEventListener("pointercancel", endDrag);

  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, .sheet")) return;
    const [page, code, n] = route();
    if (page !== "cook" || n === "done") return;
    const k = parseInt(n, 10) || 1;
    const r = cur(code);
    const rtl = r && r.lang === "he";
    const fwd = rtl ? "ArrowLeft" : "ArrowRight", bwd = rtl ? "ArrowRight" : "ArrowLeft";
    if ((e.key === fwd || e.key === " ") && r && k < r.steps.length) { e.preventDefault(); location.hash = `#/cook/${code}/${k + 1}`; }
    if (e.key === bwd && k > 1) location.hash = `#/cook/${code}/${k - 1}`;
  });
  window.addEventListener("hashchange", () => render(false));
  window.addEventListener("pageshow", (e) => { if (e.persisted) { ME = null; LIST = null; render(true); } });
  document.addEventListener("visibilitychange", () => {
    // back to the app after a while: what another device did (ticks, step, notes) and new recipes
    if (document.visibilityState !== "visible" || !ME) return;
    Promise.all([getJSON("api/me"), getJSON("api/recipes")]).then(([me, list]) => {
      if (queue.length) return;                       // a change still on its way: its answer brings the rest
      ME = me; LIST = list; SUGGEST = null;
      const page = route()[0];
      if (!page || page === "r") render(true); else paint();
    }).catch(() => {});
  });

  if (timer && timer.end < Date.now() - 3600e3) { timer = null; store.set("timer", null); }
  const shared = new URLSearchParams(location.search);
  if (["title", "text", "url"].some((k) => shared.has(k))) {
    sessionStorage.setItem("mk.share", ["url", "text", "title"].map((k) => shared.get(k) || "").join(" "));
    shareResult = null;
    history.replaceState(null, "", location.pathname + "#/shared");
  }
  render(false);
  if (canSpeak) speechSynthesis.getVoices();
})();

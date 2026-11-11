/* Matkon: amounts and temperatures in the units a person reads in.
   window.MatkonUnits.amount("1 cup", "metric") → "240 ml";  .text("Bake at 350°F", "metric") → "Bake at 180°C".
   "" (as written) changes nothing. Spoons stay spoons in metric (every kitchen has them); an amount that
   already gives both ("3 cups (720ml)") stays as written. The same rules as the Android app. */
(function () {
  "use strict";
  const GL = { "½": 0.5, "⅓": 1 / 3, "⅔": 2 / 3, "¼": 0.25, "¾": 0.75, "⅕": 0.2, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875 };
  const G = "½⅓⅔¼¾⅕⅛⅜⅝⅞";
  const Q = `(?:\\d+\\s+\\d+\\s*/\\s*\\d+|\\d+\\s*/\\s*\\d+|\\d+(?:[.,]\\d+)?\\s*[${G}]?|[${G}])`;
  const NICE = [[0, ""], [0.125, "⅛"], [0.25, "¼"], [1 / 3, "⅓"], [0.5, "½"], [2 / 3, "⅔"], [0.75, "¾"], [1, ""]];

  function value(q) {
    const s = String(q).trim().replace(/,/g, ".");
    let m = s.match(/^(\d+)\s+(\d+)\s*\/\s*(\d+)$/);
    if (m) return +m[3] ? +m[1] + m[2] / m[3] : null;
    if ((m = s.match(/^(\d+)\s*\/\s*(\d+)$/))) return +m[2] ? m[1] / m[2] : null;
    if ((m = s.match(new RegExp(`^(\\d+(?:\\.\\d+)?)?\\s*([${G}])?$`)))) {
      if (!m[1] && !m[2]) return null;
      return (m[1] ? parseFloat(m[1]) : 0) + (m[2] ? GL[m[2]] : 0);
    }
    return null;
  }
  function frac(x) {                                   // 1.5 → "1½", 0.33 → "⅓"
    const whole = Math.floor(x), f = x - whole;
    const near = NICE.reduce((a, b) => (Math.abs(b[0] - f) < Math.abs(a[0] - f) ? b : a));
    if (Math.abs(near[0] - f) < 0.07) {
      const w = near[0] === 1 ? whole + 1 : whole;
      return !near[1] ? String(w) : w === 0 ? near[1] : w + near[1];
    }
    return String(Math.round(x * 10) / 10);
  }
  const roundTo = (x, step) => Math.round(x / step) * step;

  // what each unit is: [kind, system, size in ml / g / cm]
  const U = {
    tsp: ["vol", "spoon", 5], teaspoon: ["vol", "spoon", 5], teaspoons: ["vol", "spoon", 5], "כפית": ["vol", "spoon", 5], "כפיות": ["vol", "spoon", 5],
    tbsp: ["vol", "spoon", 15], tbs: ["vol", "spoon", 15], tablespoon: ["vol", "spoon", 15], tablespoons: ["vol", "spoon", 15], "כף": ["vol", "spoon", 15], "כפות": ["vol", "spoon", 15],
    cup: ["vol", "us", 240], cups: ["vol", "us", 240], c: ["vol", "us", 240], "כוס": ["vol", "us", 240], "כוסות": ["vol", "us", 240],
    "fl oz": ["vol", "us", 29.57], pint: ["vol", "us", 473], pints: ["vol", "us", 473], quart: ["vol", "us", 946], quarts: ["vol", "us", 946], gallon: ["vol", "us", 3785],
    ml: ["vol", "metric", 1], "מ\"ל": ["vol", "metric", 1], "מ״ל": ["vol", "metric", 1], cl: ["vol", "metric", 10], dl: ["vol", "metric", 100],
    l: ["vol", "metric", 1000], liter: ["vol", "metric", 1000], liters: ["vol", "metric", 1000], litre: ["vol", "metric", 1000], litres: ["vol", "metric", 1000], "ליטר": ["vol", "metric", 1000],
    oz: ["wt", "us", 28.35], ounce: ["wt", "us", 28.35], ounces: ["wt", "us", 28.35], lb: ["wt", "us", 453.6], lbs: ["wt", "us", 453.6], pound: ["wt", "us", 453.6], pounds: ["wt", "us", 453.6],
    g: ["wt", "metric", 1], gr: ["wt", "metric", 1], gram: ["wt", "metric", 1], grams: ["wt", "metric", 1], "גרם": ["wt", "metric", 1],
    kg: ["wt", "metric", 1000], kilo: ["wt", "metric", 1000], "ק\"ג": ["wt", "metric", 1000], "ק״ג": ["wt", "metric", 1000], "קילו": ["wt", "metric", 1000],
    inch: ["len", "us", 2.54], inches: ["len", "us", 2.54], cm: ["len", "metric", 1],
  };
  const NAMES = Object.keys(U).sort((a, b) => b.length - a.length).map((u) => u.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  // a number (or range) and a unit right after it, at the start of an amount
  const LEAD = new RegExp(`^(\\s*(?:about|approx\\.?|~|כ-?)?\\s*)(${Q})(?:(\\s*(?:-|–|—|to|עד)\\s*)(${Q}))?\\s*(${NAMES.join("|")})(?![\\p{L}])`, "iu");

  const he = (lang) => lang === "he";
  function show(base, kind, mode, lang) {             // base ml/g/cm → [number, unit] in the other system
    if (mode === "metric") {
      if (kind === "vol") return base >= 1000 ? [String(Math.round(base / 100) / 10), he(lang) ? "ליטר" : "l"] : [String(base < 20 ? Math.round(base) : roundTo(base, 5)), he(lang) ? "מ״ל" : "ml"];
      if (kind === "wt") return base >= 1000 ? [String(Math.round(base / 100) / 10), he(lang) ? "ק״ג" : "kg"] : [String(base < 20 ? Math.round(base) : base < 100 ? roundTo(base, 5) : roundTo(base, 10)), he(lang) ? "גרם" : "g"];
      return [String(Math.round(base * 2) / 2), "cm"];
    }
    if (kind === "vol") {
      if (base >= 60) {
        const c = base / 240;
        const n = c < 1 ? [[0.25, "¼"], [1 / 3, "⅓"], [0.5, "½"], [2 / 3, "⅔"], [0.75, "¾"], [1, "1"]].reduce((a, b) => (Math.abs(b[0] - c) < Math.abs(a[0] - c) ? b : a))[1]
          : frac(c >= 2 ? roundTo(c, 0.25) : c);
        const many = value(n) > 1;
        return [n, he(lang) ? (many ? "כוסות" : "כוס") : many ? "cups" : "cup"];
      }
      if (base >= 15) return [frac(base / 15), he(lang) ? "כפות" : "tbsp"];
      return [frac(base / 5), he(lang) ? "כפיות" : "tsp"];
    }
    if (kind === "wt") {
      if (base >= 408) return [frac(roundTo(base / 453.6, 0.25)), "lb"];
      return [frac(Math.max(0.5, roundTo(base / 28.35, 0.5))), "oz"];
    }
    return [frac(roundTo(base / 2.54, 0.25)), he(lang) ? "אינץ׳" : "inch"];
  }
  // does the amount already give it in the wanted system ("3 cups (720ml)")?
  function alreadyBoth(a, mode) {
    const paren = a.match(/\(([^)]*)\)/g);
    if (!paren) return false;
    return paren.some((p) => {
      const m = p.slice(1, -1).match(new RegExp(`(${Q})\\s*(${NAMES.join("|")})(?![\\p{L}])`, "iu"));
      const u = m && U[m[2].toLowerCase()];
      return u && (u[1] === mode || (mode === "us" && u[1] === "us"));
    });
  }

  function amount(a, mode, lang) {
    if (!mode || !a || !a.trim()) return a;
    if (alreadyBoth(a, mode)) return a;
    const m = a.match(LEAD);
    if (!m) return a;
    const u = U[m[5].toLowerCase()] || U[m[5]];
    if (!u) return a;
    const [kind, sys, size] = u;
    if (sys === mode) return a;
    if (sys === "spoon") return a;                    // spoons are spoons everywhere
    const x = value(m[2]), y = m[4] ? value(m[4]) : null;
    if (x == null) return a;
    const [nx, unit] = show(x * size, kind, mode, lang);
    const ny = y != null ? show(y * size, kind, mode, lang)[0] : null;
    const rest = a.slice(m[0].length);
    return m[1] + nx + (ny != null ? m[3] + ny : "") + " " + unit + rest;
  }

  // temperatures, and amounts inside a sentence ("add 2 cups of flour", "bake at 350°F")
  const T_DEG = /(\d{2,3})\s*°\s*([CF])\b/gi;
  const T_WORD = /(\d{2,3})\s*(?:degrees?\s*)?(fahrenheit|celsius|F\b|C\b)/gi;
  const T_BARE_EN = /(\d{2,3})\s+degrees\b(?!\s*(?:F|C|fahrenheit|celsius)\b)/gi;
  const T_BARE_HE = /(\d{2,3})\s*מעלות(?!\s*(?:צלזיוס|פרנהייט))/g;
  const toC = (f) => roundTo((f - 32) * 5 / 9, 10);
  const toF = (c) => (c * 9 / 5 + 32 >= 200 ? roundTo(c * 9 / 5 + 32, 25) : roundTo(c * 9 / 5 + 32, 5));
  function temp(n, unit, mode) {                      // unit "C"/"F"
    if (mode === "metric") return unit === "F" ? `${toC(n)}°C` : `${n}°C`;
    return unit === "C" ? `${toF(n)}°F` : `${n}°F`;
  }
  const IN_TEXT = new RegExp(`(${Q})(?:(\\s*(?:-|–|—|to|עד)\\s*)(${Q}))?\\s*(cups?|tablespoons?|tbsp|teaspoons?|tsp|fl oz|ounces?|oz|lbs?|pounds?|grams?|g|kg|ml|liters?|litres?|inch(?:es)?|cm|כוסות|כוס|גרם|ק"ג|ק״ג|מ"ל|מ״ל|ליטר)(?![\\p{L}])`, "giu");
  function text(t, mode, lang) {
    if (!mode || !t) return t;
    let s = String(t);
    const both = /°\s*C|celsius/i.test(s) && /°\s*F|fahrenheit/i.test(s);
    if (!both) {
      s = s.replace(T_DEG, (all, n, u) => temp(+n, u.toUpperCase(), mode))
        .replace(T_WORD, (all, n, u) => temp(+n, /^f/i.test(u) ? "F" : "C", mode))
        .replace(T_BARE_EN, (all, n) => temp(+n, +n > 260 ? "F" : "C", mode))
        .replace(T_BARE_HE, (all, n) => temp(+n, +n > 260 ? "F" : "C", mode));
    }
    return s.replace(IN_TEXT, (all) => amount(all, mode, lang));
  }

  window.MatkonUnits = { amount, text };
})();

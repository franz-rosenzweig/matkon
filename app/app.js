/* Matkon: recipe reels as recipe pages.
   Plain JS. Data from the server: api/recipes (the list) and api/r/<code> (one recipe).
   Routes:  #/  home   ·   #/r/<code>  a recipe   ·   #/cook/<code>/<n>  cooking, one step at a time
   The kitchen timer survives reloads; read-aloud is the browser's own voice. */
(function () {
  "use strict";

  const app = document.getElementById("app");
  const timerbar = document.getElementById("timerbar");
  let LIST = null;
  const FULL = {};
  let query = "";
  let kind = "All";

  /* ---------- helpers ---------- */
  const store = {
    get(k, d) { try { const v = localStorage.getItem("mk." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("mk." + k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
  };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const norm = (s) => String(s || "").toLowerCase().normalize("NFKD").replace(/\p{M}+/gu, "").replace(/[^\p{L}\p{N} ]+/gu, " ").replace(/\s+/g, " ").trim();
  const fmtMin = (m) => (m < 60 ? `${m} min` : `${Math.floor(m / 60)} hr${m % 60 ? ` ${m % 60} min` : ""}`);
  const fmtClock = (ms) => {
    const s = Math.max(0, Math.ceil(ms / 1000));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(x).padStart(2, "0");
  };
  const ico = (d, extra) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${extra || ""}>${d}</svg>`;
  const I = {
    back: ico('<path d="M15 5l-7 7 7 7"/>', 'class="flip"'),
    search: ico('<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>'),
    x: ico('<path d="M6 6l12 12M18 6L6 18"/>'),
    play: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>',
    check: ico('<path d="M5 12.5l4.5 4.5L19 7.5"/>', 'stroke="#fff" stroke-width="3.2"'),
    clock: ico('<circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2M10 2h4"/>'),
    oven: ico('<rect x="3" y="3" width="18" height="18" rx="2"/><rect x="6" y="9" width="12" height="8" rx="1"/>'),
    people: ico('<circle cx="9" cy="8" r="3.2"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0M16 5.2a3 3 0 0 1 0 5.6M17.5 14.2A5.5 5.5 0 0 1 20.5 19"/>'),
    speak: ico('<path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>'),
    stop: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
    list: ico('<path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01"/>'),
    cook: ico('<path d="M4 11h16v3a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6v-3zM2 11h20M9 4c0 1.5 1 1.5 1 3M13 4c0 1.5 1 1.5 1 3"/>'),
    out: ico('<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>'),
  };

  /* Labels on a recipe page follow the recipe's language. */
  const L = {
    en: { ing: "Ingredients", steps: "Steps", tips: "Tips", nut: "Nutrition", miss: "Not in the reel", serves: "Serves", makes: "Makes", prep: "Prep",
      cook: "Cook", total: "Total", oven: "Oven", start: "Start cooking", watch: "Watch the reel", ig: "Instagram", page: "Recipe page",
      read: "Read aloud", stopRead: "Stop", awake: "Keep the screen on", step: (k, n) => `Step ${k} of ${n}`, next: "Next", backStep: "Back",
      done: "Done", finished: "All done", again: "Start again", toRecipe: "Back to the recipe", uses: "Uses", timer: (m) => `Timer ${fmtMin(m)}`,
      noAmt: "no amount", calories: "Calories", protein: "Protein", carbs: "Carbs", fat: "Fat", per: "per", close: "Close", notRecipe: "Not a recipe" },
    he: { ing: "מצרכים", steps: "אופן ההכנה", tips: "טיפים", nut: "ערכים תזונתיים", miss: "חסר בסרטון", serves: "מנות", makes: "כמות", prep: "הכנה",
      cook: "בישול", total: "סה״כ", oven: "תנור", start: "מתחילים לבשל", watch: "לצפייה בסרטון", ig: "אינסטגרם", page: "דף המתכון",
      read: "הקראה", stopRead: "עצירה", awake: "המסך נשאר דולק", step: (k, n) => `שלב ${k} מתוך ${n}`, next: "הבא", backStep: "הקודם",
      done: "סיימתי", finished: "בתיאבון", again: "מההתחלה", toRecipe: "חזרה למתכון", uses: "צריך", timer: (m) => `טיימר ${m} דק׳`,
      noAmt: "בלי כמות", calories: "קלוריות", protein: "חלבון", carbs: "פחמימות", fat: "שומן", per: "ל", close: "סגירה", notRecipe: "לא מתכון" },
  };
  const lab = (r) => L[r && r.lang === "he" ? "he" : "en"];
  const dirOf = (r) => (r && r.lang === "he" ? ' dir="rtl" lang="he"' : ' dir="ltr" lang="en"');

  /* ---------- ticked ingredients (this visit only) ---------- */
  function ticked(code) {
    try { return new Set(JSON.parse(sessionStorage.getItem("mk.t." + code) || "[]")); } catch (e) { return new Set(); }
  }
  function saveTicks(code, set) { try { sessionStorage.setItem("mk.t." + code, JSON.stringify([...set])); } catch (e) { /* ok */ } }

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

  /* ---------- kitchen timer (survives page changes and reloads) ---------- */
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
    ringing = false; store.set("timer", timer); tickTimer(); render(true);
  }
  function stopTimer() {
    timer = null; ringing = false; store.set("timer", null);
    if (navigator.vibrate) { try { navigator.vibrate(0); } catch (e) { /* ok */ } }
    if (timeup) timeup.hidden = true;
    tickTimer(); render(true);
  }
  function tickTimer() {
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
  setInterval(() => { if (timer) tickTimer(); }, 500);

  /* ---------- data ---------- */
  async function getJSON(u) {
    const r = await fetch(u, { cache: "no-cache" });
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }
  async function loadList() { LIST = await getJSON("api/recipes"); }
  async function loadOne(code) {
    if (!FULL[code]) FULL[code] = await getJSON("api/r/" + encodeURIComponent(code));
    return FULL[code];
  }

  /* ---------- home ---------- */
  function haystack(r) { return norm([r.title, r.user, r.cuisine, r.kind, (r.tags || []).join(" "), (r.items || []).join(" ")].join(" ")); }
  function visible() {
    const words = norm(query).split(" ").filter(Boolean);
    return LIST.recipes.filter((r) => r.is_recipe !== false)
      .filter((r) => kind === "All" || r.kind === kind)
      .filter((r) => words.every((w) => haystack(r).includes(w)));
  }
  function cardHTML(r) {
    return `<li><a class="card" href="#/r/${esc(r.code)}">
      <div class="pic">${r.photo ? `<img src="${esc(r.photo)}" alt="" loading="lazy">` : ""}${r.complete ? "" : `<span class="flag">${r.lang === "he" ? "חסרות כמויות" : "Missing amounts"}</span>`}</div>
      <div class="txt"${dirOf(r)}><div class="t">${esc(r.title)}</div><div class="by" dir="ltr">@${esc(r.user)}</div></div></a></li>`;
  }
  function gridHTML() {
    const list = visible();
    return list.length ? `<ul class="grid">${list.map(cardHTML).join("")}</ul>` : `<p class="empty">No recipes</p>`;
  }
  function kindsHTML() {
    const recipes = LIST.recipes.filter((r) => r.is_recipe !== false);
    const counts = {};
    recipes.forEach((r) => { counts[r.kind] = (counts[r.kind] || 0) + 1; });
    const order = ["Breakfast", "Mains", "Salads & sides", "Soups", "Bread & dough", "Baking & sweets", "Snacks", "Sauces & dips", "Drinks"];
    const kinds = [["All", recipes.length]].concat(order.filter((k) => counts[k]).map((k) => [k, counts[k]]));
    return kinds.map(([k, n]) => `<button type="button" data-action="kind" data-kind="${esc(k)}" aria-pressed="${k === kind}">${esc(k)}<span class="n">${n}</span></button>`).join("");
  }
  function home() {
    const n = LIST.recipes.filter((r) => r.is_recipe !== false).length;
    const notes = [];
    if (LIST.signed_out) notes.push(`<div class="note-bar">Instagram sign-in lapsed</div>`);
    if (LIST.waiting) notes.push(`<div class="note-bar">${LIST.waiting} more on the way</div>`);
    return `<div class="wrap">
      <header class="top"><a class="mark" href="#/"><img src="icon.svg" alt=""><h1>Matkon</h1></a><span class="count">${n} recipes</span></header>
      <div class="search" role="search">${I.search}<input id="q" type="search" placeholder="Search" value="${esc(query)}" autocomplete="off" enterkeyhint="search" aria-label="Search">
        <button type="button" class="clear" data-action="clear" aria-label="Clear"${query ? "" : " hidden"}>${I.x}</button></div>
      <nav class="kinds" aria-label="Kinds">${kindsHTML()}</nav>
      ${notes.join("")}
      <div id="grid">${gridHTML()}</div>
    </div>`;
  }

  /* ---------- recipe ---------- */
  function factsHTML(r, l) {
    const c = [];
    if (r.servings) c.push(`<span class="chip">${I.people}${esc(/^\d+([–-]\d+)?( |$)(as\b|people|servings?\b|$)/.test(r.servings.trim()) ? l.serves : l.makes)} ${esc(r.servings)}</span>`);
    [["prep", l.prep], ["cook", l.cook], ["total", l.total]].forEach(([k, name]) => { if (r.time && r.time[k]) c.push(`<span class="chip">${I.clock}${esc(name)} ${esc(r.time[k])}</span>`); });
    if (r.oven) c.push(`<span class="chip">${I.oven}${esc(l.oven)} ${esc(r.oven)}</span>`);
    return c.length ? `<div class="chips facts">${c.join("")}</div>` : "";
  }
  function ingHTML(i, key, done, l) {
    const what = `${i.amount ? `<span class="amt">${esc(i.amount)}</span> ` : ""}${esc(i.item)}${i.note ? `<span class="nt">, ${esc(i.note)}</span>` : ""}`;
    return `<li><button type="button" class="ing${done ? " done" : ""}" data-action="tick" data-k="${key}" aria-pressed="${done}">
      <span class="box">${I.check}</span><span class="what">${what}${i.amount ? "" : ` <span class="none">· ${esc(l.noAmt)}</span>`}</span></button></li>`;
  }
  function ingredientsHTML(r, l, tickable) {
    const t = ticked(r.code);
    return r.ingredient_groups.map((g, gi) => `${g.name ? `<h3>${esc(g.name)}</h3>` : ""}<ul class="ings">${g.items.map((i, ii) => {
      const key = gi + "." + ii;
      return tickable ? ingHTML(i, key, t.has(key), l) : `<li class="ing"><span class="what">${i.amount ? `<span class="amt">${esc(i.amount)}</span> ` : ""}${esc(i.item)}${i.note ? `<span class="nt">, ${esc(i.note)}</span>` : ""}</span></li>`;
    }).join("")}</ul>`).join("");
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
    return `<section class="sec"><h2>${esc(l.nut)}${n.per ? ` <span style="font-weight:500;color:var(--muted);font-size:15px">· ${esc(n.per)}</span>` : ""}</h2><div class="nut">${c.join("")}</div></section>`;
  }
  function mediaHTML(r, l, playing) {
    if (playing && r.video) return `<div class="media"><video src="${esc(r.video)}" controls playsinline autoplay preload="auto"${r.photo ? ` poster="${esc(r.photo)}"` : ""}></video></div>`;
    return `<div class="media">${r.photo ? `<img src="${esc(r.photo)}" alt="${esc(r.title)}">` : ""}${r.video ? `<button type="button" class="play" data-action="play">${I.play}${esc(l.watch)}</button>` : ""}</div>`;
  }
  let playing = null;
  function recipePage(r) {
    const l = lab(r);
    const reading = speaking === "r:" + r.code;
    const steps = r.steps || [];
    const awake = store.get("awake", true);
    return `<div class="wrap"${dirOf(r)}>
      <div class="bar"><button type="button" class="btn btn-icon" data-action="back" aria-label="Back">${I.back}</button><span class="grow"></span>
        ${canSpeak && steps.length ? `<button type="button" class="btn" data-action="read" aria-pressed="${reading}">${reading ? I.stop + esc(l.stopRead) : I.speak + esc(l.read)}</button>` : ""}</div>
      <article class="recipe">
        <div>${mediaHTML(r, l, playing === r.code)}
          ${"wakeLock" in navigator ? `<button type="button" class="switch" role="switch" aria-checked="${awake}" data-action="awake"><span>${esc(l.awake)}</span><span class="track"><span class="knob"></span></span></button>` : ""}</div>
        <div>
          <header class="head">
            <h1 tabindex="-1">${esc(r.title)}</h1>
            ${r.summary ? `<p class="sum">${esc(r.summary)}</p>` : ""}
            <div class="by" dir="ltr"><a href="${esc(r.reel)}" target="_blank" rel="noopener">@${esc(r.user)}</a>${r.link ? `<a href="${esc(r.link)}" target="_blank" rel="noopener">${esc(l.page)}</a>` : ""}</div>
            ${factsHTML(r, l)}
          </header>
          ${r.is_recipe === false ? `<p class="empty">${esc(l.notRecipe)}</p>` : `
          ${steps.length ? `<div class="actions"><a class="btn btn-accent btn-big" href="#/cook/${esc(r.code)}/1">${I.cook}${esc(l.start)}</a></div>` : ""}
          <div class="two">
            ${r.ingredient_groups.length ? `<section class="sec"><h2>${esc(l.ing)}</h2>${ingredientsHTML(r, l, true)}</section>` : ""}
            ${steps.length ? `<section class="sec"><h2>${esc(l.steps)}</h2><ol class="steps">${steps.map((s, i) => `<li><div class="step"><span class="n">${i + 1}</span><div>${esc(s.text)}${timerChips(r, s, l)}</div></div></li>`).join("")}</ol></section>` : ""}
          </div>
          ${r.tips && r.tips.length ? `<section class="sec"><h2>${esc(l.tips)}</h2><ul class="list">${r.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></section>` : ""}
          ${nutritionHTML(r, l)}
          ${r.missing && r.missing.length ? `<section class="sec miss"><h2>${esc(l.miss)}</h2><ul class="list">${r.missing.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></section>` : ""}`}
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
    if (n === "done" || n > steps.length) {
      return `<div class="cook"${dirOf(r)}>
        <div class="bar"><a class="btn" href="#/r/${esc(r.code)}">${esc(l.close)}</a><span class="name">${esc(r.title)}</span><span style="width:70px"></span></div>
        <div class="body cook-done"><h1 tabindex="-1">${esc(l.finished)}</h1>
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
        <p class="said" tabindex="-1">${esc(s.text)}</p>
        ${uses.length ? `<div class="uses"><span class="lbl">${esc(l.uses)}</span><ul>${uses.map((i) => `<li><b>${esc(i.amount)}</b> ${esc(i.item)}</li>`).join("")}</ul></div>` : ""}
        <div class="tools">${timerChips(r, s, l).replace(/class="chip"/g, 'class="btn"').replace('<div class="chips">', "").replace(/<\/div>$/, "")}
          ${canSpeak ? `<button type="button" class="btn" data-action="read-step" data-i="${k - 1}">${I.speak}${esc(l.read)}</button>` : ""}</div>
      </div>
      <div class="nav">
        <a class="btn" href="${k === 1 ? `#/r/${esc(r.code)}` : `#/cook/${esc(r.code)}/${k - 1}`}">${esc(l.backStep)}</a>
        <a class="btn btn-accent" href="#/cook/${esc(r.code)}/${last ? "done" : k + 1}">${esc(last ? l.done : l.next)}</a>
      </div>
    </div>`;
  }
  function openSheet(r) {
    const l = lab(r);
    const el = document.createElement("div");
    el.className = "sheet";
    el.innerHTML = `<div class="panel"${dirOf(r)} role="dialog" aria-modal="true" aria-label="${esc(l.ing)}"><div class="grip"></div>
      <div class="bar"><h2>${esc(l.ing)}</h2><button type="button" class="btn" data-close>${esc(l.close)}</button></div>${ingredientsHTML(r, l, true)}</div>`;
    const close = () => { el.remove(); document.removeEventListener("keydown", onKey); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    el.addEventListener("click", (e) => { if (e.target === el || e.target.closest("[data-close]")) close(); });
    document.addEventListener("keydown", onKey);
    document.body.appendChild(el);
    el.querySelector("[data-close]").focus();
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
    if (!same) { stopSpeaking(); if (!keepScroll) playing = null; }
    if (!same && page && lastRoute && !lastRoute.replace(/^#\/?/, "")) sessionStorage.setItem("mk.homeY", String(window.scrollY));
    let html, r = null;
    try {
      if (!LIST) await loadList();
      if (page === "r" || page === "cook") r = await loadOne(code);
    } catch (e) {
      app.innerHTML = `<div class="wrap"><header class="top"><a class="mark" href="#/"><img src="icon.svg" alt=""><h1>Matkon</h1></a></header><p class="empty">Can't reach Matkon</p><p style="text-align:center"><button class="btn" type="button" onclick="location.reload()">Try again</button></p></div>`;
      return;
    }
    if (page === "r") html = recipePage(r);
    else if (page === "cook") html = cookPage(r, n === "done" ? "done" : parseInt(n, 10) || 1);
    else html = home();
    const y = window.scrollY;
    app.innerHTML = html;
    document.title = r ? `${r.title} · Matkon` : "Matkon";
    setWake(page === "cook" || (page === "r" && store.get("awake", true)));
    if (same && keepScroll) window.scrollTo(0, y);
    else if (!page) window.scrollTo(0, +(sessionStorage.getItem("mk.homeY") || 0));
    else {
      window.scrollTo(0, 0);
      const h = app.querySelector("h1[tabindex], .said[tabindex]");
      if (h && lastRoute) h.focus({ preventScroll: true });
    }
    lastRoute = key;
    tickTimer();
  }

  /* ---------- events ---------- */
  document.addEventListener("input", (e) => {
    if (e.target.id !== "q") return;
    query = e.target.value;
    document.getElementById("grid").innerHTML = gridHTML();
    const c = document.querySelector("[data-action=clear]"); if (c) c.hidden = !query;
  });
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-action]");
    if (!b) return;
    const act = b.dataset.action;
    const [page, code] = route();
    const r = FULL[code];
    if (act === "kind") { kind = b.dataset.kind; document.querySelector(".kinds").innerHTML = kindsHTML(); document.getElementById("grid").innerHTML = gridHTML(); }
    else if (act === "clear") { query = ""; const q = document.getElementById("q"); q.value = ""; q.focus(); document.getElementById("grid").innerHTML = gridHTML(); b.hidden = true; }
    else if (act === "back") location.hash = "#/";
    else if (act === "play") { playing = code; render(true); }
    else if (act === "tick") {
      const t = ticked(code), k = b.dataset.k;
      if (t.has(k)) t.delete(k); else t.add(k);
      saveTicks(code, t);
      b.classList.toggle("done", t.has(k)); b.setAttribute("aria-pressed", t.has(k));
    }
    else if (act === "read" && r) {
      const l = lab(r);
      const ings = r.ingredient_groups.flatMap((g) => g.items.map((i) => [i.amount, i.item].filter(Boolean).join(" ")));
      speak([r.title + ".", l.ing + ".", ...ings, l.steps + ".", ...r.steps.map((s) => s.text)], "r:" + code, r.lang, () => render(true));
      render(true);
    }
    else if (act === "read-step" && r) { const s = r.steps[+b.dataset.i]; if (s) { speaking = null; speak([s.text], "s:" + code, r.lang); } }
    else if (act === "awake") { const on = !store.get("awake", true); store.set("awake", on); setWake(on); b.setAttribute("aria-checked", on); }
    else if (act === "timer" && r) startTimer(+b.dataset.min, code, r.title);
    else if (act === "timer-stop") stopTimer();
    else if (act === "sheet" && r) openSheet(r);
  });
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, .sheet")) return;
    const [page, code, n] = route();
    if (page !== "cook" || n === "done") return;
    const k = parseInt(n, 10) || 1;
    const rtl = FULL[code] && FULL[code].lang === "he";
    const fwd = rtl ? "ArrowLeft" : "ArrowRight", bwd = rtl ? "ArrowRight" : "ArrowLeft";
    if (e.key === fwd || e.key === " ") { e.preventDefault(); location.hash = `#/cook/${code}/${k + 1}`; }
    if (e.key === bwd && k > 1) location.hash = `#/cook/${code}/${k - 1}`;
  });
  window.addEventListener("hashchange", () => render(false));
  window.addEventListener("pageshow", (e) => { if (e.persisted) { LIST = null; render(true); } });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && !route()[0]) loadList().then(() => { const g = document.getElementById("grid"); if (g) { g.innerHTML = gridHTML(); } }).catch(() => {});
  });

  if (timer && timer.end < Date.now() - 3600e3) { timer = null; store.set("timer", null); }
  render(false);
  if (canSpeak) speechSynthesis.getVoices();
})();

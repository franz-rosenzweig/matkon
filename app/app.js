/* Matkon: recipe reels as recipe pages.
   Plain JS. Everything comes from the server and needs an account (api/me, api/recipes, api/r/<code>…).
   Routes:  #/  home  ·  #/r/<code>  a recipe  ·  #/cook/<code>/<n>  cooking  ·  #/history[/<tab>]  ·  #/settings
   Memory (saved, ticks, the cooking step, notes, ratings, what was cooked and opened) lives on the
   server, so every device of an account sees the same. The kitchen timer stays on the device. */
(function () {
  "use strict";

  const app = document.getElementById("app");
  const timerbar = document.getElementById("timerbar");
  let LIST = null, ME = null, SUGGEST = null;
  const FULL = {};
  let query = "";
  let emailPending = null, lastInvite = null;
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
  const day = (t) => new Date(t * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short", year: new Date(t * 1000).getFullYear() === new Date().getFullYear() ? undefined : "numeric" });
  const dayTime = (t) => new Date(t * 1000).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
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
    mark: ico('<path d="M7 4h10v16l-5-3.5L7 20z"/>'),
    markOn: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" aria-hidden="true"><path d="M7 4h10v16l-5-3.5L7 20z"/></svg>',
    history: ico('<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1M3.5 4v4h4"/><path d="M12 8v4.5l3 1.8"/>'),
    gear: ico('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>'),
    done: ico('<circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.8 2.8L16.5 9.5"/>'),
    trash: ico('<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>'),
  };

  /* Labels on a recipe page follow the recipe's language. */
  const L = {
    en: { ing: "Ingredients", steps: "Steps", tips: "Tips", nut: "Nutrition", miss: "Not in the reel", serves: "Serves", makes: "Makes",
      prep: "Prep", cook: "Cook", total: "Total", oven: "Oven", start: "Start cooking", cont: (n) => `Continue · step ${n}`,
      watch: "Watch the reel", page: "Recipe page", read: "Read aloud", stopRead: "Stop", awake: "Keep the screen on",
      step: (k, n) => `Step ${k} of ${n}`, next: "Next", backStep: "Back", done: "Done", finished: "Made it", again: "Start again",
      toRecipe: "Back to the recipe", uses: "Uses", timer: (m) => `Timer ${fmtMin(m)}`, noAmt: "no amount", calories: "Calories",
      protein: "Protein", carbs: "Carbs", fat: "Fat", close: "Close", notRecipe: "Not a recipe", mine: "Mine", rating: "Rating",
      notes: "Notes", madeIt: "I made it", made: (n, d) => `Made ${n === 1 ? "once" : n + " times"} · ${d}`, addedBy: (n) => `Added by ${n}` },
    he: { ing: "מצרכים", steps: "אופן ההכנה", tips: "טיפים", nut: "ערכים תזונתיים", miss: "חסר בסרטון", serves: "מנות", makes: "כמות",
      prep: "הכנה", cook: "בישול", total: "סה״כ", oven: "תנור", start: "מתחילים לבשל", cont: (n) => `ממשיכים · שלב ${n}`,
      watch: "לצפייה בסרטון", page: "דף המתכון", read: "הקראה", stopRead: "עצירה", awake: "המסך נשאר דולק",
      step: (k, n) => `שלב ${k} מתוך ${n}`, next: "הבא", backStep: "הקודם", done: "סיימתי", finished: "בתיאבון", again: "מההתחלה",
      toRecipe: "חזרה למתכון", uses: "צריך", timer: (m) => `טיימר ${m} דק׳`, noAmt: "בלי כמות", calories: "קלוריות", protein: "חלבון",
      carbs: "פחמימות", fat: "שומן", close: "סגירה", notRecipe: "לא מתכון", mine: "שלי", rating: "דירוג", notes: "הערות",
      madeIt: "הכנתי", made: (n, d) => `הוכן ${n === 1 ? "פעם אחת" : n + " פעמים"} · ${d}`, addedBy: (n) => `נוסף על ידי ${n}` },
  };
  const lab = (r) => L[r && r.lang === "he" ? "he" : "en"];
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
  async function loadAll(force) {
    if (!ME || force) ME = await getJSON("api/me");
    if (!LIST || force) LIST = await getJSON("api/recipes");
  }
  async function loadOne(code) {
    if (!FULL[code]) FULL[code] = await getJSON("api/r/" + encodeURIComponent(code));
    return FULL[code];
  }
  const M = () => ME.memory;
  const nameOf = (id) => (ME.names && ME.names[id]) || id;
  const isOwner = () => ME.account && ME.account.admin;

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
    return `<header class="top"><a class="mark" href="#/"><img src="icon.svg" alt=""><h1>${esc(title || "Matkon")}</h1></a>
      <nav class="topnav"><a class="btn btn-icon" href="#/history" aria-label="History">${I.history}</a><a class="btn btn-icon" href="#/settings" aria-label="Settings">${I.gear}</a></nav></header>`;
  }

  /* ---------- home ---------- */
  const recipesOnly = () => LIST.recipes.filter((r) => r.is_recipe !== false);
  const byCode = (c) => LIST.recipes.find((r) => r.code === c);
  function haystack(r) { return norm([r.title, r.user, r.cuisine, r.kind, nameOf(r.added_by), (r.tags || []).join(" "), (r.items || []).join(" ")].join(" ")); }
  function visible() {
    const words = norm(query).split(" ").filter(Boolean);
    return recipesOnly()
      .filter((r) => kind === "All" || (kind === "Saved" ? M().saved[r.code] : kind === "Made" ? M().cooked_count[r.code] : r.kind === kind))
      .filter((r) => words.every((w) => haystack(r).includes(w)));
  }
  function cardHTML(r) {
    const saved = M().saved[r.code], made = M().cooked_count[r.code], rating = M().ratings[r.code];
    return `<li><a class="card" href="#/r/${esc(r.code)}">
      <div class="pic">${r.photo ? `<img src="${esc(r.photo)}" alt="" loading="lazy">` : ""}${r.complete ? "" : `<span class="flag">${r.lang === "he" ? "חסרות כמויות" : "Missing amounts"}</span>`}
        ${saved || made || rating ? `<span class="marks">${saved ? `<span>${I.markOn}</span>` : ""}${made ? `<span>${I.done}</span>` : ""}${rating ? `<span class="r">${rating}</span>` : ""}</span>` : ""}</div>
      <div class="txt"${dirOf(r)}><div class="t">${esc(r.title)}</div><div class="by" dir="ltr">@${esc(r.user)}</div></div></a></li>`;
  }
  function gridHTML() {
    const list = visible();
    return list.length ? `<ul class="grid">${list.map(cardHTML).join("")}</ul>` : `<p class="empty">No recipes</p>`;
  }
  function kindsHTML() {
    const recipes = recipesOnly();
    const counts = {};
    recipes.forEach((r) => { counts[r.kind] = (counts[r.kind] || 0) + 1; });
    const order = ["Breakfast", "Mains", "Salads & sides", "Soups", "Bread & dough", "Baking & sweets", "Snacks", "Sauces & dips", "Drinks"];
    const saved = recipes.filter((r) => M().saved[r.code]).length, made = recipes.filter((r) => M().cooked_count[r.code]).length;
    const kinds = [["All", recipes.length]].concat(saved ? [["Saved", saved]] : [], made ? [["Made", made]] : [], order.filter((k) => counts[k]).map((k) => [k, counts[k]]));
    return kinds.map(([k, n]) => `<button type="button" data-action="kind" data-kind="${esc(k)}" aria-pressed="${k === kind}">${esc(k)}<span class="n">${n}</span></button>`).join("");
  }
  function nextHTML() {
    if (!SUGGEST || !SUGGEST.length || query || kind !== "All") return "";
    const items = SUGGEST.map((s) => [s, byCode(s.code)]).filter(([, r]) => r);
    if (!items.length) return "";
    return `<section class="next" aria-label="Up next"><h2>Up next</h2><ul class="next-row">${items.map(([s, r]) => `<li><a class="mini" href="#/r/${esc(r.code)}">
      <span class="pic">${r.photo ? `<img src="${esc(r.photo)}" alt="" loading="lazy">` : ""}</span>
      <span class="why">${esc((WHY[s.why] || WHY.new)(s.about))}</span><span class="t"${dirOf(r)}>${esc(r.title)}</span></a></li>`).join("")}</ul></section>`;
  }
  function home() {
    const notes = [];
    if (ME.instagram && ME.instagram.signed_out) notes.push(`<a class="note-bar" href="#/settings">Instagram sign-in lapsed</a>`);
    if (LIST.waiting) notes.push(`<div class="note-bar">${LIST.waiting} more on the way</div>`);
    return `<div class="wrap">
      ${topBar()}
      <div class="search" role="search">${I.search}<input id="q" type="search" placeholder="Search" value="${esc(query)}" autocomplete="off" enterkeyhint="search" aria-label="Search">
        <button type="button" class="clear" data-action="clear" aria-label="Clear"${query ? "" : " hidden"}>${I.x}</button></div>
      <nav class="kinds" aria-label="Kinds">${kindsHTML()}</nav>
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
    if (r.oven) c.push(`<span class="chip">${I.oven}${esc(l.oven)} ${esc(r.oven)}</span>`);
    return c.length ? `<div class="chips facts">${c.join("")}</div>` : "";
  }
  function ingHTML(i, key, done, l) {
    const what = `${i.amount ? `<span class="amt">${esc(i.amount)}</span> ` : ""}${esc(i.item)}${i.note ? `<span class="nt">, ${esc(i.note)}</span>` : ""}`;
    return `<li><button type="button" class="ing${done ? " done" : ""}" data-action="tick" data-k="${key}" aria-pressed="${done}">
      <span class="box">${I.check}</span><span class="what">${what}${i.amount ? "" : ` <span class="none">· ${esc(l.noAmt)}</span>`}</span></button></li>`;
  }
  function ingredientsHTML(r, l) {
    const t = ticked(r.code);
    return r.ingredient_groups.map((g, gi) => `${g.name ? `<h3>${esc(g.name)}</h3>` : ""}<ul class="ings">${g.items.map((i, ii) => ingHTML(i, gi + "." + ii, t.has(gi + "." + ii), l)).join("")}</ul>`).join("");
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
  function mineHTML(r, l) {
    const n = M().cooked_count[r.code], last = M().cooked_last[r.code];
    return `<section class="sec mine"><h2>${esc(l.mine)}</h2>
      <div class="made"><button type="button" class="btn" data-action="made">${I.done}${esc(l.madeIt)}</button>${n ? `<span class="sub">${esc(l.made(n, day(last)))}</span>` : ""}</div>
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
        ${canSpeak && steps.length ? `<button type="button" class="btn" data-action="read" aria-pressed="${reading}">${reading ? I.stop + esc(l.stopRead) : I.speak + esc(l.read)}</button>` : ""}
        <button type="button" class="btn btn-icon save${saved ? " on" : ""}" data-action="save" aria-pressed="${saved}" aria-label="Save">${saved ? I.markOn : I.mark}</button></div>
      <article class="recipe">
        <div>${mediaHTML(r, l, playing === r.code)}
          ${"wakeLock" in navigator ? `<button type="button" class="switch" role="switch" aria-checked="${awake}" data-action="awake"><span>${esc(l.awake)}</span><span class="track"><span class="knob"></span></span></button>` : ""}</div>
        <div>
          <header class="head">
            <h1 tabindex="-1">${esc(r.title)}</h1>
            ${r.summary ? `<p class="sum">${esc(r.summary)}</p>` : ""}
            <div class="by" dir="ltr"><a href="${esc(r.reel)}" target="_blank" rel="noopener">@${esc(r.user)}</a>${r.link ? `<a href="${esc(r.link)}" target="_blank" rel="noopener">${esc(l.page)}</a>` : ""}${others && r.added_by ? `<span>${esc(l.addedBy(nameOf(r.added_by)))}</span>` : ""}</div>
            ${factsHTML(r, l)}
          </header>
          ${r.is_recipe === false ? `<p class="empty">${esc(l.notRecipe)}</p>` : `
          ${steps.length ? `<div class="actions"><a class="btn btn-accent btn-big" href="#/cook/${esc(r.code)}/${at || 1}">${I.cook}${esc(at ? l.cont(at) : l.start)}</a></div>` : ""}
          <div class="two">
            ${r.ingredient_groups.length ? `<section class="sec"><h2>${esc(l.ing)}</h2>${ingredientsHTML(r, l)}</section>` : ""}
            ${steps.length ? `<section class="sec"><h2>${esc(l.steps)}</h2><ol class="steps">${steps.map((s, i) => `<li><div class="step"><span class="n">${i + 1}</span><div>${esc(s.text)}${timerChips(r, s, l)}</div></div></li>`).join("")}</ol></section>` : ""}
          </div>
          ${r.tips && r.tips.length ? `<section class="sec"><h2>${esc(l.tips)}</h2><ul class="list">${r.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></section>` : ""}
          ${nutritionHTML(r, l)}
          ${r.missing && r.missing.length ? `<section class="sec miss"><h2>${esc(l.miss)}</h2><ul class="list">${r.missing.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></section>` : ""}
          ${mineHTML(r, l)}`}
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
        <p class="said" tabindex="-1">${esc(s.text)}</p>
        ${uses.length ? `<div class="uses"><span class="lbl">${esc(l.uses)}</span><ul>${uses.map((i) => `<li><b>${esc(i.amount)}</b> ${esc(i.item)}</li>`).join("")}</ul></div>` : ""}
        <div class="tools">${timerChips(r, s, l).replace(/class="chip"/g, 'class="btn"').replace('<div class="chips">', "").replace(/<\/div>$/, "")}
          ${canSpeak ? `<button type="button" class="btn" data-action="read-step" data-i="${k - 1}">${I.speak}${esc(l.read)}</button>` : ""}</div>
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
      <span class="t"${dirOf(r)}>${esc(r.title)}</span>${right || ""}</a></li>`;
  }
  async function historyPage(tab) {
    const h = await getJSON("api/history");
    tab = tab || "cooked";
    const tabs = [["cooked", "Cooked"], ["viewed", "Viewed"], ["imported", "Imported"]];
    let body = "";
    if (tab === "cooked") {
      const rows = h.cooked.map((e) => [e, byCode(e.code)]).filter(([, r]) => r);
      body = rows.length ? `<ul class="hlist">${rows.map(([e, r]) => rowHTML(r, `<span class="when">${esc(day(e.at))}</span>`).replace("</a></li>", `</a><button type="button" class="btn btn-icon del" data-action="uncook" data-id="${esc(e.id)}" aria-label="Remove">${I.trash}</button></li>`)).join("")}</ul>` : `<p class="empty">Nothing yet</p>`;
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

  /* ---------- settings ---------- */
  function field(name, label, value, type, extra) {
    return `<label class="field"><span>${esc(label)}</span><input name="${name}" type="${type || "text"}" value="${esc(value == null ? "" : value)}" ${extra || ""}></label>`;
  }
  async function settingsPage() {
    const s = await getJSON("api/settings");
    const ig = s.instagram;
    const scan = ig.scan || {};
    const status = !ig.connected ? "Not connected" : ig.signed_out ? "Sign-in lapsed" : ig.shared ? "Connected · shared sign-in" : "Connected";
    const cols = scan.collections ? `<ul class="cols">${scan.collections.map((c) => `<li><button type="button" class="col${String(c.id) === String(ig.collection_id) ? " on" : ""}" data-action="pick-col" data-id="${esc(c.id)}">
        <span class="t">${esc(c.count)} saved</span>${c.captions.map((t) => `<span class="cap">${esc(t)}</span>`).join("")}</button></li>`).join("")}</ul>` : "";
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
        <button type="button" class="switch" role="switch" aria-checked="${s.settings.nutrition}" data-action="nutrition"><span>Calories and protein</span><span class="track"><span class="knob"></span></span></button></section>
      <section class="sec set"><h2>Instagram</h2>
        <p class="status">${esc(status)}${ig.collection_id ? ` · ${esc(ig.collection_name || "Collection " + ig.collection_id)}` : ""}</p>
        ${ig.connected ? `<div class="row"><button type="button" class="btn" data-action="scan"${scan.running ? " disabled" : ""}>${scan.running ? "Looking…" : "Find my collections"}</button>${ig.shared ? "" : `<button type="button" class="btn" data-action="disconnect">Disconnect</button>`}</div>` : ""}
        ${scan.error ? `<p class="err">Instagram sign-in lapsed</p>` : ""}${cols}
        <form data-form="cookies" class="stack"><h3>${ig.connected && !ig.shared ? "New sign-in" : "Connect"}</h3>
          <label class="field"><span>cookies.txt</span><input type="file" name="file" accept=".txt,.json,text/plain,application/json"></label>
          <label class="field"><span>Or paste it</span><textarea name="text" rows="3" spellcheck="false"></textarea></label>
          <button class="btn" type="submit">Connect</button></form></section>
      <section class="sec set"><h2>Add a reel</h2>
        <form data-form="add" class="row">${field("url", "Reel link", "", "url")}<button class="btn" type="submit">Add</button></form></section>
      ${k ? `<section class="sec set"><h2>Kitchen</h2>
        <div class="row"><button type="button" class="btn" data-action="sync">Check now</button></div>
        <form data-form="kitchen" class="stack">
          ${field("scan_pages", "Pages each hour", k.scan_pages, "number", 'min="1" max="50"')}
          ${field("full_every_hours", "Every save, every (hours)", k.full_every_hours, "number", 'min="0" max="10000"')}
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
    if (page === "join") { signInPage("", "join", { email: code || "", code: n || "" }); lastRoute = key; return; }
    try {
      await loadAll();
      if (page === "r" || page === "cook") r = await loadOne(code);
      if (!page && !SUGGEST) getJSON("api/suggest").then((d) => { SUGGEST = d.suggest; const el = document.getElementById("next"); if (el) el.innerHTML = nextHTML(); }).catch(() => {});
      if (page === "r") html = recipePage(r);
      else if (page === "cook") html = cookPage(r, n === "done" ? "done" : parseInt(n, 10) || 1);
      else if (page === "history") html = await historyPage(code);
      else if (page === "settings") html = await settingsPage();
      else html = home();
    } catch (e) {
      if (e instanceof SignedOut) { signInPage(); return; }
      app.innerHTML = `<div class="wrap"><header class="top"><a class="mark" href="#/"><img src="icon.svg" alt=""><h1>Matkon</h1></a></header><p class="empty">Can't reach Matkon</p><p style="text-align:center"><button class="btn" type="button" onclick="location.reload()">Try again</button></p></div>`;
      return;
    }
    const y = window.scrollY;
    app.innerHTML = html;
    document.title = r ? `${r.title} · Matkon` : page === "history" ? "History · Matkon" : page === "settings" ? "Settings · Matkon" : "Matkon";
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
    const r = FULL[code];
    if (act === "kind") { kind = b.dataset.kind; document.querySelector(".kinds").innerHTML = kindsHTML(); document.getElementById("grid").innerHTML = gridHTML(); document.getElementById("next").innerHTML = nextHTML(); }
    else if (act === "clear") { query = ""; const q = document.getElementById("q"); q.value = ""; q.focus(); document.getElementById("grid").innerHTML = gridHTML(); document.getElementById("next").innerHTML = nextHTML(); b.hidden = true; }
    else if (act === "play") { playing = code; render(true); }
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
    else if (act === "made") { await remember("cooked", { code }); render(true); }
    else if (act === "finish") { await remember("cooked", { code }); location.hash = `#/cook/${code}/done`; }
    else if (act === "uncook") { await remember("uncook", { id: b.dataset.id }); render(true); }
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
    else if (act === "signout") { await post("api/signout").catch(() => {}); signInPage(); }
    else if (act === "nutrition") { const on = b.getAttribute("aria-checked") !== "true"; if (await setting("nutrition", { value: on })) { b.setAttribute("aria-checked", on); Object.keys(FULL).forEach((c) => delete FULL[c]); } }
    else if (act === "scan") { if (await setting("instagram-scan", {})) { render(true); pollScan(); } }
    else if (act === "disconnect") { if (await setting("instagram-disconnect", {})) { ME = null; render(true); } }
    else if (act === "pick-col") { if (await setting("instagram-collection", { id: b.dataset.id, name: "Recipes" }, "Saved")) render(true); }
    else if (act === "sync") setting("sync", {}, "Checking");
    else if (act === "mode") signInPage("", b.dataset.mode);
    else if (act === "invite-cancel") { if (await setting("invite-cancel", { email: b.dataset.email }, "Invite cancelled")) render(true); }
    else if (act === "email-set") {
      const c = document.querySelector("form[data-form=email] input[name=code]");
      if (await setting("email-set", { email: emailPending, code: c ? c.value : "" }, "Email saved")) { emailPending = null; ME = null; render(true); }
    }
    else if (act === "to-password") { const p = document.getElementById("password"); p.scrollIntoView({ behavior: "smooth", block: "center" }); p.querySelector("input").focus({ preventScroll: true }); }
    else if (act === "remove-account") { if (confirm("Remove this account?") && await setting("account-remove", { id: b.dataset.id })) { ME = null; render(true); } }
  });
  function pollScan() {
    const t = setInterval(async () => {
      if (route()[0] !== "settings") { clearInterval(t); return; }
      const s = await getJSON("api/settings").catch(() => null);
      if (s && !(s.instagram.scan || {}).running) { clearInterval(t); render(true); }
    }, 5000);
  }
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
    if (kindOf === "name") { if (await setting("name", { name: v.name }, "Saved")) ME = null; }
    else if (kindOf === "password") { if (await setting("password", { old: v.old, new: v.new }, "Password changed")) f.reset(); }
    else if (kindOf === "cookies") {
      let text = v.text || "";
      const file = f.querySelector("input[type=file]").files[0];
      if (file) text = await file.text();
      if (await setting("instagram-cookies", { text }, "Connected")) { ME = null; render(true); }
    }
    else if (kindOf === "add") { if (await setting("add-reel", { url: v.url }, "Added. It's on the way.")) f.reset(); }
    else if (kindOf === "kitchen") setting("kitchen", v, "Saved");
    else if (kindOf === "account") { if (await setting("account-add", v, "Account added")) { ME = null; render(true); } }
    else if (kindOf === "reset") { if (await setting("account-password", { id: f.dataset.id, password: v.password }, "Password set")) f.reset(); }
  });
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, .sheet")) return;
    const [page, code, n] = route();
    if (page !== "cook" || n === "done") return;
    const k = parseInt(n, 10) || 1;
    const r = FULL[code];
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
      ME = me; LIST = list; SUGGEST = null;
      const page = route()[0];
      if (!page || page === "r") render(true);
    }).catch(() => {});
  });

  if (timer && timer.end < Date.now() - 3600e3) { timer = null; store.set("timer", null); }
  render(false);
  if (canSpeak) speechSynthesis.getVoices();
})();

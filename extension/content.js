/* Matkon on instagram.com: the only part of Matkon that talks to Instagram.

   It runs in your own browser, signed in as you, and asks Instagram only what its own website asks
   while you use it: your newest saves, a page or two, every few hours, a little while after you open
   Instagram and only while the tab is in front of you. The reels in your recipe collection that Matkon
   doesn't have yet go to Matkon (through background.js): the post, then its video, a few an hour at
   most. Your Instagram sign-in never leaves the browser.

   On your recipe collection's own page it also picks up what you scroll past, for saves older than
   the newest pages. */
(() => {
  if (globalThis.__matkonOn) return;
  globalThis.__matkonOn = true;
  const P = globalThis.browser || globalThis.chrome;
  const T = globalThis.__matkonTest || {};          // extension/test.mjs: no waiting
  const APP_ID = '936619743392459';                   // the website's own app id, which its requests send
  // Firefox gives content scripts the page's own fetch (content.fetch): the request is the page's in every way.
  const pageFetch = (typeof content !== 'undefined' && content && content.fetch) ? content.fetch.bind(content) : fetch.bind(globalThis);
  const wait = (lo, hi) => new Promise(r => setTimeout(r, T.fast ? 0 : (lo + Math.random() * (hi - lo)) * 1000));
  const ask = async msg => {
    const r = await P.runtime.sendMessage(msg);
    if (r && r.error) throw new Error(r.error);
    return r || {};
  };

  class Stop extends Error {}                         // Instagram said no: signed-out, busy, gone, instagram

  let S = null;                                       // what Matkon said: collection, paused, pages, wanted
  const queue = new Map();                            // code → the post, or null: ask Instagram for it
  const sent = new Set();
  let checking = false, bringing = false;

  function cookie(name) {
    const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : '';
  }

  async function ig(path) {
    let claim = '0';
    try { claim = sessionStorage.getItem('www-claim-v2') || '0'; } catch (e) { /* none */ }
    const r = await pageFetch(location.origin + path, {
      credentials: 'include',
      headers: { 'X-IG-App-ID': APP_ID, 'X-IG-WWW-Claim': claim, 'X-CSRFToken': cookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest', Accept: '*/*' }
    });
    if (r.status === 401 || r.status === 403 || (r.redirected && /\/accounts\/login|\/challenge/.test(r.url))) throw new Stop('signed-out');
    if (r.status === 429) throw new Stop('busy');
    if (r.status === 404 || r.status === 400) throw new Stop('gone');
    if (!r.ok) throw new Stop('instagram');
    try { return await r.json(); } catch (e) { throw new Stop('signed-out'); }     // a page instead of data: the sign-in page
  }

  const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
  function pkOf(code) {                               // a reel's code is its number in base 64
    const s = code.length > 28 ? code.slice(0, -28) : code;
    let n = 0n;
    for (const ch of s) {
      const i = ALPHABET.indexOf(ch);
      if (i < 0) return null;
      n = n * 64n + BigInt(i);
    }
    return n.toString();
  }

  function trim(m) {                                  // all Matkon gets of a post
    return {
      code: m.code, pk: String(m.pk || ''), media_type: m.media_type, product_type: m.product_type || '',
      user: { username: (m.user || {}).username || '', full_name: (m.user || {}).full_name || '' },
      caption: { text: (m.caption || {}).text || '' }, taken_at: m.taken_at, video_duration: m.video_duration
    };
  }

  function videoOf(m) {                               // the biggest one up to 1080 wide
    const v = (m.video_versions || []).filter(x => x && x.url).sort((a, b) => (b.width || 0) - (a.width || 0));
    const pick = v.find(x => (x.width || 0) <= 1080) || v[v.length - 1];
    return pick ? pick.url : null;
  }

  const inCollection = m => (m.saved_collection_ids || []).map(String).includes(String(S.collection_id));

  function collectionHere() {
    const m = location.pathname.match(/^\/[^/]+\/saved\/([^/]+)\/(\d{5,30})\/?$/);
    if (!m) return null;
    let name = m[1];
    try { name = decodeURIComponent(name); } catch (e) { /* as is */ }
    name = name.replace(/[-_]+/g, ' ').trim();
    return { id: m[2], name: name.charAt(0).toUpperCase() + name.slice(1) };
  }

  function reelHere() {
    const m = location.pathname.match(/^\/(?:[\w.]+\/)?(?:reels?|p|tv)\/([\w-]{5,40})\/?$/);
    return m ? m[1] : null;
  }

  // ---- looking ----

  async function hello() {
    S = await ask({ type: 'hello' });
    if (S.connected && !S.paused) for (const c of S.wanted || []) if (!queue.has(c) && !sent.has(c)) queue.set(c, null);
    return S;
  }

  async function check() {
    if (checking || !S || !S.connected || S.paused || !S.collection_id) return { found: 0 };
    checking = true;
    let error = null, found = 0;
    try {
      let maxId = null;
      const pages = Math.max(1, Math.min(5, S.pages || 2));
      for (let n = 0; n < pages; n++) {
        if (n) await wait(4, 9);
        const d = await ig('/api/v1/feed/saved/posts/' + (maxId ? '?max_id=' + encodeURIComponent(maxId) : ''));
        const mine = (d.items || []).map(x => x && x.media).filter(m => m && m.code && inCollection(m));
        let known = [];
        if (mine.length) {
          const r = await ask({ type: 'seen', codes: mine.map(m => m.code) });
          known = r.known || [];
          for (const m of mine) {
            if ((r.want || []).includes(m.code) && !sent.has(m.code)) { queue.set(m.code, m); found++; }
          }
        }
        if (known.length || !d.more_available || !d.next_max_id) break;   // what's further down is older and in already
        maxId = d.next_max_id;
      }
    } catch (e) {
      error = e instanceof Stop ? e.message : 'matkon';
    } finally {
      checking = false;
    }
    await ask({ type: 'checked', error }).catch(() => {});
    if (!error) bring();
    return { found, error };
  }

  async function bring() {
    if (bringing) return;
    bringing = true;
    try {
      while (queue.size && S && !S.paused) {
        if (!(await ask({ type: 'allowance' })).left) break;                // a few an hour, at most
        const [code, listed] = queue.entries().next().value;
        queue.delete(code);
        sent.add(code);
        try {
          let m = listed;
          if (!m) {
            await wait(3, 8);
            const pk = pkOf(code);
            m = pk ? ((await ig('/api/v1/media/' + pk + '/info/')).items || [])[0] : null;
          }
          if (!m || !m.code) { await ask({ type: 'post', media: { code }, error: 'not on Instagram' }); continue; }
          if (m.media_type !== 2) { await ask({ type: 'post', media: trim(m) }); continue; }   // Matkon notes it isn't a video
          const url = videoOf(m);
          if (!url) { await ask({ type: 'post', media: trim(m), error: 'no video' }); continue; }
          const r = await P.runtime.sendMessage({ type: 'take', media: trim(m), video: url });
          if (r && r.error === 'later') { queue.set(code, m); sent.delete(code); break; }
          if (r && r.error) throw new Error(r.error);
        } catch (e) {
          if (e instanceof Stop && e.message === 'gone') { await ask({ type: 'post', media: { code }, error: 'not on Instagram' }).catch(() => {}); continue; }
          await ask({ type: 'checked', error: e instanceof Stop ? e.message : 'matkon', quiet: true }).catch(() => {});
          sent.delete(code);
          break;
        }
        if (queue.size) await wait(12, 30);
      }
    } finally {
      bringing = false;
    }
  }

  async function harvest() {                         // the recipe collection's own page: what's on screen
    const c = collectionHere();
    if (!c || !S || !S.connected || S.paused || c.id !== String(S.collection_id)) return;
    const codes = [...document.querySelectorAll('a[href*="/reel/"], a[href*="/p/"]')]
      .map(a => (a.getAttribute('href').match(/\/(?:reels?|p)\/([\w-]{5,40})/) || [])[1])
      .filter(x => x && !sent.has(x) && !queue.has(x) && !harvest.seen.has(x));
    if (!codes.length) return;
    codes.forEach(x => harvest.seen.add(x));
    const r = await ask({ type: 'seen', codes: [...new Set(codes)].slice(0, 100) });
    for (const x of r.want || []) if (!queue.has(x) && !sent.has(x)) queue.set(x, null);
    bring();
  }
  harvest.seen = new Set();

  // ---- when ----

  const visible = () => document.visibilityState === 'visible';
  async function maybe() {
    if (!visible()) return;
    try { await hello(); } catch (e) { return; }
    if (!S.connected || S.paused) return;
    if (S.due) await check();
    else bring();
  }

  P.runtime.onMessage.addListener((msg, sender, send) => {
    const reply = v => { send(v); };
    if (!msg) return false;
    if (msg.type === 'page') {
      reply({ reel: reelHere(), collection: collectionHere(), current: S && S.collection_id ? String(S.collection_id) : null, busy: checking || bringing, waiting: queue.size });
      return false;
    }
    (async () => {
      try {
        await hello();
        if (!S.connected) return reply({ error: 'not connected' });
        if (S.paused) return reply({ error: 'paused' });
        if (msg.type === 'check-now') { check(); return reply({ ok: true }); }
        if (msg.type === 'send-this') {
          const code = reelHere();
          if (!code) return reply({ error: 'no reel' });
          const r = await ask({ type: 'seen', codes: [code], force: true });
          if (!(r.want || []).includes(code)) return reply({ ok: true, had: true });
          queue.set(code, null);
          sent.delete(code);
          bring();
          return reply({ ok: true });
        }
        if (msg.type === 'use-collection') {
          const c = collectionHere();
          if (!c) return reply({ error: 'no collection' });
          await ask({ type: 'collection', id: c.id, name: c.name });
          await hello();
          harvest();
          return reply({ ok: true });
        }
        reply({ error: 'unknown' });
      } catch (e) {
        reply({ error: String(e.message || e) });
      }
    })();
    return true;
  });

  if (T.manual) { globalThis.__matkon = { check, bring, harvest, hello, queue, pkOf }; return; }
  // A little while after Instagram opens, like a person would, then every half hour while it stays open.
  setTimeout(maybe, (20 + Math.random() * 40) * 1000);
  setInterval(maybe, 30 * 60 * 1000);
  document.addEventListener('visibilitychange', () => { if (visible() && S && S.due && !checking) setTimeout(maybe, (5 + Math.random() * 20) * 1000); });
  setInterval(() => { if (visible() && collectionHere()) harvest().catch(() => {}); }, 5000);
})();

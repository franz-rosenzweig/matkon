/* The extension's go-between: content.js (on instagram.com) hands it what to send, and this talks to
   your Matkon with the key from Matkon's Settings, and fetches each reel's video file from Instagram's
   video servers (the same file the page plays; no sign-in goes with it). */
const P = globalThis.browser || globalThis.chrome;
const VERSION = P.runtime.getManifest().version;

const conf = () => P.storage.local.get({ url: '', key: '', lastCheck: 0, brought: [], lastError: null, name: '', state: null });

async function matkon(path, body, method) {
  const c = await conf();
  if (!c.url || !c.key) throw new Error('not connected');
  const video = typeof Blob !== 'undefined' && body instanceof Blob;
  let r;
  try {
    r = await fetch(c.url + path, {
      method: method || 'POST', credentials: 'omit', cache: 'no-store',
      headers: { 'X-Matkon': '1', 'X-Matkon-Key': c.key, 'Content-Type': video ? 'video/mp4' : 'application/json' },
      body: video ? body : JSON.stringify(body || {})
    });
  } catch (e) {
    throw new Error('Matkon didn’t answer');
  }
  let d = {};
  try { d = await r.json(); } catch (e) { /* no JSON */ }
  if (!r.ok) throw new Error(d.error || 'Matkon answered ' + r.status);
  return d;
}

const lastHour = list => (list || []).filter(t => t > Date.now() - 3600e3);

async function hello(extra) {
  const c = await conf();
  if (!c.url || !c.key) return { connected: false };
  extra = extra || {};
  const d = await matkon('/api/ext/hello', { version: VERSION, error: 'error' in extra ? extra.error : c.lastError, checked: !!extra.checked });
  const lastCheck = extra.checked ? Date.now() : c.lastCheck;
  await P.storage.local.set({ name: d.name, state: d, lastCheck, lastError: 'error' in extra ? extra.error : c.lastError });
  return { connected: true, ...d, lastCheck, due: !!d.collection_id && !d.paused && Date.now() - lastCheck > (d.check_hours || 6) * 3600e3 };
}

const handlers = {
  hello: () => hello(),
  test: () => hello(),
  // a check is over (error: what Instagram said, if it said no); quiet: only the error, it wasn't a check
  checked: m => (m.quiet ? hello({ error: m.error || null }) : hello({ checked: true, error: m.error || null })),
  seen: m => matkon('/api/ext/seen', { codes: m.codes || [] }),
  allowance: async () => {
    const c = await conf();
    return { left: Math.max(0, ((c.state || {}).per_hour || 4) - lastHour(c.brought).length) };
  },
  post: m => matkon('/api/ext/post', { media: m.media, error: m.error || null }),
  take: async m => {
    const c = await conf();
    const brought = lastHour(c.brought);
    if (brought.length >= ((c.state || {}).per_hour || 4)) return { error: 'later' };
    const p = await matkon('/api/ext/post', { media: m.media });
    if (!p.video) return { ok: true, had: true };
    let v;
    try { v = await fetch(m.video, { credentials: 'omit' }); } catch (e) { throw new Error('the video didn’t come'); }
    if (!v.ok) throw new Error('the video didn’t come (' + v.status + ')');
    const blob = await v.blob();
    await P.storage.local.set({ brought: [...brought, Date.now()] });
    await matkon('/api/ext/video/' + encodeURIComponent(m.media.code), blob, 'PUT');
    return { ok: true };
  },
  collection: m => matkon('/api/ext/collection', { id: m.id, name: m.name }),
  status: async () => {
    const c = await conf();
    const s = c.state || {};
    return { connected: !!(c.url && c.key), url: c.url, name: c.name, lastCheck: c.lastCheck, lastError: c.lastError,
             paused: !!s.paused, collection: s.collection_name || '', collectionId: s.collection_id || null };
  }
};

P.runtime.onMessage.addListener((msg, sender, send) => {
  const h = handlers[msg && msg.type];
  if (!h) return false;
  Promise.resolve().then(() => h(msg, sender)).then(v => send(v || {}), e => send({ error: String((e && e.message) || e) }));
  return true;
});

if (globalThis.__matkonTest) globalThis.__matkonBackground = { handlers, hello };

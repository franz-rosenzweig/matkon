// The extension against a pretend Instagram and a real Matkon (a throwaway one, on a test port).
//
//   node extension/test.mjs
//
// It runs the real content.js and background.js, each in its own sandbox with the bits of the browser
// they use, starts Matkon with an empty state folder, and serves the pretend Instagram's API and video
// files itself. Nothing here talks to the real Instagram. Needs python3 and ffmpeg.
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const ROOT = path.dirname(HERE);
const PORT = 8531, CDN = 8532, COLL = '123456789';
let failures = 0;
const ok = (cond, what) => { console.log((cond ? '  ok   ' : '  FAIL ') + what); if (!cond) failures++; };

// ---- a throwaway Matkon ----
const state = fs.mkdtempSync(path.join(os.tmpdir(), 'matkon-ext-test-'));
const envFile = path.join(state, 'test.env');
fs.writeFileSync(envFile, [`MATKON_STATE=${state}`, `MATKON_SETTINGS=${state}/settings.json`, `MATKON_PORT=${PORT}`, 'MATKON_HOSTS=127.0.0.1',
  'MATKON_OWNER=tester', 'MATKON_PY=/bin/false'].join('\n') + '\n');       // MATKON_PY=false: a run stops at the transcript, no Claude
const env = { ...process.env, MATKON_ENV: envFile };
const py = code => {
  const r = spawnSync('python3', ['-c', `import sys; sys.path.insert(0, ${JSON.stringify(ROOT)})\n${code}`], { env, encoding: 'utf8' });
  if (r.status) throw new Error(r.stderr);
  return r.stdout.trim();
};
const KEY = py(`from matkon import accounts, kitchen, config
config.STATE.mkdir(parents=True, exist_ok=True); accounts.ensure()
st = config.settings(); st.update(collection_id="${COLL}", collection_name="Recipes", per_hour=4, scan_pages=3); config.save_settings(st)
print(kitchen.new_key("tester"))`);
const server = spawn('python3', ['-I', path.join(ROOT, 'run.py'), 'serve'], { env, stdio: ['ignore', 'pipe', 'pipe'] });
const M = `http://127.0.0.1:${PORT}`;
for (let i = 0; i < 50; i++) { try { await fetch(M + '/'); break; } catch (e) { await new Promise(r => setTimeout(r, 100)); } }

// ---- a pretend Instagram: its API (for content.js) and its video server (for background.js) ----
const video = path.join(state, 'clip.mp4');
spawnSync('ffmpeg', ['-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=size=320x568:rate=24:duration=2', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
  '-shortest', '-pix_fmt', 'yuv420p', '-y', video]);
const cdnHits = [];
const cdn = http.createServer((q, s) => { cdnHits.push(q.url); s.writeHead(200, { 'Content-Type': 'video/mp4' }); s.end(fs.readFileSync(video)); }).listen(CDN);
const media = (code, inColl, type = 2) => ({
  code, pk: '1', media_type: type, product_type: 'clips', taken_at: 1790000000, video_duration: 2,
  user: { username: 'cook.example', full_name: 'A Cook' }, caption: { text: `Recipe ${code} https://example.com/r` },
  saved_collection_ids: inColl ? [COLL] : ['999999999'],
  video_versions: type === 2 ? [{ width: 1440, url: `http://127.0.0.1:${CDN}/big/${code}.mp4` }, { width: 720, url: `http://127.0.0.1:${CDN}/v/${code}.mp4` }] : undefined
});
const igHits = [];
let igMode = 'ok';
const PAGES = {
  '': { items: [media('AAAAAA1', true), media('BBBBBB1', false), media('CCCCCC1', true), media('PHOTO01', true, 1)], more_available: true, next_max_id: 'p2' },
  p2: { items: [media('EEEEEE1', true), media('KNOWN01', true), media('FFFFFF1', true)], more_available: true, next_max_id: 'p3' },
  p3: { items: [media('ZZZZZZ1', true)], more_available: false }
};
async function igFetch(url, opts) {
  const u = new URL(url);
  igHits.push({ path: u.pathname + u.search, headers: opts.headers, credentials: opts.credentials });
  const json = (d, status = 200) => new Response(JSON.stringify(d), { status, headers: { 'Content-Type': 'application/json' } });
  if (igMode === 'signed-out') return json({ message: 'login_required' }, 401);
  if (u.pathname === '/api/v1/feed/saved/posts/') {      // the saved feed's items are {media}
    const p = PAGES[u.searchParams.get('max_id') || ''];
    return json({ ...p, items: p.items.map(m => ({ media: m })) });
  }
  const m = u.pathname.match(/^\/api\/v1\/media\/(\d+)\/info\/$/);
  if (m) {
    const code = { [pk('WANTED1')]: 'WANTED1', [pk('HARVST1')]: 'HARVST1', [pk('ONREEL1')]: 'ONREEL1' }[m[1]];
    return code ? json({ items: [media(code, false)] }) : json({ message: 'not found' }, 404);
  }
  return json({}, 404);
}
const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
function pk(code) { let n = 0n; for (const c of code) n = n * 64n + BigInt(A.indexOf(c)); return n.toString(); }

// ---- the extension, in two sandboxes ----
const store = {};
let bgListener, pageListener;
const bg = vm.createContext({
  console, fetch, Blob, URL, setTimeout, Date, JSON, Promise, Math, __matkonTest: {},
  chrome: {
    runtime: { getManifest: () => ({ version: '0.1.0' }), onMessage: { addListener: f => { bgListener = f; } } },
    storage: { local: { get: async d => Object.fromEntries(Object.entries(d).map(([k, v]) => [k, k in store ? store[k] : v])), set: async o => { Object.assign(store, o); } } }
  }
});
vm.runInContext(fs.readFileSync(path.join(HERE, 'background.js'), 'utf8'), bg, { filename: 'background.js' });
const toBg = msg => new Promise(res => { if (!bgListener(msg, {}, res)) res(undefined); });

let anchors = [];
const page = {
  console, URL, setTimeout, setInterval, Date, JSON, Promise, Math, BigInt, RegExp, Map, Set, Error,
  __matkonTest: { fast: true, manual: true },
  location: { origin: 'https://www.instagram.com', pathname: '/' },
  document: { cookie: 'csrftoken=tok123; other=1', visibilityState: 'visible', addEventListener() {}, querySelectorAll: () => anchors.map(h => ({ getAttribute: () => h })) },
  sessionStorage: { getItem: () => 'claim-xyz' },
  fetch: igFetch,
  chrome: { runtime: { sendMessage: toBg, onMessage: { addListener: f => { pageListener = f; } } } }
};
vm.createContext(page);
vm.runInContext(fs.readFileSync(path.join(HERE, 'content.js'), 'utf8'), page, { filename: 'content.js' });
const X = page.__matkon;
const toPage = msg => new Promise(res => { if (!pageListener(msg, {}, res)) res(undefined); });
const api = (p, body, key = KEY, method = 'POST') => fetch(M + p, { method, headers: { 'X-Matkon': '1', 'X-Matkon-Key': key, 'Content-Type': 'application/json' }, body: typeof body === 'string' || body instanceof Uint8Array ? body : JSON.stringify(body || {}) });
const reel = code => path.join(state, 'reels', code);
const settle = async () => { for (let i = 0; i < 200 && (X.queue.size || (await toPage({ type: 'page' })).busy); i++) await new Promise(r => setTimeout(r, 50)); };

try {
  console.log('Matkon refuses what it should');
  ok((await api('/api/ext/hello', {}, 'mk_wrongwrongwrongwrongwrong')).status === 401, 'a wrong key');
  ok((await fetch(M + '/api/ext/hello', { method: 'POST', headers: { 'X-Matkon-Key': KEY }, body: '{}' })).status === 403, 'no X-Matkon header');
  ok((await api('/api/ext/video/NOPOST1', 'xx', KEY, 'PUT')).status === 409, 'a video before its post');
  await api('/api/ext/post', { media: media('KNOWN01', true) });
  ok((await api('/api/ext/video/KNOWN01', new Uint8Array([1, 2, 3, 4]), KEY, 'PUT')).status === 400, 'something that isn\'t a video');
  ok((await api('/api/ext/video/KNOWN01', fs.readFileSync(video), KEY, 'PUT')).ok && fs.existsSync(path.join(reel('KNOWN01'), 'video.mp4')), 'a real video, after its post');
  py(`from matkon import store; print(store.queue("https://www.instagram.com/reel/WANTED1/", "tester"))`);   // "Add a reel"

  console.log('A check');
  ok(!(await X.hello()).connected, 'not connected before the connection is saved');
  Object.assign(store, { url: M, key: KEY });          // what the options page saves
  const s = await X.hello();
  ok(s.connected && s.due && s.collection_id === COLL && s.wanted.includes('WANTED1'), 'hello: connected, due, the collection, the queue');
  const r = await X.check();
  await settle();
  const feed = igHits.filter(h => h.path.startsWith('/api/v1/feed/saved/posts/'));
  ok(feed.length === 2, `two pages of saves, and not the third (stops at a reel Matkon has): ${feed.length}`);
  ok(feed.every(h => h.headers['X-IG-App-ID'] === '936619743392459' && h.headers['X-CSRFToken'] === 'tok123' && h.headers['X-IG-WWW-Claim'] === 'claim-xyz' && h.credentials === 'include'),
    'Instagram is asked the way its own page asks');
  ok(!r.error && r.found === 5, `five new in the collection (A, C, the photo, E, F): ${r.found}`);
  const up = ['WANTED1', 'AAAAAA1', 'CCCCCC1', 'EEEEEE1'];
  ok(up.every(c => fs.existsSync(path.join(reel(c), 'video.mp4'))), 'four videos in (the queued one first), the most an hour');
  ok(!fs.existsSync(path.join(reel('FFFFFF1'), 'video.mp4')) && X.queue.has('FFFFFF1'), 'the fifth waits for the next hour');
  ok(!fs.existsSync(reel('BBBBBB1')), 'a save in another collection stays out');
  ok(cdnHits.every(u => u.startsWith('/v/')), 'the 720 video, not the 1440 one');
  const photo = JSON.parse(fs.readFileSync(path.join(reel('PHOTO01'), 'status.json'), 'utf8'));
  ok(photo.tries >= 3 && /not a video/.test(photo.error), 'a photo post is noted and left alone');
  const post = JSON.parse(fs.readFileSync(path.join(reel('AAAAAA1'), 'post.json'), 'utf8'));
  ok(post.user === 'cook.example' && post.caption.startsWith('Recipe AAAAAA1') && post.added_by === 'tester' && !('video_versions' in post), 'the post: who, the caption, who added it, nothing else');
  ok(igHits.filter(h => h.path.includes('/media/')).length === 1, 'one info request, for the queued reel only');
  ok(store.lastCheck > 0 && !store.lastError, 'the check is remembered');
  ok(!(await X.hello()).due, 'not due again right away');

  console.log('Matkon makes the recipe');
  let st = {};
  for (let i = 0; i < 100; i++) {
    try { st = JSON.parse(fs.readFileSync(path.join(reel('AAAAAA1'), 'status.json'), 'utf8')); } catch (e) { /* not yet */ }
    if (st.error) break;
    await new Promise(r => setTimeout(r, 100));
  }
  ok(/^transcript:/.test(st.error || ''), `a run started on its own and went on to the transcript (stopped there on purpose): ${st.error}`);

  console.log('The recipe collection\'s own page');
  store.brought = [];
  page.location.pathname = `/someone/saved/recipes/${COLL}/`;
  anchors = ['/someone/reel/HARVST1/', '/p/AAAAAA1/', '/explore/'];
  await X.harvest();
  await settle();
  ok(fs.existsSync(path.join(reel('HARVST1'), 'video.mp4')), 'a reel scrolled past comes in');
  ok(fs.existsSync(path.join(reel('FFFFFF1'), 'video.mp4')), 'and the one that waited');
  const pg = await toPage({ type: 'page' });
  ok(pg.collection && pg.collection.id === COLL && pg.collection.name === 'Recipes' && pg.current === COLL, 'the popup knows it\'s on the recipe collection');

  console.log('The popup\'s buttons');
  page.location.pathname = '/someone/saved/dinners/555555555/';
  ok((await toPage({ type: 'use-collection' })).ok && (await X.hello()).collection_id === '555555555', 'Use this collection');
  const saved = JSON.parse(fs.readFileSync(path.join(state, 'settings.json'), 'utf8'));
  ok(saved.collection_id === '555555555' && saved.collection_name === 'Dinners', 'and it\'s the owner\'s collection now');
  page.location.pathname = '/reel/ONREEL1/';
  ok((await toPage({ type: 'send-this' })).ok, 'Send this reel');
  await settle();
  ok(fs.existsSync(path.join(reel('ONREEL1'), 'video.mp4')), 'it came in');
  ok((await toPage({ type: 'send-this' })).had, 'and a second time it says it\'s in already');

  console.log('Instagram says no');
  igMode = 'signed-out';
  store.lastCheck = 0;
  const before = igHits.length;
  const r2 = await X.check();
  ok(r2.error === 'signed-out' && igHits.length === before + 1, 'one request, then it stops');
  const b = JSON.parse(fs.readFileSync(path.join(state, 'users', 'tester', 'browser.json'), 'utf8'));
  ok(b.error === 'signed-out' && b.version === '0.1.0', 'Matkon hears about it (Settings shows it)');

  console.log('Paused');
  fs.writeFileSync(path.join(state, 'paused'), 'now\n');
  igMode = 'ok';
  store.lastCheck = 0;
  const n = igHits.length;
  const s3 = await X.hello();
  await X.check();
  ok(s3.paused && !s3.due && s3.wanted.length === 0 && igHits.length === n, 'nothing asks Instagram for anything');
  ok((await toPage({ type: 'check-now' })).error === 'paused', 'Check now says it\'s paused');
} finally {
  server.kill();
  cdn.close();
  fs.rmSync(state, { recursive: true, force: true });
}
console.log(failures ? `\n${failures} failed` : '\nall good');
process.exit(failures ? 1 : 0);

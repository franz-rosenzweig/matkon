/* The options page: the connection from Matkon's Settings (its address and this browser's key, as one
   line: https://your-matkon/#/key/mk_…), kept in the extension's own storage. */
const P = globalThis.browser || globalThis.chrome;
const $ = s => document.querySelector(s);
const INSTAGRAM = ['https://www.instagram.com/*', 'https://*.cdninstagram.com/*', 'https://*.fbcdn.net/*'];

function say(text, kind) { const s = $('#status'); s.textContent = text; s.className = 'status' + (kind ? ' ' + kind : ''); }

function parse(line) {
  const m = (line || '').trim().match(/^(https?:\/\/[^\s#?]+?)\/?#\/key\/(mk_[A-Za-z0-9_-]{20,})$/);
  return m ? { url: m[1].replace(/\/+$/, ''), key: m[2] } : null;
}

async function test() {
  say('Checking…');
  const r = await P.runtime.sendMessage({ type: 'test' });
  if (r && r.connected) say('Connected · ' + (r.name || r.account) + (r.collection_name ? ' · ' + r.collection_name : ''), 'ok');
  else say((r && r.error) || 'The extension didn’t answer.', 'bad');
}

$('#f').addEventListener('submit', async e => {
  e.preventDefault();
  const line = $('#conn').value.trim();
  if (!line) {
    await P.storage.local.set({ url: '', key: '', state: null, name: '' });
    return say('Disconnected');
  }
  const c = parse(line);
  if (!c) return say('That isn’t a connection from Matkon’s Settings.', 'bad');
  // Asked while the click still counts (a browser only asks about access during one): Instagram, its
  // video servers, and your Matkon.
  let allowed = true;
  try { allowed = await P.permissions.request({ origins: [...INSTAGRAM, new URL(c.url).origin + '/*'] }); } catch (err) { /* already granted */ }
  if (!allowed) return say('The extension needs Instagram and your Matkon to work.', 'bad');
  await P.storage.local.set({ url: c.url, key: c.key });
  test();
});

(async () => {
  const s = await P.storage.local.get({ url: '', key: '' });
  if (s.url && s.key) {
    $('#conn').value = s.url + '/#/key/' + s.key;
    test();
  }
})();

/* The toolbar button: whether it's connected, when it last looked, and on Instagram, "Check now",
   "Send this reel" on a reel, and "Use this collection" on one of your saved collections. */
const P = globalThis.browser || globalThis.chrome;
const $ = s => document.querySelector(s);
const SAID = { 'signed-out': 'Sign in to Instagram', busy: 'Instagram asked for a break', instagram: 'Instagram didn’t answer', matkon: 'Matkon didn’t answer' };

function when(t) {
  const d = new Date(t);
  const today = d.toDateString() === new Date().toDateString();
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) + (today ? '' : ' · ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' }));
}

function say(text, kind) { const s = $('#status'); s.textContent = text; s.className = 'status' + (kind ? ' ' + kind : ''); }

function button(label, fn, accent) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'btn' + (accent ? ' accent' : '');
  b.textContent = label;
  b.addEventListener('click', async () => {
    b.disabled = true;
    try { await fn(b); } catch (e) { say(String(e.message || e), 'bad'); }
  });
  $('#actions').append(b);
  return b;
}

async function toPage(tab, msg) {
  const r = await P.tabs.sendMessage(tab.id, msg);
  if (r && r.error) throw new Error(r.error === 'paused' ? 'Paused' : r.error);
  return r || {};
}

$('#options').addEventListener('click', () => { P.runtime.openOptionsPage(); window.close(); });

(async () => {
  const s = await P.runtime.sendMessage({ type: 'status' });
  if (!s.connected) {
    say('Not connected');
    button('Connect', () => { P.runtime.openOptionsPage(); window.close(); }, true);
    return;
  }
  say([s.name || 'Connected', s.paused ? 'Paused' : s.lastError ? (SAID[s.lastError] || s.lastError) : s.lastCheck ? 'Checked ' + when(s.lastCheck) : '']
    .filter(Boolean).join(' · '), !s.paused && s.lastError ? 'bad' : '');
  $('#sub').textContent = s.collection || '';
  if (s.paused) return;
  const [tab] = await P.tabs.query({ active: true, currentWindow: true });
  if (!tab || !/^https:\/\/www\.instagram\.com\//.test(tab.url || '')) return;
  let page;
  try { page = await P.tabs.sendMessage(tab.id, { type: 'page' }); } catch (e) { return; }   // the page from before the extension: reload
  if (!page) return;
  if (page.collection && page.collection.id !== page.current) {
    button('Use this collection', async () => { await toPage(tab, { type: 'use-collection' }); say('Saved', 'ok'); $('#sub').textContent = page.collection.name; }, true);
  }
  if (page.reel) {
    button('Send this reel', async () => { const r = await toPage(tab, { type: 'send-this' }); say(r.had ? 'Already in Matkon' : 'On its way', 'ok'); });
  }
  if (page.current) {
    button(page.busy ? 'Checking…' : 'Check now', async b => { await toPage(tab, { type: 'check-now' }); b.textContent = 'Checking…'; say('Checking…'); }).disabled = page.busy;
  }
})();

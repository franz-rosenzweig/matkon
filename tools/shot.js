#!/usr/bin/env node
'use strict';
// Screenshots of Matkon in a headless Chrome with remote debugging on, one fresh browser context per
// shot.   DEVTOOLS=host:port (default 127.0.0.1:9222), or CHROME=<docker container> to find it.
//   node tools/shot.js <app url as Chrome sees it> <out dir> name:WxH[:dark][:full][:clear][:click=sel]:#/route ...
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const [APP, OUT, ...SHOTS] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const DT = process.env.DEVTOOLS || (process.env.CHROME
  ? execFileSync('docker', ['inspect', '-f', '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}', process.env.CHROME]).toString().trim().split(' ')[0] + ':9222'
  : '127.0.0.1:9222');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, seq = 0;
const pending = new Map();
function cdp(method, params = {}, sessionId) {
  const id = ++seq;
  ws.send(JSON.stringify({ id, method, params, sessionId }));
  return new Promise((ok, no) => pending.set(id, { ok, no }));
}
(async () => {
  const v = await (await fetch(`http://${DT}/json/version`)).json();
  ws = new WebSocket(v.webSocketDebuggerUrl.replace(/\/\/[^/]+/, `//${DT}`));
  await new Promise((r) => ws.addEventListener('open', r));
  const errors = [];
  ws.addEventListener('message', (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.no(new Error(m.error.message)) : p.ok(m.result); }
    if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
  });
  for (const spec of SHOTS) {
    const [name, size, ...rest] = spec.split(':');
    const route = rest.find((x) => x.startsWith('#')) || '#/';
    const click = (rest.find((x) => x.startsWith('click=')) || '').slice(6);
    const [width, height] = size.split('x').map(Number);
    const { browserContextId } = await cdp('Target.createBrowserContext', { disposeOnDetach: true });
    const { targetId } = await cdp('Target.createTarget', { url: 'about:blank', browserContextId });
    const { sessionId } = await cdp('Target.attachToTarget', { targetId, flatten: true });
    const s = (m, p) => cdp(m, p, sessionId);
    await s('Page.enable'); await s('Runtime.enable');
    await s('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 2, mobile: width < 1000 });
    await s('Emulation.setTouchEmulationEnabled', { enabled: width < 1400, maxTouchPoints: 5 });
    await s('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: rest.includes('dark') ? 'dark' : 'light' }] });
    if (rest.includes('clear')) await s('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });   // a transparent background (icons)
    await s('Page.navigate', { url: APP + route });
    await sleep(2500);
    if (click) { await s('Runtime.evaluate', { expression: `document.querySelector(${JSON.stringify(click)})?.click()` }); await sleep(1200); }
    const ev = await s('Runtime.evaluate', { expression: 'JSON.stringify({w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight})', returnByValue: true });
    const dims = JSON.parse(ev.result.value);
    const full = rest.includes('full');
    const shot = await s('Page.captureScreenshot', { format: 'png', captureBeyondViewport: full, ...(full ? { clip: { x: 0, y: 0, width, height: Math.min(dims.h, 6000), scale: 1 } } : {}) });
    fs.writeFileSync(path.join(OUT, name + '.png'), Buffer.from(shot.data, 'base64'));
    console.log(name, `${width}x${height}`, 'scrollWidth', dims.w, dims.w > width ? 'OVERFLOW' : 'ok', 'height', dims.h);
    await cdp('Target.closeTarget', { targetId });
    await cdp('Target.disposeBrowserContext', { browserContextId }).catch(() => {});
  }
  if (errors.length) console.log('PAGE ERRORS:', errors);
  ws.close();
})().catch((e) => { console.error(e); process.exit(1); });

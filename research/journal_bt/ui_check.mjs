// Runs the journal's own Signals code (index.html) on the rebuilt scanner alerts and
// saved Delta candles, for every "How each trade is played" rule set, and writes one
// R per alert per rule set (Float32, NaN = no result) plus each alert's labels.
//
// node harness.mjs --app /home/user/journal --data DIR --candles DIR --now EPOCH --out DIR [--limit N] [--rules all|smoke]
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const APP = arg('app', '/home/user/journal');
const DATA = arg('data');
const CANDLES = arg('candles', '');
const NOW = +arg('now');
const OUT = arg('out');
const RULES = arg('rules', 'all');
const LIMIT = +arg('limit', 0);
fs.mkdirSync(OUT, { recursive: true });

const readMaybeGz = f => fs.existsSync(f) ? fs.readFileSync(f) : fs.existsSync(f + '.gz') ? zlib.gunzipSync(fs.readFileSync(f + '.gz')) : null;
const SCAN = {
  'fibtl_rebuild_records.jsonl': readMaybeGz(path.join(DATA, 'fibtl_rebuild_records.jsonl')),
  'fibtl_rebuild_results.json': readMaybeGz(path.join(DATA, 'fibtl_rebuild_results.json')),
  'fibtl_rebuild_meta.json': readMaybeGz(path.join(DATA, 'fibtl_rebuild_meta.json')),
};
for (const [k, v] of Object.entries(SCAN)) if (!v) throw new Error('missing ' + k);

const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  if (u.startsWith('/candles/')) {
    const f = path.join(CANDLES, path.basename(u) + '.json.gz');
    if (!CANDLES || !fs.existsSync(f)) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(zlib.gunzipSync(fs.readFileSync(f)));
  }
  const file = path.join(APP, u === '/' ? 'index.html' : u);
  if (!file.startsWith(APP) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': file.endsWith('.html') ? 'text/html; charset=utf-8' : 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = 'http://127.0.0.1:' + server.address().port + '/';

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--js-flags=--max-old-space-size=8000'] });
const ctx = await browser.newContext({ timezoneId: 'Asia/Kolkata', viewport: { width: 1400, height: 900 } });
const SCANNER_BASE = 'https://raw.githubusercontent.com/victus2034/victus-indicator-strategy/scanner-runtime-state/';
await ctx.route(url => !url.href.startsWith(base), r => {
  const h = r.request().url();
  if (h.startsWith(SCANNER_BASE)) {
    const name = h.slice(SCANNER_BASE.length).split('?')[0];
    return r.fulfill({ status: 200, contentType: 'text/plain', body: SCAN[name] || '' });
  }
  return r.abort();
});
// Delta's candle API, answered from the saved candles: the rows whose open time is in
// [start, end], as Delta answers (journal_bt_candles.py edge probe).
await ctx.addInitScript(base => {
  const store = {}, loading = {};
  const orig = window.fetch.bind(window);
  window.__deltaReads = 0;
  window.__deltaMiss = {};
  async function series(sym, res) {
    const k = sym + '_' + res;
    if (store[k]) return store[k];
    if (!loading[k]) loading[k] = window.__getSeries(k).then(t => t ? JSON.parse(t) : null).then(j => {
      const rows = j && Array.isArray(j.candles) ? j.candles : [];
      store[k] = { t: Float64Array.from(rows.map(x => x[0])), rows };
      return store[k];
    });
    return loading[k];
  }
  const lb = (a, v) => { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] < v) lo = m + 1; else hi = m; } return lo; };
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input.url;
    if (url.startsWith('https://api.india.delta.exchange/v2/history/candles')) {
      window.__deltaReads++;
      const q = new URL(url).searchParams;
      const s = await series(q.get('symbol'), q.get('resolution'));
      if (!s.rows.length) window.__deltaMiss[q.get('symbol') + '_' + q.get('resolution')] = 1;
      const a = lb(s.t, +q.get('start')), b = lb(s.t, +q.get('end') + 1);
      const result = s.rows.slice(a, b).map(x => ({ time: x[0], open: x[1], high: x[2], low: x[3], close: x[4], volume: x[5] }));
      return new Response(JSON.stringify({ success: true, result }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    return orig(input, init);
  };
}, base);

// Saved candles reach the page through a binding (the app's CSP allows no local reads).
await ctx.exposeFunction('__getSeries', k => {
  const f = path.join(CANDLES, path.basename(k) + '.json.gz');
  return CANDLES && fs.existsSync(f) ? zlib.gunzipSync(fs.readFileSync(f)).toString('utf8') : null;
});
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', e => errs.push('page error: ' + (e.stack || e.message)));
page.on('dialog', d => d.dismiss());
await page.clock.setFixedTime(new Date(NOW * 1000));
await page.goto(base, { waitUntil: 'load' });
await page.waitForFunction(() => typeof state !== 'undefined' && state && typeof tgtReady !== 'undefined' && tgtReady, null, { timeout: 60000 });
await page.waitForTimeout(3500);


// UI check: drive the Signals tab like a person would, let the app read its own
// candles (tgtLoad), and read the stat strip off the page.
const combos = JSON.parse(fs.readFileSync(arg('combos'), 'utf8'));
await page.evaluate(async () => {
  await signalsReady;
  state.ui.sigMkt = 'crypto';
  while (sigAutoBusy) await new Promise(r => setTimeout(r, 200));
  await autoRefreshAlerts(true);
  await mktFetch();
  switchTab('signals');
});
const out = [];
for (const c of combos) {
  const res = await page.evaluate(async c => {
    Object.assign(state.ui, { sigKind: c.kind, sigChan: c.chan, sigCoins: c.coins, sigCoinRank: 'cap', mktFilter: c.btc, sigLvl: c.lvl || '', sigTlType: c.tl || '',
      sigPeriod: { mode: 'all' }, sigDay: '', sigTgt: c.tgt, sigHold: c.hold, sigNoFee: c.nofee, sigSkipTiny: false,
      sigStop: c.stop, sigTrail: c.trail });
    renderSignalsTable();
    for (let k = 0; k < 2000; k++) { await new Promise(r => setTimeout(r, 100)); if (!tgtBusy) { renderSignalsTable(); await new Promise(r => setTimeout(r, 50)); if (!tgtBusy) break; } }
    const cards = [...document.querySelectorAll('#sigEdgeStrip > div')].map(d => d.innerText.replace(/\s+/g, ' ').trim());
    const note = (document.getElementById('sigTgtNote') || {}).innerText || '';
    return { cards, note, period: state.ui.sigPeriod };
  }, c);
  out.push({ c, res });
  console.log(JSON.stringify(c.label), '\n  ', res.cards.join(' | '), '\n  ', res.note.slice(0, 220));
}
fs.writeFileSync(path.join(OUT, 'ui_check.json'), JSON.stringify(out, null, 1));
console.log('errors', errs.length, errs.slice(0, 3));
await browser.close();
server.close();

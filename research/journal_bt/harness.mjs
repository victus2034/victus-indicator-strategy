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
const WALK = arg('walk', 'app'); // app: tgtOne as the app reads; fine: every walk on 15m candles (precision check)
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
  window.__series = series;
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

// 1) Alerts, read the way the app reads them.
const loaded = await page.evaluate(async () => {
  await signalsReady;
  state.ui.sigMkt = 'crypto';
  while (sigAutoBusy) await new Promise(r => setTimeout(r, 200));
  await autoRefreshAlerts(true);
  await mktFetch();
  const n = {};
  (state.signals || []).forEach(g => { const k = (g.kind || 'zone') + ' ' + g.channel; n[k] = (n[k] || 0) + 1; });
  return { total: (state.signals || []).length, n, btcDays: Object.keys(mktCache().byDate).length, err: mktLoadErr };
});
console.log('alerts', JSON.stringify(loaded));

// 2) Alert list in the app's order, with every "which alerts" label.
const meta = await page.evaluate(limit => {
  const out = [];
  window.__btPairs = [];
  ['fib', 'trendline'].forEach(kind => {
    let pairs = matchSignals(kind).filter(pr => /^CRYPTO /.test(chanKey(pr.signal)));
    if (limit) pairs = pairs.slice(-limit);
    pairs.forEach(pr => {
      const g = pr.signal, geo = kind === 'fib' ? fibGeom(g) : null;
      const line = kind === 'trendline' ? sigTlLine(g) : null, side = g.side === 'short' ? 'short' : 'long';
      const tt = kind === 'trendline' ? (SIG_TL_TYPES.find(x => x.k && x.line === line && x.side === side) || {}).k || '' : '';
      window.__btPairs.push(pr);
      out.push({ i: out.length, kind, chan: chanKey(g), coin: coinOf(g), btc: mktBiasOn(g.date, g.time) || '', lvl: geo ? geo.entryLevel : '', tl: tt,
        date: g.date, time: g.time, when: sbtWhen(g), sym: g.symbol, dsym: tgtSym(g.symbol), side, entry: signalEntry(g), stop: g.stop, tf: g.timeframe, slp: slPct(g), feeR: sigFeeR(g), key: g.key,
        filled: g.filled === true ? 1 : g.filled === false ? 0 : -1, scanR: typeof g.resultR === 'number' ? g.resultR : null, why: tgtWhy(g) });
    });
  });
  return out;
}, LIMIT);
console.log('pairs', meta.length);

// 3) Candle walks, both holds, through the app's own tgtOne (its resolution choice and tgtWalk).
const walks = await page.evaluate(async WALK => {
  // The app's tgtWalk on 15m candles for every alert, whatever its age (tgtOne reads one
  // page of at most 1900 candles, so an older alert gets 1h / 4h / 1d candles).
  async function fineWalk(g, hold) {
    const s = await window.__series(tgtSym(g.symbol), '15m');
    const t0 = tgtAlertMs(g), span = hold === 'tp' ? Math.max(Date.now() - t0, 3600000) : 2 * TGT_BARS * tfMinutes(g.timeframe) * 60000;
    const from = (t0 - 15 * 60000) / 1000, to = Math.min(Date.now(), t0 + span) / 1000;
    const lb = v => { let lo = 0, hi = s.t.length; while (lo < hi) { const m = (lo + hi) >> 1; if (s.t[m] < v) lo = m + 1; else hi = m; } return lo; };
    const rows = s.rows.slice(lb(from), lb(to + 1e-6)).map(x => ({ time: x[0], open: x[1], high: x[2], low: x[3], close: x[4] }));
    return rows.length ? tgtWalk(g, rows, 15, hold) : { none: 'no candles on Delta' };
  }
  state.ui.sigTgt = '1R';
  const st = { tp: {}, '20': {} };
  for (const hold of ['tp', '20']) {
    for (const pr of window.__btPairs) {
      const g = pr.signal, k = tgtHoldKey(g, hold);
      if (tgtWhy(g) || !tgtBase({ signal: g })) { st[hold].skip = (st[hold].skip || 0) + 1; continue; }
      if (tgtCache()[k] || tgtLive[k]) continue;
      let w;
      try { w = WALK === 'fine' ? await fineWalk(g, hold) : await tgtOne(g, hold); } catch (e) { st[hold].fail = (st[hold].fail || 0) + 1; st[hold].lastErr = String(e && e.stack || e).slice(0, 300); continue; }
      if ((w.none && !w.wait) || w.sl || w.done) tgtCache()[k] = w; else { tgtLive[k] = w; delete tgtCache()[k]; }
      const lab = w.none ? 'none:' + w.none + (w.wait ? ':wait' : '') : w.sl ? 'sl' : w.done ? 'done' : 'open';
      st[hold][lab] = (st[hold][lab] || 0) + 1;
    }
  }
  return { st, reads: window.__deltaReads, miss: Object.keys(window.__deltaMiss) };
}, WALK);
console.log('walks', JSON.stringify(walks));

// 4) Rule sets.
const STOP_ATS = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3], STOP_TOS = [-0.5, 0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 2.5];
const STOP_ATS_P = [0.25, 0.5, 0.75, 1, 1.5, 2, 2.5, 3], STOP_TOS_P = [-0.25, 0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 2.5];
const TGTS = [['1R', 1, 'R'], ['1.5R', 1.5, 'R'], ['2R', 2, 'R'], ['3R', 3, 'R'], ['1%', 1, '%'], ['2%', 2, '%'], ['3%', 3, '%']];
const rules = [{ tgt: '', hold: 'tp', stop: 'off', trail: 'off' }];
for (const hold of ['tp', '20']) for (const [tk, tv, u] of TGTS) {
  const ats = u === 'R' ? STOP_ATS : STOP_ATS_P, tos = u === 'R' ? STOP_TOS : STOP_TOS_P;
  const stops = [{ mode: 'off' }];
  ats.filter(a => a < tv).forEach(a => stops.push({ mode: 'be', at: a }));
  ats.filter(a => a < tv).forEach(a => tos.filter(t => t < a).forEach(t => stops.push({ mode: 'shift', at: a, to: t })));
  const trails = [{ on: false }];
  [0.25, 0.5, 1].forEach(s => [0, 0.25, 0.5, 0.75, 1].forEach(g => trails.push({ on: true, step: s, gap: g })));
  for (const sp of stops) for (const tr of trails) {
    const stopTxt = sp.mode === 'off' ? 'off' : sp.mode === 'be' ? `BE at +${sp.at}${u}` : `SL to ${sp.to > 0 ? '+' : ''}${sp.to}${u} at +${sp.at}${u}`;
    const trTxt = tr.on ? `TP +${tr.step}${u}, SL ${tr.gap}${u} behind` : 'off';
    rules.push({ tgt: tk, unit: u, hold, stopRule: sp, trailRule: tr, stop: stopTxt, trail: trTxt });
  }
}
const use = RULES === 'smoke' ? rules.filter((r, i) => i === 0 || (r.stop === 'off' && (r.trail === 'off' || r.trail.startsWith('TP +0.25')))) : rules;
console.log('rule sets', use.length);
fs.writeFileSync(path.join(OUT, 'rules.json'), JSON.stringify(use));
fs.writeFileSync(path.join(OUT, 'alerts.json'), JSON.stringify(meta));

// 5) Score: the app's outcomeNow inside the Signals scope, each rule set set on state.ui.
const fd = fs.openSync(path.join(OUT, 'r.f32'), 'w');
const t0 = Date.now();
const B = 40;
for (let i = 0; i < use.length; i += B) {
  const chunk = use.slice(i, i + B);
  const b64 = await page.evaluate(chunk => {
    const n = window.__btPairs.length, buf = new Float32Array(n * chunk.length);
    chunk.forEach((ru, j) => {
      state.ui.sigTgt = ru.tgt;
      state.ui.sigHold = ru.hold;
      state.ui.sigNoFee = false;
      const sp = ru.stopRule || { mode: 'off' }, pc = ru.unit === '%';
      const st = { mode: sp.mode, beAt: 1, shAt: 1, shTo: 0.75, beAtP: 1, shAtP: 1, shToP: 0.5 };
      if (sp.mode === 'be') st[pc ? 'beAtP' : 'beAt'] = sp.at;
      if (sp.mode === 'shift') { st[pc ? 'shAtP' : 'shAt'] = sp.at; st[pc ? 'shToP' : 'shTo'] = sp.to; }
      state.ui.sigStop = st;
      const tr = ru.trailRule || { on: false };
      state.ui.sigTrail = { on: !!tr.on, step: tr.step || 0.25, gap: tr.gap != null ? tr.gap : 0.25, stepP: tr.step || 0.25, gapP: tr.gap != null ? tr.gap : 0.25 };
      // The app's own reading of these settings must be what was asked.
      const mv = inSigScope(() => sigStopMove()), tv = inSigScope(() => sigTrail());
      if (sp.mode !== 'off' && (!mv || mv.at !== sp.at || (sp.mode === 'shift' && mv.to !== sp.to))) throw new Error('stop rule not taken: ' + JSON.stringify(ru));
      if (tr.on && (!tv || tv.step !== tr.step || tv.gap !== tr.gap)) throw new Error('trail not taken: ' + JSON.stringify(ru));
      inSigScope(() => withOutcomeCache(() => {
        for (let a = 0; a < n; a++) { const o = outcomeOf(window.__btPairs[a]); buf[j * n + a] = o ? o.r : NaN; }
      }));
    });
    const u8 = new Uint8Array(buf.buffer); let s = '';
    for (let k = 0; k < u8.length; k += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(k, k + 0x8000));
    return btoa(s);
  }, chunk);
  fs.writeSync(fd, Buffer.from(b64, 'base64'));
  if ((i / B) % 10 === 0) console.log(`scored ${Math.min(i + B, use.length)}/${use.length} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
}
fs.closeSync(fd);

// 6) Fees off, read the app's way for a sample, to check R + fee-in-R holds.
const feeCheck = await page.evaluate(() => {
  let bad = 0, n = 0;
  for (const tk of ['', '1R', '2%']) {
    state.ui.sigTgt = tk; state.ui.sigHold = 'tp'; state.ui.sigStop = { mode: 'off' }; state.ui.sigTrail = { on: true, step: 0.25, gap: 0.25, stepP: 0.25, gapP: 0.25 };
    window.__btPairs.forEach(pr => {
      state.ui.sigNoFee = false; const a = inSigScope(() => outcomeNow(pr));
      state.ui.sigNoFee = true; const b = inSigScope(() => outcomeNow(pr));
      if (!a && !b) return; n++;
      if (!a || !b || Math.abs(b.r - a.r - sigFeeR(pr.signal)) > 1e-6) bad++;
    });
  }
  state.ui.sigNoFee = false;
  return { n, bad };
});
console.log('fee check', JSON.stringify(feeCheck));
fs.writeFileSync(path.join(OUT, 'run.json'), JSON.stringify({ now: NOW, loaded, walks, feeCheck, rules: use.length, alerts: meta.length, errs }, null, 1));
console.log('errors', errs.length, errs.slice(0, 3));
await browser.close();
server.close();

"""1D TL breaks only vs touch + break, on checked candles (lakky, 2026-11-21: "make sure all the
symbols data is accurate and clean and also do not include data which does not have any confirm
exit and fix all those which does not show data and also make sure in signals it connect and
shows true results").

Three jobs in one run:
  data     - every coin's Bitunix 1d / 4h / 15m and Delta 1d / 15m: rows, first candle, missing
             candles (gaps), duplicates, zero / NaN rows, high / low not covering open / close,
             one-candle spikes, and Bitunix vs Delta daily close / high / low
  replay   - tl_breaks_only_backtest on cleaned candles (scanner.clean_candles, the live
             scanner's own filter), closed trades only; a trade whose walk crosses a missing
             15m candle is counted apart ("clean only" rows); open / waiting / no fill / no stop /
             news trades are counted and left out
  journal  - the 1D crypto TL BROKEN alerts the journal's Signals tab shows (fibtl rebuild
             before its cutoff, live records after), walked like the journal on Delta 15m
             (wick-or-body 0.75% stop, 1.5R + SL shift + trail, fees 0.0826%, slip 0.05%), one
             row per alert id, plus the Delta candles used (gzip) so the journal itself can be
             replayed offline against them

    PYTHONPATH=research python research/tl_breaks_verify.py STATE_DIR --since 2025-01-01
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_data  # noqa: E402
import config  # noqa: E402
import fib_trendline_data as ftd  # noqa: E402
import journal_fib_setup_backtest as jfs  # noqa: E402
import journal_tl_setup_backtest as jts  # noqa: E402
import scanner  # noqa: E402
import tl_lower_tf_entry_backtest as low  # noqa: E402
from journal_fib_setup_backtest import DAY, IST, ist, news_overlap, stats, walk, wick_body_stop  # noqa: E402
from tl_breaks_only_backtest import HEAD, SEP1, slots  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "tl_breaks_verify"
SEC = {"1d": 86400, "4h": 14400, "15m": 900}
JUN1 = int(datetime(2026, 6, 1, tzinfo=IST).timestamp())

# ----------------------------------------------------------------- candles: raw kept, clean served

RAW = {}
_orig_bitunix = ftd.bitunix_candles


def raw_bitunix(pair, res, start, end):
    key = (pair, res, int(start))
    if key not in RAW:
        RAW[key] = _orig_bitunix(pair, res, start, end)
    return RAW[key]


def clean_bitunix(pair, res, start, end):
    return [r[:5] for r in scanner.clean_candles(raw_bitunix(pair, res, start, end))]


jts.bitunix_candles = clean_bitunix
low.bitunix_candles = clean_bitunix


def pair_of(symbol):
    return bitunix_data.pair_for(symbol, scanner.delta_contract(symbol))


# ----------------------------------------------------------------- job 1: data audit

def check(rows, sec, start=None):
    """Problems in one candle list [ts, o, h, l, c]."""
    ts = [r[0] for r in rows]
    bad = [r for r in rows if not all(isinstance(x, (int, float)) and math.isfinite(x) and x > 0 for x in r[1:5])]
    badid = {id(r) for r in bad}
    good = [r for r in rows if id(r) not in badid]
    hl = [r for r in good if r[2] < max(r[1], r[4]) or r[3] > min(r[1], r[4])]
    off = [t for t in ts if t % sec]
    uniq = sorted(set(ts))
    if start is not None:
        uniq = [t for t in uniq if t >= start]
    gaps = []
    for a, b in zip(uniq, uniq[1:]):
        if b - a > sec:
            gaps.append((a + sec, (b - a) // sec - 1))
    spikes = []
    # one-candle spike: a wick 4x the median 20-candle range past both neighbours
    for i in range(1, len(good) - 1):
        p, c, n = good[i - 1], good[i], good[i + 1]
        body_hi, body_lo = max(c[1], c[4]), min(c[1], c[4])
        up = (c[2] - max(body_hi, p[2], n[2])) / c[4]
        dn = (min(body_lo, p[3], n[3]) - c[3]) / c[4]
        lim = {86400: 0.25, 14400: 0.12, 900: 0.05}[sec]
        if up > lim or dn > lim:
            spikes.append((c[0], round(max(up, dn) * 100, 1)))
    return {"rows": len(rows), "first": ist(ts[0])[:10] if ts else "-", "last": ist(ts[-1]) if ts else "-",
            "dup": len(ts) - len(set(ts)), "bad": len(bad), "hl": len(hl), "off": len(off),
            "missing": sum(g[1] for g in gaps), "gaps": gaps, "spikes": spikes}


def venue_diff(bit, dlt, since):
    """Bitunix vs Delta daily candles on the same UTC day since `since`."""
    d = {r[0]: r for r in dlt}
    close, wick, n, worst = 0, 0, 0, (0.0, None)
    for r in bit:
        if r[0] < since or r[0] not in d:
            continue
        o = d[r[0]]
        n += 1
        cd = abs(r[4] - o[4]) / o[4] * 100
        wd = max(abs(r[2] - o[2]) / o[2], abs(r[3] - o[3]) / o[3]) * 100
        close += cd > 1.0
        wick += wd > 3.0
        if max(cd, wd) > worst[0]:
            worst = (max(cd, wd), r[0])
    return n, close, wick, worst


def audit_symbol(symbol, since, now):
    pair = pair_of(symbol)
    dname = jfs.delta_name(symbol)
    got = {}
    got["b1d"] = raw_bitunix(pair, "1d", ftd.HISTORY_START, now)
    got["b4h"] = raw_bitunix(pair, "4h", ftd.HISTORY_START, now)
    got["b15"] = raw_bitunix(pair, "15m", since - 3 * DAY, now)
    got["d1d"] = jfs.delta(dname, 1440, "1d", since - 320 * DAY, now)
    got["d15"] = jfs.delta(dname, 15, "15m", JUN1 - 3 * DAY, now)
    return symbol, got


def data_report(symbols, data, since):
    text = ["## 1. Candle data, every coin", "",
            "Missing = candles absent inside the coin's own history (gaps); Bad = zero / NaN price; H/L = high or "
            "low not covering open / close; Spike = a one-candle wick far past both neighbours "
            "(1d 25%, 4h 12%, 15m 5%). Venue = days Bitunix vs Delta close differs >1% / wick >3%.", "",
            "| Coin | Bitunix 1d from | 1d miss | 4h miss | 15m rows | 15m miss | Dup | Bad | H/L | Spikes 1d/4h/15m | Delta 15m miss | Venue days (close/wick) of n | Worst |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    detail = []
    for s in symbols:
        g = data.get(s)
        if not g:
            text.append(f"| {s} | NO DATA | | | | | | | | | | | |")
            continue
        a, b, c = check(g["b1d"], SEC["1d"]), check(g["b4h"], SEC["4h"]), check(g["b15"], SEC["15m"], since - 3 * DAY)
        d15 = check(g["d15"], SEC["15m"])
        n, cl, wk, worst = venue_diff(g["b1d"], g["d1d"], since)
        text.append(f"| {s} | {a['first']} | {a['missing']} | {b['missing']} | {c['rows']} | {c['missing']} | "
                    f"{a['dup'] + b['dup'] + c['dup']} | {a['bad'] + b['bad'] + c['bad']} | {a['hl'] + b['hl'] + c['hl']} | "
                    f"{len(a['spikes'])}/{len(b['spikes'])}/{len(c['spikes'])} | {d15['missing']} | {cl}/{wk} of {n} | "
                    f"{worst[0]:.1f}% {ist(worst[1])[:10] if worst[1] else ''} |")
        for name, x in (("Bitunix 1d", a), ("Bitunix 4h", b), ("Bitunix 15m", c), ("Delta 15m", d15)):
            big = sorted(x["gaps"], key=lambda g: -g[1])[:5]
            if big:
                detail.append(f"{s} {name} gaps (largest): " + ", ".join(f"{ist(t)} x{k}" for t, k in big))
            if x["spikes"]:
                detail.append(f"{s} {name} spikes: " + ", ".join(f"{ist(t)} {p}%" for t, p in x["spikes"][:6]))
    return text + ["", "```"] + (detail or ["no gaps, no spikes"]) + ["```"]


# ----------------------------------------------------------------- job 2: replay on clean candles

def gap_in(fine_ts, start, end):
    """Missing 15m candles in [start, end)."""
    if end is None or end <= start:
        return 0
    want = (end - start) // 900
    import bisect
    have = bisect.bisect_left(fine_ts, end) - bisect.bisect_left(fine_ts, start)
    return max(0, want - have)


def replay_symbol(symbol, since, now):
    try:
        touches = low.symbol_trades(symbol, since, now)["confirm 1h, SL day"]
        breaks = [t for t in jts.symbol_trades(symbol, since, now) if t["level"] == "BR"]
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} replay failed: {error!r}")
        return None
    for t in touches:
        t["level"] = "touch"
    fine_ts = sorted(r[0] for r in clean_bitunix(pair_of(symbol), "15m", since - 3 * DAY, now))
    rows = touches + breaks
    for t in rows:
        if t.get("fill_ts") is not None:
            t["gap"] = gap_in(fine_ts, t["fill_ts"], t.get("exit_ts", now - now % 900) + (900 if t.get("exit_ts") else 0))
    return rows


def trow(name, rows, extra=""):
    st = stats(sorted(rows, key=lambda t: t["fill_ts"]))
    if not st:
        return f"| {name} | 0 | | | | | |{extra}"
    return (f"| {name} | {st['n']} | {st['wins'] / st['n'] * 100:.0f}% | {st['avg']:+.3f}R | {st['pct']:+.2f}% | "
            f"{st['tot']:+.1f}R | -{st['dd']:.1f}R |{extra}")


THEAD = "| Set | Closed | Win | R/trade | %/trade | Total R | Max DD |\n|---|---|---|---|---|---|---|"


def replay_report(rows, since, symbols):
    count = lambda xs, f: sum(1 for t in xs if f(t))
    text = ["## 2. Replay, 1D TL, closed trades only", ""]
    for label, lo in (("Sep 1 - now", max(since, SEP1)), (f"{ist(since)[:10]} - now", since)):
        part = [t for t in rows if t.get("alert_ts", 0) >= lo]
        filled = [t for t in part if t.get("fill_ts") is not None and t.get("outcome") != "no stop"]
        news = [t for t in filled if t.get("news")]
        ok = [t for t in filled if not t.get("news")]
        opened = [t for t in ok if t.get("r") is None]
        closed = [t for t in ok if t.get("r") is not None]
        gap = [t for t in closed if t.get("gap")]
        clean = [t for t in closed if not t.get("gap")]
        br, to = [t for t in closed if t["level"] == "BR"], [t for t in closed if t["level"] == "touch"]
        brc = [t for t in clean if t["level"] == "BR"]
        # the bot's slots count open trades too (they hold a slot), then only closed ones are scored
        live = slots([t for t in ok], config.COINDCX_LIVE_MAX_OPEN)
        live_br = slots([t for t in ok if t["level"] == "BR"], config.COINDCX_LIVE_MAX_OPEN)
        text += [f"### {label}", "",
                 f"Alerts {len(part)}: no fill {count(part, lambda t: t.get('fill_ts') is None)}, no 0.75% wick/body stop "
                 f"{count(part, lambda t: t.get('outcome') == 'no stop')}, CPI/PPI/FOMC fills left out {len(news)}, "
                 f"still open (no exit yet, left out) {len(opened)} (breaks {count(opened, lambda t: t['level'] == 'BR')}), "
                 f"closed {len(closed)}, of which {len(gap)} cross a missing 15m candle.", "", THEAD,
                 trow("Live now: touch + break, 1 per coin, max 5", [t for t in live if t.get("r") is not None]),
                 trow("**Breaks only, 1 per coin, max 5**", [t for t in live_br if t.get("r") is not None]),
                 trow("Touch + break, no slot limit", closed),
                 trow("Breaks only, no slot limit", br),
                 trow("Touches only, no slot limit", to),
                 trow("Breaks only, no slot limit, no data gap", brc), ""]
        exits = {}
        for t in br:
            exits[t["outcome"]] = exits.get(t["outcome"], 0) + 1
        text += ["Break exits: " + ", ".join(f"{k} {v}" for k, v in sorted(exits.items())), ""]
    by = {s: [t for t in rows if t["symbol"] == s and t["level"] == "BR" and t.get("r") is not None and not t.get("news")]
          for s in symbols}
    text += ["### Breaks per coin (no slot limit, whole period)", "", THEAD]
    text += [trow(s, by[s]) for s in symbols]
    return text


def trace(rows, symbol_daily, n=6):
    """Full candle trail of a few break trades, to check by hand on a chart."""
    rnd = random.Random(21)
    pick = [t for t in rows if t["level"] == "BR" and t.get("r") is not None and not t.get("news")]
    out = ["## 4. Hand trace (6 random closed breaks, Bitunix)", "", "```"]
    for t in rnd.sample(pick, min(n, len(pick))):
        d = {c[0]: c for c in symbol_daily[t["symbol"]]}
        brk = d.get(t["alert_ts"] - t["alert_ts"] % DAY - DAY)
        sc = t.get("stop_candle")
        out += [f"{t['symbol']} {t['side']} break, daily close {ist(t['alert_ts'])}: break candle {brk}",
                f"  entry {t['entry']} (15m open {ist(t['alert_ts'])}), stop {t['sl']} ({t['risk_pct']:.2f}%) on daily "
                f"{ist(sc[0])[:10] if sc else '-'} {sc}",
                f"  fill {ist(t['fill_ts'])} {t.get('fill_bar')} -> {t['outcome']} {ist(t['exit_ts'])} bar {t.get('exit_bar')} "
                f"level {t.get('exit_level')} best {t.get('best_r')}R = {t['r']:+.3f}R"]
    return out + ["```"]


# ----------------------------------------------------------------- job 3: what the journal shows

def journal_rows(state, now, dcache):
    state = Path(state)
    meta = json.loads((state / "fibtl_rebuild_meta.json").read_text())
    cutoff = datetime.fromisoformat(meta["cutoff"]).timestamp()
    res = json.loads((state / "fibtl_rebuild_results.json").read_text())
    ok = lambda r: (r.get("kind") == "trendline" and r.get("tf") == "1d" and r.get("market") == "crypto"
                    and r.get("broken") and r.get("plan") and r.get("sent_ts", 0) >= JUN1)
    recs = [dict(r, rb=True) for r in jfs.load(state / "fibtl_rebuild_records.jsonl") if ok(r) and r["sent_ts"] < cutoff
            and not (res.get(r["id"]) or {}).get("news_window")]
    recs += [r for r in jfs.load(state / "fib_trendline_alert_records.jsonl") if ok(r) and r["sent_ts"] >= cutoff]
    recs.sort(key=lambda r: r["sent_ts"])
    out = []
    for rec in recs:
        p, sym = rec["plan"], rec["symbol"]
        s = -1 if p["side"] == "short" else 1
        dname = jfs.delta_name(sym)
        if dname not in dcache:
            dcache[dname] = {"1d": jfs.delta(dname, 1440, "1d", JUN1 - 330 * DAY, now) if dname else [],
                             "15m": jfs.delta(dname, 15, "15m", JUN1 - 3 * DAY, now) if dname else []}
        c = dcache[dname]
        t0 = rec["sent_ts"] // 60 * 60
        base = {"id": rec["id"], "symbol": sym, "delta": dname, "side": p["side"], "entry": p["entry"],
                "alert_sl": p["sl"], "alert_ts": t0, "rebuild": bool(rec.get("rb"))}
        if not c["15m"]:
            out.append({**base, "outcome": "no Delta candles"})
            continue
        stop, sc = wick_body_stop(c["1d"], t0, p["entry"], s)
        if stop is None:
            out.append({**base, "outcome": "no stop"})
            continue
        m15 = [[b[0], b[2], b[3], b[4], 900] for b in c["15m"]]
        w = walk(p["entry"], stop, s, m15, t0, False)
        w["news"] = w.get("fill_ts") is not None and news_overlap(w["fill_ts"], w["fill_ts"] + 900)
        fine_ts = [b[0] for b in c["15m"]]
        if w.get("fill_ts") is not None:
            w["gap"] = gap_in(fine_ts, w["fill_ts"], w.get("exit_ts", now - now % 900) + (900 if w.get("exit_ts") else 0))
        out.append({**base, "sl": stop, **{k: v for k, v in w.items() if k not in ("fill_bar", "exit_bar")}})
    return out


def journal_report(rows):
    text = ["## 3. What the journal's Signals tab should show - 1D crypto TL BROKEN (SP + RS TL BR)", "",
            "Journal's own alerts (rebuild before its cutoff, live after), Delta 15m, SL wick or body 0.75%, Exit 1.5R, "
            "SL shift +1R -> +0.75R, Trail TP 0.25R / 0.5R, Till TP / SL, fees on. Open trades left out.", "", THEAD]
    for label, lo in (("1 Jun - now", JUN1), ("Sep 1 - now", SEP1)):
        part = [t for t in rows if t["alert_ts"] >= lo]
        closed = [t for t in part if t.get("r") is not None]
        text.append(trow(label + " (all)", closed))
        text.append(trow(label + " (no news fills)", [t for t in closed if not t.get("news")]))
    outc = {}
    for t in rows:
        outc[t.get("outcome")] = outc.get(t.get("outcome"), 0) + 1
    text += ["", "Outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(outc.items(), key=str)),
             "Missing-data alerts: " + (", ".join(f"{ist(t['alert_ts'])} {t['symbol']} ({t['outcome']})" for t in rows
                                                  if t.get("outcome") in ("no Delta candles",)) or "none"),
             "Trades crossing a missing Delta 15m candle: " + str(sum(1 for t in rows if t.get("gap")))]
    return text


# ----------------------------------------------------------------- main

def main(state, since_text):
    since = int(datetime.fromisoformat(since_text).replace(tzinfo=IST).timestamp())
    now = int(time.time())
    config.FIB_TL_CRYPTO_NIGHT = True
    symbols = list(config.CRYPTO_WATCHLIST)
    data, failed = {}, []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for fut in [pool.submit(audit_symbol, s, since, now) for s in symbols]:
            try:
                s, g = fut.result()
                data[s] = g
                print(f"{s}: data ok")
            except Exception as error:  # noqa: BLE001
                print(f"data failed: {error!r}")
    failed = [s for s in symbols if s not in data or not data[s]["b15"]]
    rows = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for s, r in zip(symbols, pool.map(lambda x: replay_symbol(x, since, now), symbols)):
            if r is None:
                failed.append(s)
                continue
            print(f"{s}: {len(r)} trades")
            rows += r
    dcache = {}
    jrows = journal_rows(state, now, dcache) if state else []
    text = [f"# 1D TL breaks only, verified data - {since_text} to {ist(now)}", "",
            f"{len(symbols)} crypto coins (live list), Bitunix candles cleaned with scanner.clean_candles, live bot rules, "
            "fees 0.0826%, slip 0.05%, fills within 15 min of US CPI / PPI / FOMC left out, open trades left out."
            + (f" FAILED: {', '.join(sorted(set(failed)))}." if failed else " Every coin loaded."), ""]
    text += data_report(symbols, data, since) + [""]
    text += replay_report(rows, since, symbols) + [""]
    if jrows:
        text += journal_report(jrows) + [""]
    text += trace(rows, {s: data[s]["b1d"] for s in data})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "SUMMARY.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    keep = ("symbol", "level", "side", "entry", "sl", "alert_ts", "fill_ts", "exit_ts", "r", "risk_pct", "outcome",
            "news", "gap", "best_r")
    (OUT / "replay_trades.json").write_text(json.dumps([{k: t.get(k) for k in keep} for t in rows]))
    (OUT / "journal_trades.json").write_text(json.dumps(jrows))
    with gzip.open(OUT / "delta_candles.json.gz", "wt", encoding="utf-8") as f:
        json.dump({k: v for k, v in dcache.items() if k}, f, separators=(",", ":"))
    print("\n".join(text))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("state", nargs="?", default="")
    ap.add_argument("--since", default="2025-01-01")
    a = ap.parse_args()
    main(a.state, a.since)

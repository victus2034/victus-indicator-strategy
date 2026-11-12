"""lakky's journal setup for 1D crypto fibs, backtested (2026-11-12: "do a backtest of this
strategy without any mistake ... this is one of the strategy i think it will work").

His Signals screen (Fib alerts, CRYPTO 1D, all coins, 1 Month 12 Oct - 12 Nov):
  - levels L2 / L3 / L4 (L1 off), every BTC day
  - SL "Wick or body" at least 0.75% past entry: walking back from the last closed daily
    candle before the alert, the first wick (low for a buy, high for a sell) and the first
    body (open / close) at least 0.75% past the entry; the stop is the closer of the two
    (300 candles back; none = the alert is left out)
  - Exit 1.5R; SL shift: once +1R trades the stop goes to +0.75R; Trail TP on: at 1.5R the
    stop locks at +1.5R and the target steps +0.25R, the stop 0.5R behind the highest
    target reached; held till TP / SL
  - limit fill at the entry within 20 daily candles; the fill candle can only stop out;
    a candle touching the stop and a target is the stop; a moved stop counts from the
    next candle; stops slip 0.05%; fees 0.0826% of the position
  - journal: 57 alerts, 54 filled, 27W / 23L, +11.83R, +0.24R a trade, PF 1.49, DD -7.43R

Two jobs, written from the rules above and not from the journal's code:
  journal  - the alerts the journal shows for that month (rebuild before its cutoff, live
             after), scored on Delta candles the way the journal reads them, and again on
             Bitunix 5m with only candles after the alert -> compare with his screen
  replay   - every 1D fib alert today's live rules would have sent (fib_trendline_backtest.replay,
             whole watchlist), from --since, on 15m candles; fills within 15 min of US
             CPI / PPI / FOMC left out (backtest standard)

    PYTHONPATH=research python research/journal_fib_setup_backtest.py journal STATE_DIR
    PYTHONPATH=research python research/journal_fib_setup_backtest.py replay --since 2026-09-01
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_data  # noqa: E402
import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, HISTORY_START, bitunix_candles, delta_candles  # noqa: E402
from news_window_backtest import EVENT_TS, WINDOW_MIN  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
OUT = Path(__file__).resolve().parent / "out" / "journal_fib_setup"
DELTA = "https://api.india.delta.exchange"

LEVELS = ("L2", "L3", "L4")
NEW = "journal v.184 way (rebuilt rows fill only after the band candle)"
TARGET, SHIFT_AT, SHIFT_TO, STEP, GAP = 1.5, 1.0, 0.75, 0.25, 0.5
FEE, SLIP = 0.0826, 0.05
FILL_SECONDS = 20 * 86400
SL_GAP_PCT, SL_LOOKBACK = 0.75, 300
DAY = 86400


def ist(ts):
    return datetime.fromtimestamp(ts, IST).strftime("%Y-%m-%d %H:%M")


# ----------------------------------------------------------------- the rules

def wick_body_stop(daily, t0, entry, s):
    """daily = [ts, o, h, l, c]. The stop and the candle it sits on, or (None, None)."""
    closed = [c for c in daily if c[0] + DAY <= t0][-SL_LOOKBACK:]
    edge = entry * (1 - s * SL_GAP_PCT / 100)
    wick = body = None
    for c in reversed(closed):
        w = c[3] if s > 0 else c[2]
        b = min(c[1], c[4]) if s > 0 else max(c[1], c[4])
        if wick is None and ((w <= edge) if s > 0 else (w >= edge)):
            wick = (w, c)
        if body is None and ((b <= edge) if s > 0 else (b >= edge)):
            body = (b, c)
        if wick and body:
            break
    found = [x for x in (wick, body) if x]
    if not found:
        return None, None
    return max(found, key=lambda x: x[0]) if s > 0 else min(found, key=lambda x: x[0])


def walk(entry, stop0, s, bars, t0, alert_candle, band=None):
    """bars = [ts, h, l, c, seconds], oldest first. alert_candle True: the candle the alert
    was sent inside can fill (the journal's way); False: only candles opening at / after t0."""
    risk = abs(entry - stop0) / entry * 100
    bars = [b for b in bars if (b[0] + b[4] > t0 if alert_candle else b[0] >= t0)]
    mv = lambda px: s * (px - entry) / entry * 100 / risk
    hit = lambda b, lvl: (b[2] <= lvl) if s > 0 else (b[1] >= lvl)
    res = {"risk_pct": risk}
    start = 0
    if band is not None:
        # journal v.184, rebuilt rows: fills count only after the first candle that reaches the alert band
        edge = entry * (1 + s * band)
        bi = next((i for i, b in enumerate(bars) if ((b[2] <= edge) if s > 0 else (b[1] >= edge))), None)
        start = len(bars) if bi is None else bi + 1
        if bi is not None:
            res["band_bar"] = bars[bi][:4]
    fi = next((i for i, b in enumerate(bars) if i >= start and b[0] < t0 + FILL_SECONDS and hit(b, entry)), None)
    if fi is None:
        seen = bars[-1][0] + bars[-1][4] if bars else 0
        return {**res, "outcome": "waiting" if seen < t0 + FILL_SECONDS else "no fill"}
    f = bars[fi]
    res.update(fill_ts=f[0], fill_bar=f[:4])
    sl_r = -1 - (stop0 / entry) * SLIP / risk - FEE / risk
    if hit(f, stop0):
        return {**res, "outcome": "SL", "r": sl_r, "exit_ts": f[0], "exit_bar": f[:4], "best_r": 0.0}
    stop, why, tgt = None, "", TARGET

    def lift(best):
        nonlocal stop, why, tgt
        while best >= tgt - 1e-9:
            lvl = max(TARGET, tgt - GAP)
            if stop is None or lvl > stop + 1e-9:
                stop, why = lvl, "Trail TP"
            tgt += STEP
        if best >= SHIFT_AT - 1e-9 and (stop is None or SHIFT_TO > stop + 1e-9):
            stop, why = SHIFT_TO, "SL shift"

    best = max(0.0, mv(f[3]))
    lift(best)
    for b in bars[fi + 1:]:
        lvl = stop0 if stop is None else entry * (1 + s * stop * risk / 100)
        if hit(b, lvl):
            r = sl_r if stop is None else stop - (1 + s * stop * risk / 100) * SLIP / risk - FEE / risk
            return {**res, "outcome": "SL" if stop is None else why, "r": r, "exit_ts": b[0],
                    "exit_bar": b[:4], "exit_level": lvl, "best_r": round(best, 3)}
        best = max(best, mv(b[1] if s > 0 else b[2]))
        lift(best)
    return {**res, "outcome": "open", "best_r": round(best, 3)}


def news_overlap(start, end):
    return any(start <= ev + WINDOW_MIN * 60 and end > ev - WINDOW_MIN * 60 for _n, ev in EVENT_TS)


def stats(rows):
    """rows in alert order; closed trades only."""
    done = [t for t in rows if t.get("r") is not None]
    n = len(done)
    if not n:
        return None
    rs = [t["r"] for t in done]
    win, loss = sum(r for r in rs if r > 0), -sum(r for r in rs if r < 0)
    eq = peak = dd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return {"n": n, "wins": sum(r > 0 for r in rs), "tot": sum(rs), "avg": sum(rs) / n,
            "pct": sum(t["r"] * t["risk_pct"] for t in done) / n, "pct_tot": sum(t["r"] * t["risk_pct"] for t in done),
            "pf": win / loss if loss else float("inf"), "dd": dd,
            "risk": sum(t["risk_pct"] for t in done) / n}


HEAD = ("| Set | Alerts | Filled | Closed | Won | Total R | R/trade | %/trade | PF | Max DD | Avg SL | Open |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|")


def line(name, rows):
    rows = sorted(rows, key=lambda t: t["alert_ts"])
    st = stats(rows)
    filled = sum(1 for t in rows if t.get("fill_ts") is not None)
    opened = sum(1 for t in rows if t.get("outcome") == "open")
    if not st:
        return f"| {name} | {len(rows)} | {filled} | 0 | | | | | | | | {opened} |"
    return (f"| {name} | {len(rows)} | {filled} | {st['n']} | {st['wins'] / st['n'] * 100:.0f}% ({st['wins']}W/{st['n'] - st['wins']}L) | "
            f"{st['tot']:+.2f}R | {st['avg']:+.3f}R | {st['pct']:+.2f}% | {st['pf']:.2f} | -{st['dd']:.2f}R | "
            f"{st['risk']:.2f}% | {opened} |")


def detail(t):
    r = t.get("r")
    sc = t.get("stop_candle")
    return (f"{ist(t['alert_ts'])} {t['symbol']:12} {t.get('level')} {t['side']:5} entry {t['entry']:.6g} "
            f"sl {t['sl']:.6g} ({t['risk_pct']:.2f}%, alert sl {t.get('alert_sl', 0):.6g}) "
            f"stop candle {ist(sc[0])[:10] if sc else '-'} o {sc[1] if sc else '-'} h {sc[2] if sc else '-'} l {sc[3] if sc else '-'} c {sc[4] if sc else '-'} | "
            f"fill {ist(t['fill_ts']) if t.get('fill_ts') else '-'} {t.get('fill_bar', [0, '-', '-'])[1:3]} "
            f"exit {ist(t['exit_ts']) if t.get('exit_ts') else '-'} {t.get('exit_bar', [0, '-', '-'])[1:3]} "
            f"best {t.get('best_r', '-')}R {t['outcome']:9}" + ("" if r is None else f" {r:+.3f}R {r * t['risk_pct']:+.2f}%")
            + (" NEWS" if t.get("news") else ""))


# ----------------------------------------------------------------- job 1: the journal's month

def delta(sym, res_min, res, start, end):
    out, t = {}, int(start)
    span = res_min * 60 * 1900
    while t < end:
        j = {}
        for attempt in range(4):
            try:
                j = requests.get(f"{DELTA}/v2/history/candles", params={
                    "symbol": sym, "resolution": res, "start": t, "end": int(min(end, t + span))}, timeout=20).json()
                break
            except Exception:  # noqa: BLE001
                time.sleep(2 * (attempt + 1))
        for c in j.get("result") or []:
            out[int(c["time"])] = [int(c["time"]), float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])]
        t += span
    return [out[k] for k in sorted(out) if min(out[k][1:]) > 0]


def load(path):
    for raw in open(path, encoding="utf-8"):
        try:
            yield json.loads(raw)
        except ValueError:
            continue


def delta_name(symbol):
    if "/" in symbol:                       # an old ccxt-named record (MRVL/USDT:USDT): Delta's bStock name
        return symbol.split("/")[0] + "BUSD"
    return scanner.delta_contract(symbol) or symbol


def journal(state, since, now):
    state = Path(state)
    meta = json.loads((state / "fibtl_rebuild_meta.json").read_text())
    cutoff = datetime.fromisoformat(meta["cutoff"]).timestamp()
    res = json.loads((state / "fibtl_rebuild_results.json").read_text())
    ok = lambda r: (r.get("kind") == "fib" and r.get("tf") == "1d" and r.get("market") == "crypto"
                    and r.get("level") in LEVELS and since <= r.get("sent_ts", 0) <= now)
    recs = [r for r in load(state / "fibtl_rebuild_records.jsonl") if ok(r) and r["sent_ts"] < cutoff
            and not (res.get(r["id"]) or {}).get("news_window")]
    recs += [r for r in load(state / "fib_trendline_alert_records.jsonl") if ok(r) and r["sent_ts"] >= cutoff]
    recs.sort(key=lambda r: r["sent_ts"])
    cache = {}

    def candles(sym):
        if sym not in cache:
            d = delta_name(sym)
            got = {"1d": [], "15m": [], "1h": [], "b5": []}
            if d:
                got["1d"] = delta(d, 1440, "1d", since - 320 * DAY, now)
                got["15m"] = delta(d, 15, "15m", since - DAY, now)
                got["1h"] = delta(d, 60, "1h", since - DAY, now)
                try:
                    contract = scanner.delta_contract(sym) or sym
                    pair = bitunix_data.pair_for(sym, contract)
                    got["b5"] = [[r[0], r[2], r[3], r[4], 300] for r in bitunix_data.klines(pair, "5m", int(since - DAY), int(now))]
                except Exception as error:  # noqa: BLE001
                    print("bitunix", sym, error)
            cache[sym] = got
        return cache[sym]

    ways = {"journal way (Delta 15m then 1h, alert candle counts)": [], NEW: [], "Delta 15m, after the alert only": [],
            "Bitunix 5m, after the alert only": []}
    skipped = []
    for rec in recs:
        p = rec["plan"]
        s = -1 if p["side"] == "short" else 1
        c = candles(rec["symbol"])
        t0 = rec["sent_ts"] // 60 * 60       # the journal keeps the alert's minute
        stop, sc = wick_body_stop(c["1d"], t0, p["entry"], s)
        if stop is None:
            skipped.append(f"{ist(t0)} {rec['symbol']} {rec.get('level')}: " + ("no Delta candles" if not c["1d"] else "no candle 0.75% past entry"))
            continue
        base = {"symbol": rec["symbol"], "level": rec.get("level"), "side": p["side"], "entry": p["entry"],
                "sl": stop, "alert_sl": p["sl"], "alert_ts": t0, "stop_candle": sc, "id": rec["id"]}
        m15 = [[b[0], b[2], b[3], b[4], 900] for b in c["15m"]]
        # The journal: one read when 15m fits 1900 candles from the alert to now, else
        # 15m for 1800 candles and 1h from the next 1h open on.
        if (now - t0) / 900 <= 1900:
            mixed = m15
        else:
            cut = (t0 + 1800 * 900) // 3600 * 3600
            mixed = [b for b in m15 if b[0] < cut] + [[b[0], b[2], b[3], b[4], 3600] for b in c["1h"] if b[0] >= cut]
        ways["journal way (Delta 15m then 1h, alert candle counts)"].append({**base, **walk(p["entry"], stop, s, mixed, t0, True)})
        ways[NEW].append({**base, **walk(p["entry"], stop, s, mixed, t0, True, 0.0075 if rec.get("rebuild") else None)})
        ways["Delta 15m, after the alert only"].append({**base, **walk(p["entry"], stop, s, m15, t0, False)})
        if c["b5"]:
            ways["Bitunix 5m, after the alert only"].append({**base, **walk(p["entry"], stop, s, c["b5"], t0, False)})
    out = OUT / "journal"
    out.mkdir(parents=True, exist_ok=True)
    text = [f"# Journal check - CRYPTO 1D fibs L2-L4, {ist(since)} to {ist(now)} IST", "",
            "His screen: 57 alerts, 54 filled, 27W / 23L, +11.83R, +0.24R a trade, PF 1.49, max DD -7.43R.",
            f"Alerts found: {len(recs)} (rebuild before {ist(cutoff)}, live after), {len(skipped)} left out.", "", HEAD]
    text += [line(name, rows) for name, rows in ways.items()]
    old = {t["id"]: t for t in ways["journal way (Delta 15m then 1h, alert candle counts)"]}
    text += ["", "## Changed by v.184 (old -> new)", "```"]
    for t in ways[NEW]:
        o = old[t["id"]]
        if (o.get("fill_ts"), o.get("outcome")) != (t.get("fill_ts"), t.get("outcome")):
            fr = lambda x: "-" if x.get("r") is None else f"{x['r']:+.2f}R"
            bb = t.get("band_bar")
            text.append(f"{ist(t['alert_ts'])} {t['symbol']:12} {t['level']} {t['side']:5} entry {t['entry']:.6g} sl {t['sl']:.6g} | "
                        f"band candle {ist(bb[0]) if bb else '-'} h {bb[1] if bb else '-'} l {bb[2] if bb else '-'} | "
                        f"old fill {ist(o['fill_ts']) if o.get('fill_ts') else '-'} {o['outcome']} {fr(o)} -> "
                        f"new fill {ist(t['fill_ts']) if t.get('fill_ts') else '-'} {t['outcome']} {fr(t)}")
    text += ["```", "", "Left out:"] + (skipped or ["none"])
    for name, rows in ways.items():
        text += ["", f"## {name}", "```"] + [detail(t) for t in rows] + ["```"]
    (out / "result.json").write_text(json.dumps(ways, indent=0))
    (out / "SUMMARY.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text))


# ----------------------------------------------------------------- job 2: today's rules, replayed

def symbol_trades(symbol, since, now):
    contract = scanner.delta_contract(symbol)
    if bitunix_data.uses_bitunix(symbol):
        pair = bitunix_data.pair_for(symbol, contract)
        get = lambda res, start: fbt._cached(f"jf_{pair}_{res}_{int(start) // DAY}", lambda: bitunix_candles(pair, res, start, now))
    else:
        get = lambda res, start: fbt._cached(f"jf_{contract}_{res}_{int(start) // DAY}", lambda: delta_candles(contract, res, max(start, now - 2000 * DAY), now))
    daily, four = get("1d", HISTORY_START), get("4h", HISTORY_START)
    fine = [[c[0], c[2], c[3], c[4], 900] for c in get("15m", since - 3 * DAY)]
    band = fbt.band_for("1d")
    out = []
    for t in fbt.replay(CRYPTO, symbol, "1d", daily, four, now):
        if t["kind"] != "fib" or t["alert_ts"] < since or t.get("level") not in LEVELS:
            continue
        p = t["plan"]
        s = -1 if p["side"] == "short" else 1
        edge = p["entry"] * (1 + s * band)
        # The alert goes out in the 15m candle that first comes into the band, inside the
        # replay's 4h candle; fills count from the next one.
        t0 = next((b[0] + 900 for b in fine if t["alert_ts"] <= b[0] < t["alert_ts"] + 4 * 3600
                   and ((b[2] <= edge) if s > 0 else (b[1] >= edge))), t["alert_ts"] + 4 * 3600)
        base = {"symbol": symbol, "level": t.get("level"), "side": p["side"], "entry": p["entry"],
                "alert_sl": p["sl"], "alert_ts": t0}
        stop, sc = wick_body_stop(daily, t0, p["entry"], s)
        own = walk(p["entry"], p["sl"], s, fine, t0, False)
        row = {**base, "sl": stop, "stop_candle": sc, "own": {k: own.get(k) for k in ("r", "risk_pct", "outcome", "fill_ts")}}
        if stop is None:
            out.append({**row, "outcome": "no stop", "risk_pct": 0.0, "sl": 0.0})
            continue
        w = walk(p["entry"], stop, s, fine, t0, False)
        w["news"] = w.get("fill_ts") is not None and news_overlap(w["fill_ts"], w["fill_ts"] + 900)
        out.append({**row, **w})
    return out


def _safe(symbol, since, now):
    try:
        return symbol_trades(symbol, since, now)
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} failed: {error!r}")
        return None


def replay(since_text, tag):
    since = int(datetime.fromisoformat(since_text).replace(tzinfo=IST).timestamp())
    now = int(time.time())
    fbt.FIB_LEVELS = config.FIB_ALERT_LEVELS
    symbols = list(config.WATCHLIST)
    got, failed = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for symbol, res in zip(symbols, pool.map(lambda x: _safe(x, since, now), symbols)):
            if res is None:
                failed.append(symbol)
                continue
            print(f"{symbol}: {len(res)} alerts")
            got += res
    got.sort(key=lambda t: t["alert_ts"])
    ok = [t for t in got if t["outcome"] != "no stop" and not t.get("news")]
    news = sum(1 for t in got if t.get("news"))
    crypto = set(config.CRYPTO_WATCHLIST)
    own = [{**t, "r": t["own"]["r"], "risk_pct": t["own"]["risk_pct"], "outcome": t["own"]["outcome"],
            "fill_ts": t["own"]["fill_ts"]} for t in got
           if not (t["own"]["fill_ts"] is not None and news_overlap(t["own"]["fill_ts"], t["own"]["fill_ts"] + 900))]
    text = [f"# Journal 1D fib setup, replayed under today's rules - {since_text} to {ist(now)[:10]}", "",
            "L2-L4, SL = wick or body 0.75%+ past entry (daily candles before the alert), exit 1.5R, SL shift +1R -> +0.75R, "
            "Trail TP +0.25R / 0.5R behind, held till TP / SL, fill within 20 days, fees 0.0826%, stop slip 0.05%. "
            f"15m candles (Bitunix; XAUT / SLVON Delta). {news} fills within 15 min of US CPI / PPI / FOMC left out; "
            f"{sum(1 for t in got if t['outcome'] == 'no stop')} alerts with no candle that far left out."
            + (f" FAILED symbols: {', '.join(failed)}." if failed else ""), "", HEAD,
            line("All (crypto + xStocks + XAUT/SLVON)", ok),
            line(f"{len(crypto)} crypto coins only", [t for t in ok if t["symbol"] in crypto]),
            line("Same alerts, the alert's own SL", own), "", "## By level", "", HEAD]
    text += [line(lv, [t for t in ok if t["level"] == lv]) for lv in LEVELS]
    text += ["", "## By side", "", HEAD] + [line(sd, [t for t in ok if t["side"] == sd]) for sd in ("long", "short")]
    text += ["", "## By month (alert month)", "", HEAD]
    for m in sorted({ist(t["alert_ts"])[:7] for t in ok}):
        text.append(line(m, [t for t in ok if ist(t["alert_ts"])[:7] == m]))
    text += ["", "## By coin", "", HEAD] + [line(sym, [t for t in ok if t["symbol"] == sym]) for sym in symbols]
    outcomes = {}
    for t in ok:
        outcomes[t["outcome"]] = outcomes.get(t["outcome"], 0) + 1
    text += ["", "Outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())),
             "", "## Trades", "```"] + [detail(t) for t in got if t["outcome"] != "no stop"] + ["```"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"trades_{tag}.json").write_text(json.dumps(got, indent=0))
    (OUT / f"SUMMARY_{tag}.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text[:text.index("## Trades")]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("job", choices=("journal", "replay"))
    ap.add_argument("state", nargs="?")
    ap.add_argument("--since", default="2026-09-01")
    ap.add_argument("--tag", default="")
    ap.add_argument("--from-ist", default="2026-10-12T00:00")
    ap.add_argument("--to-ist", default="2026-11-12T21:26")       # his v.184 screenshot (15:27 for the first one)
    a = ap.parse_args()
    if a.job == "journal":
        journal(a.state, datetime.fromisoformat(a.from_ist).replace(tzinfo=IST).timestamp(),
                datetime.fromisoformat(a.to_ist).replace(tzinfo=IST).timestamp())
    else:
        replay(a.since, a.tag or a.since)

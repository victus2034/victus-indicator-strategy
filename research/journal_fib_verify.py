"""Checks the journal's Signals numbers for 1D crypto fib alerts (lakky, 2026-11-08:
"are these results real or forged, and does the backtest follow the rules").

His screen: Fib alerts, CRYPTO 1D, Top 3 by market cap (BTC, ETH, XRP), 1 Month
(2026-10-08 -> 11-08), exit 1.5R, SL shift +1R -> +0.75R, Trail TP +0.25R / 0.5R behind,
held till TP / SL, fees on -> 9 alerts, 6 filled, 5W / 1L, +4.00R, +0.67R an alert.

Three scorings of the same live alert records, written here from the rules, not from
the journal's code:
  journal  - Delta candles at the resolution the journal picks (finest with <= 1900
             candles from the alert to now: 1h for a month-old alert), counting the
             candle the alert was sent inside, as tgtWalk does
  delta5   - Delta 5m, only candles opening after the alert was sent
  bitunix5 - the same on Bitunix 5m (the alert source)
Rules: limit fill at entry within 20 daily candles of the alert; the fill candle can
only stop out; from the next candle the stop is checked before the high/low moves
anything; +1R moves the stop to +0.75R; at 1.5R the stop locks at +1.5R and the
target steps +0.25R, the stop trailing 0.5R behind the highest target; no time limit.
Stops slip 0.05%; fees 0.0826% round trip (Delta).

    python research/journal_fib_verify.py fib_trendline_alert_records.jsonl live
    python research/journal_fib_verify.py fibtl_rebuild_records.jsonl rebuild   # what the journal shows
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bitunix_data  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
OUT = Path(__file__).resolve().parent / "out" / "journal_fib_verify"
DELTA = "https://api.india.delta.exchange"
SYMBOLS = ("BTCUSD", "ETHUSD", "XRPUSD", "ZECUSD")
SINCE = datetime(2026, 10, 8, tzinfo=IST).timestamp()
NOW = datetime(2026, 11, 8, 12, 19, tzinfo=IST).timestamp()     # his screenshot
TARGET, SHIFT_AT, SHIFT_TO, STEP, GAP = 1.5, 1.0, 0.75, 0.25, 0.5
FEE, SLIP, FILL_DAYS = 0.0826, 0.05, 20
RES = [(1, "1m"), (5, "5m"), (15, "15m"), (60, "1h"), (240, "4h"), (1440, "1d")]


def delta(sym, res_min, res, start, end):
    out, t = {}, int(start)
    span = res_min * 60 * 1900
    while t < end:
        for attempt in range(4):
            try:
                j = requests.get(f"{DELTA}/v2/history/candles", params={
                    "symbol": sym, "resolution": res, "start": t, "end": min(end, t + span)}, timeout=20).json()
                break
            except Exception:  # noqa: BLE001
                time.sleep(2 * (attempt + 1))
        for c in j.get("result") or []:
            out[int(c["time"])] = (int(c["time"]), float(c["high"]), float(c["low"]), float(c["close"]))
        t += span
    return [out[k] for k in sorted(out)]


def bitunix(sym, start, end):
    pair = sym.replace("USD", "USDT")
    return [(r[0], r[2], r[3], r[4]) for r in bitunix_data.klines(pair, "5m", int(start), int(end))]


def score(rec, bars, res_s, include_alert_candle):
    p = rec["plan"]
    entry, stop0, s = p["entry"], p["sl"], (-1 if p["side"] == "short" else 1)
    risk = abs(entry - stop0) / entry * 100
    t0 = rec["sent_ts"]
    bars = [b for b in bars if (b[0] + res_s > t0 if include_alert_candle else b[0] >= t0)]
    mv = lambda px: s * (px - entry) / entry * 100 / risk
    hit = lambda b, lvl: (b[2] <= lvl) if s > 0 else (b[1] >= lvl)
    fi = next((i for i, b in enumerate(bars) if b[0] < t0 + FILL_DAYS * 86400
               and ((b[2] <= entry) if s > 0 else (b[1] >= entry))), None)
    base = {"alert": datetime.fromtimestamp(t0, IST).strftime("%m-%d %H:%M"), "symbol": rec["symbol"],
            "level": rec.get("level"), "side": p["side"], "entry": entry, "sl": stop0, "risk_pct": round(risk, 3)}
    if fi is None:
        waiting = bars and bars[-1][0] < t0 + FILL_DAYS * 86400 - res_s
        return {**base, "result": "waiting" if waiting else "no fill"}
    f = bars[fi]
    base["fill"] = datetime.fromtimestamp(f[0], IST).strftime("%m-%d %H:%M")
    sl_r = -1 - (stop0 / entry) * SLIP / risk - FEE / risk
    if hit(f, stop0):
        return {**base, "result": "SL", "r": sl_r, "exit": base["fill"]}
    stop, why, tgt = None, "", TARGET

    def lift(best):
        nonlocal stop, why, tgt
        while best >= tgt - 1e-9:
            lvl = max(TARGET, tgt - GAP)
            if stop is None or lvl > stop:
                stop, why = lvl, "Trail TP"
            tgt += STEP
        if best >= SHIFT_AT - 1e-9 and (stop is None or SHIFT_TO > stop):
            stop, why = SHIFT_TO, "SL shift"

    best = max(0.0, mv(f[3]))
    lift(best)
    for b in bars[fi + 1:]:
        lvl = stop0 if stop is None else entry * (1 + s * stop * risk / 100)
        if hit(b, lvl):
            ex = datetime.fromtimestamp(b[0], IST).strftime("%m-%d %H:%M")
            if stop is None:
                return {**base, "result": "SL", "r": sl_r, "exit": ex}
            r = stop - (1 + s * stop * risk / 100) * SLIP / risk - FEE / risk
            return {**base, "result": why, "r": r, "exit": ex}
        best = max(best, mv(b[1] if s > 0 else b[2]))
        lift(best)
    return {**base, "result": "open", "best_r": round(best, 2)}


def main():
    out = OUT / (sys.argv[2] if len(sys.argv) > 2 else "live")
    out.mkdir(parents=True, exist_ok=True)
    recs = []
    for line in open(sys.argv[1] if len(sys.argv) > 1 else "fib_trendline_alert_records.jsonl"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if (r.get("kind") == "fib" and r.get("tf") == "1d" and r.get("symbol") in SYMBOLS
                and SINCE <= r.get("sent_ts", 0) <= NOW):
            recs.append(r)
    recs.sort(key=lambda r: r["sent_ts"])
    cache, rows = {}, []
    for rec in recs:
        sym, t0 = rec["symbol"], rec["sent_ts"]
        span = max(NOW - t0, 3600)
        rm, rn = next((x for x in RES if span / (x[0] * 60) <= 1900), RES[-1])
        key = (sym, rn)
        if key not in cache:
            cache[key] = delta(sym, rm, rn, SINCE - 86400, NOW)
        if (sym, "d5") not in cache:
            cache[(sym, "d5")] = delta(sym, 5, "5m", SINCE - 86400, NOW)
        if (sym, "b5") not in cache:
            try:
                cache[(sym, "b5")] = bitunix(sym, SINCE - 86400, NOW)
            except Exception as e:  # noqa: BLE001
                print("bitunix", sym, e)
                cache[(sym, "b5")] = []
        rows.append({
            "id": rec["id"], "journal_res": rn,
            "journal": score(rec, cache[key], rm * 60, True),
            "delta5": score(rec, cache[(sym, "d5")], 300, False),
            "bitunix5": score(rec, cache[(sym, "b5")], 300, False),
        })
    (out / "result.json").write_text(json.dumps(rows, indent=1))
    lines = []
    for way in ("journal", "delta5", "bitunix5"):
        lines.append(f"\n== {way} ==")
        tot, n, w = 0.0, 0, 0
        for row in rows:
            x = row[way]
            r = x.get("r")
            pct = None if r is None else r * x["risk_pct"]
            lines.append(f"{x['alert']} {x['symbol']:7} {x['level']} {x['side']:5} entry {x['entry']:.6g} sl {x['sl']:.6g} "
                         f"risk {x['risk_pct']:.2f}% fill {x.get('fill', '-'):11} exit {x.get('exit', '-'):11} "
                         f"{x['result']:9} " + ("" if r is None else f"{r:+.2f}R {pct:+.2f}%")
                         + (f" [{row['journal_res']}]" if way == "journal" else ""))
            if r is not None:
                tot += r
                n += 1
                w += r > 0
        lines.append(f"filled+closed {n}, wins {w}, total {tot:+.2f}R, per filled {tot / max(n, 1):+.2f}R")
    text = "\n".join(lines)
    (out / "result.txt").write_text(text)
    print(text)


def load(path):
    for line in open(path):
        try:
            yield json.loads(line)
        except ValueError:
            continue


def bitunix_any(sym, start, end):
    pair = bitunix_data.pair_for(sym, sym)
    return [(r[0], r[2], r[3], r[4]) for r in bitunix_data.klines(pair, "5m", int(start), int(end))]


def main_all(rebuild_path, rebuild_results, live_path, cutoff, now):
    """Every CRYPTO 1D fib alert the journal shows for 8 Oct - now: the rebuild before
    its cutoff (news-window fills left out, as the journal does), live alerts after."""
    global NOW
    NOW = now
    res = json.load(open(rebuild_results))
    recs = [r for r in load(rebuild_path) if r.get("kind") == "fib" and r.get("tf") == "1d"
            and r.get("market") == "crypto" and SINCE <= r.get("sent_ts", 0) <= NOW
            and not (res.get(r["id"]) or {}).get("news_window")]
    recs += [r for r in load(live_path) if r.get("kind") == "fib" and r.get("tf") == "1d"
             and r.get("market") == "crypto" and cutoff <= r.get("sent_ts", 0) <= NOW]
    recs.sort(key=lambda r: r["sent_ts"])
    out = OUT / "all"
    out.mkdir(parents=True, exist_ok=True)
    cache, rows = {}, []
    for rec in recs:
        sym = rec["symbol"]
        if sym not in cache:
            try:
                b = bitunix_any(sym, SINCE - 86400, NOW)
            except Exception as e:  # noqa: BLE001
                print("bitunix", sym, e)
                b = []
            d = delta(sym, 5, "5m", SINCE - 86400, NOW)
            cache[sym] = (b, d)
        b, d = cache[sym]
        rows.append({"id": rec["id"], "bitunix5": score(rec, b, 300, False) if b else None,
                     "delta5": score(rec, d, 300, False) if d else None})
    (out / "result.json").write_text(json.dumps(rows, indent=1))
    lines, tot = [], {}
    for row in rows:
        x = row["bitunix5"] or row["delta5"]
        src = "bitunix" if row["bitunix5"] else ("delta" if row["delta5"] else "none")
        if x is None:
            lines.append(f"{row['id']} no candles")
            continue
        y = row["delta5"]
        r, pct = x.get("r"), (None if x.get("r") is None else x["r"] * x["risk_pct"])
        diff = ""
        if row["bitunix5"] and y and (y.get("result"), round(y.get("r") or 0, 2)) != (x.get("result"), round(r or 0, 2)):
            diff = f"  DELTA: {y.get('result')} {y.get('r') if y.get('r') is None else round(y['r'], 2)}"
        lines.append(f"{x['alert']} {x['symbol']:15} {x['level']} {x['side']:5} risk {x['risk_pct']:6.2f}% "
                     f"fill {x.get('fill', '-'):11} exit {x.get('exit', '-'):11} {x['result']:9} "
                     + ("" if r is None else f"{r:+.2f}R {pct:+.2f}%") + f" [{src}]" + diff)
        t = tot.setdefault(x["result"] if r is None else "closed", [0, 0.0, 0.0, 0])
        t[0] += 1
        if r is not None:
            t[1] += r
            t[2] += pct
            t[3] += r > 0
    c = tot.get("closed", [0, 0, 0, 0])
    lines.append(f"\nalerts {len(rows)}; " + ", ".join(f"{k} {v[0]}" for k, v in tot.items()))
    lines.append(f"closed {c[0]}: {c[3]}W / {c[0] - c[3]}L, total {c[1]:+.2f}R ({c[2]:+.2f}%), "
                 f"per trade {c[1] / max(c[0], 1):+.3f}R / {c[2] / max(c[0], 1):+.3f}%")
    text = "\n".join(lines)
    (out / "result.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        # --all REBUILD RESULTS LIVE CUTOFF_TS NOW_TS
        main_all(sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]), float(sys.argv[6]))
    else:
        main()

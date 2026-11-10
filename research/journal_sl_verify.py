"""Checks the journal's Signals SL choice on 1D crypto fibs (lakky, 2026-11-10: "why is it
showing negative overall but with each candle wick and body it's positive").

His screen: Fib alerts, CRYPTO 1D, 1 Month (2026-10-10 -> 11-10), exit 1.5R, SL shift
+1R -> +0.75R, Trail TP +0.5R with the stop 0.25R behind, held till TP / SL, fees on.
  Alert SL      -0.65R  (-39.82% price move)
  Wick 0.75%   +10.63R  (+31.61%)
  Body 0.75%   +15.66R   (-4.41%)
  Wick or body +17.30R  (+25.45%)

Written from the rules, not from the journal's code. Each alert is played four ways:
  alert - the alert's own stop
  wick / body / near - the last closed 1D candle before the alert whose low (wick) or
          min(open, close) (body) is at least 0.75% under a buy's entry (over a sell's);
          near = the closer of the two. The stop sits on that price.
Fill: limit at entry within 20 daily candles, the candle the alert was sent inside
counts. The fill candle can only stop out. From the next candle the stop is checked
before the high moves anything: +1R moves the stop to +0.75R; 1.5R locks it at +1.5R
and the target steps +0.5R with the stop 0.25R behind it; no time limit. Stops slip
0.05%; fees 0.0826% round trip. Candles: Delta 1d (stop) and 15m (walk).
"% price move" = R x the stop's distance from entry, the journal's figure.

    python research/journal_sl_verify.py REBUILD RESULTS LIVE CUTOFF_TS
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

IST = timezone(timedelta(hours=5, minutes=30))
OUT = Path(__file__).resolve().parent / "out" / "journal_sl_verify"
DELTA = "https://api.india.delta.exchange"
SINCE = datetime(2026, 10, 10, tzinfo=IST).timestamp()
NOW = datetime(2026, 11, 10, 20, 9, tzinfo=IST).timestamp()     # his screenshot
TARGET, SHIFT_AT, SHIFT_TO, STEP, GAP = 1.5, 1.0, 0.75, 0.5, 0.25
FEE, SLIP, FILL_DAYS, GAP_PCT, LOOKBACK = 0.0826, 0.05, 20, 0.75, 300
MODES = ("alert", "wick", "body", "near")


def delta(sym, res_min, res, start, end):
    out, t, span = {}, int(start), res_min * 60 * 1900
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
            o, h, l, cl = (float(c[k]) for k in ("open", "high", "low", "close"))
            if min(o, h, l, cl) > 0:
                out[int(c["time"])] = (int(c["time"]), o, h, l, cl)
        t += span
    return [out[k] for k in sorted(out)]


def candle_stop(rec, days, mode):
    p = rec["plan"]
    e, s, t0 = p["entry"], (-1 if p["side"] == "short" else 1), rec["sent_ts"]
    T = e * (1 - s * GAP_PCT / 100)
    closed = [d for d in days if d[0] + 86400 <= t0][-LOOKBACK:]

    def first(val):
        for d in reversed(closed):
            v = val(d)
            if (v <= T) if s > 0 else (v >= T):
                return v
        return None
    w = first(lambda d: d[3] if s > 0 else d[2])
    b = first(lambda d: min(d[1], d[4]) if s > 0 else max(d[1], d[4]))
    if mode == "wick":
        return w
    if mode == "body":
        return b
    if w is None or b is None:
        return w if b is None else b
    return max(w, b) if s > 0 else min(w, b)


def walk(rec, stop0, bars):
    p = rec["plan"]
    entry, s, t0 = p["entry"], (-1 if p["side"] == "short" else 1), rec["sent_ts"]
    risk = abs(entry - stop0) / entry * 100
    bars = [b for b in bars if b[0] + 900 > t0]
    hit = lambda b, lvl: (b[3] <= lvl) if s > 0 else (b[2] >= lvl)
    mv = lambda px: s * (px - entry) / entry * 100 / risk
    fi = next((i for i, b in enumerate(bars) if b[0] < t0 + FILL_DAYS * 86400
               and ((b[3] <= entry) if s > 0 else (b[2] >= entry))), None)
    out = {"risk": risk, "stop": stop0}
    if fi is None:
        return {**out, "result": "waiting" if t0 + FILL_DAYS * 86400 > NOW else "no fill"}
    f = bars[fi]
    out["fill"] = datetime.fromtimestamp(f[0], IST).strftime("%m-%d %H:%M")
    sl_r = -1 - (stop0 / entry) * SLIP / risk - FEE / risk
    if hit(f, stop0):
        return {**out, "result": "SL", "r": sl_r, "exit": out["fill"]}
    st = {"stop": None, "why": "", "tgt": TARGET}

    def lift(best):
        while best >= st["tgt"] - 1e-9:
            lvl = max(TARGET, st["tgt"] - GAP)
            if st["stop"] is None or lvl > st["stop"]:
                st["stop"], st["why"] = lvl, "Trail TP"
            st["tgt"] += STEP
        if best >= SHIFT_AT - 1e-9 and (st["stop"] is None or SHIFT_TO > st["stop"]):
            st["stop"], st["why"] = SHIFT_TO, "SL shift"

    best = max(0.0, mv(f[4]))
    lift(best)
    for b in bars[fi + 1:]:
        stop = st["stop"]
        lvl = stop0 if stop is None else entry * (1 + s * stop * risk / 100)
        if hit(b, lvl):
            ex = datetime.fromtimestamp(b[0], IST).strftime("%m-%d %H:%M")
            if stop is None:
                return {**out, "result": "SL", "r": sl_r, "exit": ex}
            r = stop - (1 + s * stop * risk / 100) * SLIP / risk - FEE / risk
            return {**out, "result": st["why"], "r": r, "exit": ex}
        best = max(best, mv(b[2] if s > 0 else b[3]))
        lift(best)
    return {**out, "result": "open"}


def load(path):
    for line in open(path):
        try:
            yield json.loads(line)
        except ValueError:
            continue


def main(rebuild, results, live, cutoff):
    res = json.load(open(results))
    keep = lambda r: r.get("kind") == "fib" and r.get("tf") == "1d" and r.get("market") == "crypto"
    recs = [r for r in load(rebuild) if keep(r) and SINCE <= r.get("sent_ts", 0) < cutoff
            and not (res.get(r["id"]) or {}).get("news_window")]
    recs += [r for r in load(live) if keep(r) and cutoff <= r.get("sent_ts", 0) <= NOW]
    recs.sort(key=lambda r: r["sent_ts"])
    OUT.mkdir(parents=True, exist_ok=True)
    cache, rows = {}, []
    for rec in recs:
        sym = rec["symbol"]
        if sym not in cache:
            cache[sym] = (delta(sym, 1440, "1d", SINCE - (LOOKBACK + 5) * 86400, NOW),
                          delta(sym, 15, "15m", SINCE - 86400, NOW))
        days, q = cache[sym]
        row = {"id": rec["id"], "symbol": sym, "level": rec.get("level"), "side": rec["plan"]["side"],
               "entry": rec["plan"]["entry"], "alert": datetime.fromtimestamp(rec["sent_ts"], IST).strftime("%m-%d %H:%M")}
        if not q:
            row["none"] = "no Delta candles"
        for m in MODES:
            stop = rec["plan"]["sl"] if m == "alert" else candle_stop(rec, days, m)
            row[m] = {"result": "no stop"} if stop is None else ({"result": "no candles"} if not q else walk(rec, stop, q))
        rows.append(row)
    (OUT / "result.json").write_text(json.dumps(rows, indent=1))
    lines = ["# Journal SL check, CRYPTO 1D fibs, 10 Oct - 10 Nov 2026 (Delta 1d + 15m)", ""]
    lines.append("| SL | closed | W / L | total R | % price move | avg stop % (winners) | avg stop % (losers) | open | waiting / no fill / no stop |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for m in MODES:
        c = [r[m] for r in rows if "r" in r[m]]
        w = [x for x in c if x["r"] > 0]
        l = [x for x in c if x["r"] <= 0]
        avg = lambda xs: sum(x["risk"] for x in xs) / len(xs) if xs else 0
        other = sum(1 for r in rows if r[m]["result"] in ("waiting", "no fill", "no stop", "no candles"))
        lines.append(f"| {m} | {len(c)} | {len(w)} / {len(l)} | {sum(x['r'] for x in c):+.2f}R | "
                     f"{sum(x['r'] * x['risk'] for x in c):+.2f}% | {avg(w):.2f}% | {avg(l):.2f}% | "
                     f"{sum(1 for r in rows if r[m]['result'] == 'open')} | {other} |")
    lines += ["", "Per alert: result R (stop %, % price move)", ""]
    for r in rows:
        cells = []
        for m in MODES:
            x = r[m]
            cells.append(f"{m} {x['result']}" + (f" {x['r']:+.2f}R ({x['risk']:.2f}%, {x['r'] * x['risk']:+.2f}%)" if "r" in x else
                         (f" ({x['risk']:.2f}%)" if "risk" in x else "")))
        lines.append(f"- {r['alert']} {r['symbol']} {r['level']} {r['side']} entry {r['entry']:.6g}: " + " | ".join(cells))
    text = "\n".join(lines)
    (OUT / "RESULT.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]))

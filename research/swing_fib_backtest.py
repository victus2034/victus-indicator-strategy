"""Research only (lakky, 2026-11-04, round 4): his hand-backtested Nifty 5m fib trades, made mechanical.

From his charts (Oct 28, Oct 30, Nov 2, Nov 4): the fib is drawn on the swing that just finished - from
where the move started to its extreme (Oct 28: open high 22,691 -> low 22,498, then that low -> high
22,778; Oct 30: Oct 29's 22,799 low -> 23,019, then 22,905 -> 23,118; Nov 2: open low 23,212 -> 23,360;
Nov 4: Nov 3's low 23,483 -> 23,946). Two 0.55-0.66 boxes; he enters at a box edge in the swing's
direction with a tight stop (7-13 points, ~0.45 of a box) and a target near the swing's extreme.

Mechanical version:
  swing    zigzag on 5m highs/lows: a swing ends once price comes back T% from its extreme; that finished
           swing is the one fib in force until the next swing finishes (not redrawn every candle). A gap
           open of G% or more starts a new swing at the first candle (Nov 2: anchor = its open low).
  levels   L1 = top of the box nearer the extreme (0.34 back from it), L2 its other edge (0.45),
           L3 = 0.55, L4 = 0.66; each once per fib, price must come to it from the extreme's side
  stop     0.45 of a box past the entry (his median); fib cancelled once price passes the swing's start
  target   1R, 3R, or the swing's extreme ("high"); anything open closes at the day's last candle
  order    5m candles: a stop on the fill candle counts (marked "fill-candle stop": order unknown),
           targets from the next candle
"went your side" = target hit, or closed at day end in profit.

    PYTHONPATH=research python research/swing_fib_backtest.py --since 2026-09-01
    PYTHONPATH=research python research/swing_fib_backtest.py --csv research/out/swing_fib/nifty_5m.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fib_trendline_data import IST  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "swing_fib"
LEVELS = {"L1": 0.34, "L2": 0.45, "L3": 0.55, "L4": 0.66}   # fraction of the swing back from its extreme
STOP_BOX = 0.45
TARGETS = ("1R", "3R", "high")
GAP_PCT = 0.2
CHECK_DAYS = ("2026-10-28", "2026-10-29", "2026-10-30", "2026-11-02", "2026-11-03", "2026-11-04")


def day_of(ts):
    return datetime.fromtimestamp(ts, IST).date()


def hm(ts):
    return datetime.fromtimestamp(ts, IST).strftime("%m-%d %H:%M")


def swings(bars, t_pct, gap_pct=GAP_PCT, min_pct=0.0):
    """Yield (i, fib) for each bar: fib = (dir, start_price, start_ts, ext_price, ext_ts, confirmed_i) in force
    from bar i on, or None. A fib becomes active on the bar after its swing is confirmed."""
    d, p, p_ts, e, e_ts = 1, bars[0][3], bars[0][0], bars[0][2], bars[0][0]
    fib = None
    out = []
    for i, (ts, o, h, lo, c, *_) in enumerate(bars):
        out.append(fib)                                 # what is known before this candle
        if i and day_of(ts) != day_of(bars[i - 1][0]) and abs(o / bars[i - 1][4] - 1) * 100 >= gap_pct:
            d = 1 if o > bars[i - 1][4] else -1
            p, p_ts, e, e_ts = (lo, ts, h, ts) if d == 1 else (h, ts, lo, ts)
            fib = None
            out[-1] = None
            continue
        if d == 1:
            if h > e:
                e, e_ts = h, ts
            elif (e - lo) / e * 100 >= t_pct:
                if (e - p) / p * 100 >= min_pct:          # smaller swings leave the last fib in force
                    fib = (1, p, p_ts, e, e_ts, i)
                d, p, p_ts, e, e_ts = -1, e, e_ts, lo, ts
        else:
            if lo < e:
                e, e_ts = lo, ts
            elif (h - e) / e * 100 >= t_pct:
                if (p - e) / p * 100 >= min_pct:
                    fib = (-1, p, p_ts, e, e_ts, i)
                d, p, p_ts, e, e_ts = 1, e, e_ts, h, ts
    return out


def walk_1m(d, entry, stop, target, ones, ts):
    """Same walk on 1m candles, from the first 1m candle inside the 5m fill candle that touches the entry."""
    day = day_of(ts)
    idx = [k for k, b in enumerate(ones) if ts <= b[0] < ts + 300 and ((b[3] if d == 1 else b[2]) - entry) * d <= 0]
    if not idx:
        return None
    k = idx[0]
    if ((ones[k][3] if d == 1 else ones[k][2]) - stop) * d <= 0:
        return "SL*", stop
    last = ones[k]
    for b in ones[k + 1:]:
        if day_of(b[0]) != day:
            break
        last = b
        if ((b[3] if d == 1 else b[2]) - stop) * d <= 0:
            return "SL", stop
        if ((b[2] if d == 1 else b[3]) - target) * d >= 0:
            return "TP", target
    return ("EOD+" if (last[4] - entry) * d > 0 else "EOD-"), last[4]


def walk(d, entry, stop, target, bars, i):
    ts, o, h, lo, c, *_ = bars[i]
    if ((lo if d == 1 else h) - stop) * d <= 0:
        return "SL*", stop
    day = day_of(ts)
    last = bars[i]
    for b in bars[i + 1:]:
        if day_of(b[0]) != day:
            break
        last = b
        if ((b[3] if d == 1 else b[2]) - stop) * d <= 0:
            return "SL", stop
        if ((b[2] if d == 1 else b[3]) - target) * d >= 0:
            return "TP", target
    return ("EOD+" if (last[4] - entry) * d > 0 else "EOD-"), last[4]


def backtest(bars, t_pct, since, min_pct=0.0, ones=None):
    fibs = swings(bars, t_pct, min_pct=min_pct)
    one_days = {day_of(b[0]) for b in ones or []}
    rows, used, dead = [], set(), set()
    for i, fib in enumerate(fibs):
        if fib is None or day_of(bars[i][0]) < since:
            continue
        d, start, start_ts, ext, ext_ts, conf = fib
        key = (start_ts, ext_ts)
        ts, o, h, lo, c, *_ = bars[i]
        if key in dead:
            continue
        rng = (ext - start) * d
        box = 0.11 * rng
        for name, frac in LEVELS.items():
            if (key, name) in used:
                continue
            entry = ext - d * frac * rng
            if (o - entry) * d <= 0 or ((lo if d == 1 else h) - entry) * d > 0:
                continue                                  # not coming from the extreme's side / not touched
            used.add((key, name))
            stop = entry - d * STOP_BOX * box
            risk = abs(entry - stop)
            for tgt in TARGETS:
                target = ext if tgt == "high" else entry + d * float(tgt[:-1]) * risk
                res = "5m"
                got = walk_1m(d, entry, stop, target, ones, ts) if day_of(ts) in one_days else None
                if got:
                    res = "1m"
                    out, px = got
                else:
                    out, px = walk(d, entry, stop, target, bars, i)
                rows.append({"T%": t_pct, "min swing %": min_pct, "res": res, "target": tgt, "day": str(day_of(ts)), "fill": hm(ts),
                             "side": "buy" if d == 1 else "sell", "level": name,
                             "fib": f"{start:.2f} ({hm(start_ts)}) -> {ext:.2f} ({hm(ext_ts)})",
                             "entry": round(entry, 2), "stop": round(stop, 2), "target_px": round(target, 2),
                             "risk_pts": round(risk, 2), "outcome": out, "exit": round(px, 2),
                             "r": round(d * (px - entry) / risk, 2)})
        if ((lo if d == 1 else h) - start) * d <= 0:
            dead.add(key)                                 # price passed the swing's start
    return rows


def load(args):
    if args.csv:
        with open(args.csv) as f:
            return [[int(r[0])] + [float(x) for x in r[1:5]] for r in csv.reader(f) if r[0] != "ts"]
    import fib_trendline_data as fdata
    from daily_fib_backtest import drop_close_print
    bars = drop_close_print(fdata.nse_download(["^NSEI"], "5m").get("^NSEI", []), "5m")
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "nifty_5m.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close"])
        w.writerows([b[:5] for b in bars])
    return bars


def load_1m(args):
    path = Path(args.csv).with_name("nifty_1m.csv") if args.csv else None
    if path and path.exists():
        with open(path) as f:
            return [[int(r[0])] + [float(x) for x in r[1:5]] for r in csv.reader(f) if r[0] != "ts"]
    if args.csv:
        return []
    import time as _t

    import yfinance as yf
    from fib_trendline_data import _frame_to_candles
    out = {}
    end = _t.time()
    for _ in range(4):                                    # Yahoo keeps 1m for 30 days, 8 days a request
        start = end - 7 * 86400
        try:
            raw = yf.download("^NSEI", interval="1m", start=datetime.fromtimestamp(start),
                              end=datetime.fromtimestamp(end), progress=False, auto_adjust=False)
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            for c in _frame_to_candles(raw):
                out[c[0]] = c
        except Exception as error:  # noqa: BLE001
            print("1m chunk failed:", error)
        end = start
    ones = [out[k] for k in sorted(out)
            if (datetime.fromtimestamp(k, IST).hour, datetime.fromtimestamp(k, IST).minute) < (15, 29)]
    with open(OUT / "nifty_1m.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close"])
        w.writerows([b[:5] for b in ones])
    return ones


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-09-01")
    ap.add_argument("--csv")
    ap.add_argument("--t", default="0.3")
    ap.add_argument("--min", default="0,0.6")
    args = ap.parse_args()
    since = datetime.strptime(args.since, "%Y-%m-%d").date()
    bars = load(args)
    print(f"NIFTY 5m: {len(bars)} candles, {hm(bars[0][0])} to {hm(bars[-1][0])}")
    OUT.mkdir(parents=True, exist_ok=True)
    ones = load_1m(args)
    print(f"NIFTY 1m: {len(ones)} candles" + (f", {hm(ones[0][0])} to {hm(ones[-1][0])}" if ones else ""))
    rows = []
    for t in [float(x) for x in args.t.split(",")]:
        # the fibs on his chart days, to compare with what he drew
        seen = set()
        for f in swings(bars, t):
            if f and str(day_of(f[4])) in CHECK_DAYS and f[:5] not in seen:
                seen.add(f[:5])
                d, s, s_ts, e, e_ts, _ = f
                r = (e - s) * d
                print(f"T={t}% fib {'up' if d == 1 else 'down'} {s:.2f} ({hm(s_ts)}) -> {e:.2f} ({hm(e_ts)}): "
                      + ", ".join(f"{n} {e - d * fr * r:.2f}" for n, fr in LEVELS.items()))
        for mn in [float(x) for x in args.min.split(",")]:
            rows += backtest(bars, t, since, mn, ones)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "trades.csv", index=False)
    table = []
    df["window"] = df["res"].map({"1m": "1m candles (last ~30 days)", "5m": "5m candles (earlier)"})
    for (t, mn, win, tgt), g in df.groupby(["T%", "min swing %", "window", "target"], sort=False):
        mine = g.outcome.isin(["TP", "EOD+"])
        table.append({"swing T%": t, "min swing %": mn, "scored on": win, "target": tgt, "trades": len(g),
                      "your side": f"{int(mine.sum())} ({100 * mine.mean():.0f}%)",
                      "TP": int((g.outcome == "TP").sum()), "SL": int(g.outcome.isin(["SL", "SL*"]).sum()),
                      "SL on fill candle": int((g.outcome == "SL*").sum()),
                      "day end +/-": f"{int((g.outcome == 'EOD+').sum())}/{int((g.outcome == 'EOD-').sum())}",
                      "R/trade (no costs)": round(g.r.mean(), 2), "avg stop pts": round(g.risk_pts.mean(), 1)})
    tdf = pd.DataFrame(table)
    tdf.to_csv(OUT / "summary.csv", index=False)
    check = df[df.day.isin(CHECK_DAYS) & (df["min swing %"] == 0.6) & (df.target == "high")]
    text = [f"# Swing fib, lakky's hand rule, NIFTY 5m (run {datetime.now(IST):%Y-%m-%d %H:%M} IST)", "",
            tdf.to_markdown(index=False), "", "## His chart days (min swing 0.6%, target = swing extreme)", "",
            check.drop(columns=["T%", "min swing %", "window"]).to_markdown(index=False), ""]
    (OUT / "SWING_FIB.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()

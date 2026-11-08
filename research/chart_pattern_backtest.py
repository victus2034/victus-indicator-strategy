"""Research (lakky, 2026-11-08): do the chart patterns in his "Trading Chart Patterns" PDF
improve the fib (L1-L4) and trendline alerts?

Every fib / trendline touch the live rules would have sent (fib_trendline_backtest.replay,
live levels and stops, crypto on Delta candles, NSE on Yahoo) is scored three ways:

  live        the alert as traded today (limit at the entry).
  candle      confirmation entry: once the entry fills, wait up to CONFIRM_BARS candles of the
              alert's own timeframe (the fill candle first) for the pattern in the trade's
              direction; enter at that candle's close, same stop, same target rule (fib 2R + BE,
              TL 1R). No pattern in time, or the stop hit first -> no trade.
  chart       double bottom / top and (inverse) head and shoulders, known before the touch:
              a filter on the live trade ("filter"), or the filter plus any confirming candle.

Patterns (buy / sell mirror): engulfing, hammer / shooting star (rejection wick toward the level),
inverted hammer / hanging man (wick away), morning / evening star, piercing / dark cloud cover,
harami, dragonfly / gravestone doji; double bottom / top, inverse H&S / H&S.

Net after fees, R and % per trade. Trades filled within 15 min of a US CPI / PPI / FOMC release
left out.

    PYTHONPATH=research python research/chart_pattern_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import bisect
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402
from trail_fib_tl_backtest import news  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "chart_pattern"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")), ("1D", ("1d",)), ("1W", ("1w",)), ("1M", ("1M",)))
CONFIRM_BARS = 3          # the fill candle and the two after it
PIVOT = 3                 # swing length for double bottom / H&S pivots
LOOKBACK = 60             # candles back for the first bottom / left shoulder
NEAR_PCT = 1.0            # "equal" low/high: within 1% of the entry
TOL = 0.0005              # open-vs-close tolerance (crypto rarely gaps)


# ----------------------------------------------------------------- candle patterns
# Each takes (o, h, l, c) lists and index j, and the trade side (+1 buy, -1 sell).
# Sell = the buy rule on the mirrored candles, so one definition serves both.

def mirror(bars, long):
    return bars if long else [(-o, -l, -h, -c) for o, h, l, c in bars]


def parts(bar):
    o, h, l, c = bar
    rng = h - l
    return abs(c - o), rng, h - max(o, c), min(o, c) - l


def engulfing(b):
    (o1, _, _, c1), (o, _, _, c) = b[-2], b[-1]
    tol = TOL * abs(c1) if c1 else 0
    return c1 < o1 and c > o and o <= c1 + tol and c >= o1 - tol and (c - o) > (o1 - c1)


def hammer(b):                    # rejection wick toward the level (buy: long lower wick)
    body, rng, up, lo = parts(b[-1])
    return rng > 0 and lo >= 2 * body and up <= 0.15 * rng and lo >= 0.6 * rng


def inverted_hammer(b):           # the wick away from the level
    body, rng, up, lo = parts(b[-1])
    return rng > 0 and up >= 2 * body and lo <= 0.15 * rng and up >= 0.6 * rng


def morning_star(b):
    (o2, h2, l2, c2), (o1, _, _, c1), (o, _, _, c) = b[-3], b[-2], b[-1]
    body2 = o2 - c2
    return (c2 < o2 and body2 >= 0.5 * (h2 - l2) and abs(c1 - o1) <= 0.3 * body2
            and c > o and c > (o2 + c2) / 2)


def piercing(b):
    (o1, _, _, c1), (o, _, _, c) = b[-2], b[-1]
    tol = TOL * abs(c1) if c1 else 0
    return c1 < o1 and c > o and o <= c1 + tol and (o1 + c1) / 2 < c < o1


def harami(b):
    (o1, _, _, c1), (o, _, _, c) = b[-2], b[-1]
    return c1 < o1 and c > o and o >= c1 and c <= o1 and (c - o) <= 0.5 * (o1 - c1)


def dragonfly(b):
    body, rng, up, _lo = parts(b[-1])
    return rng > 0 and body <= 0.1 * rng and up <= 0.1 * rng


CANDLES = {
    "Engulfing": (engulfing, 2),
    "Hammer / Shooting star": (hammer, 1),
    "Inv. hammer / Hanging man": (inverted_hammer, 1),
    "Morning / Evening star": (morning_star, 3),
    "Piercing / Dark cloud": (piercing, 2),
    "Harami": (harami, 2),
    "Dragonfly / Gravestone doji": (dragonfly, 1),
}


def candle_hits(bars, j, long):
    """Names of the candle patterns that complete on candle j for this side."""
    got = []
    for name, (rule, need) in CANDLES.items():
        if j - need + 1 < 0:
            continue
        if rule(mirror(bars[j - need + 1:j + 1], long)):
            got.append(name)
    return got


# ----------------------------------------------------------------- chart patterns

def pivots(lows, upto):
    """Swing lows confirmed before candle `upto` (PIVOT candles each side, all closed)."""
    out = []
    for i in range(max(PIVOT, upto - LOOKBACK), upto - PIVOT):
        window = lows[i - PIVOT:i + PIVOT + 1]
        if lows[i] == min(window):
            out.append(i)
    return out


def chart_flags(bars, f, entry, long):
    """Double bottom / inverse H&S (buy) or their mirrors (sell), from candles before f only."""
    m = mirror(bars, long)
    lows = [b[2] for b in m]
    level = entry if long else -entry
    near = abs(level) * NEAR_PCT / 100
    piv = pivots(lows, f)
    double = False
    for p in piv:
        if f - p >= 5 and abs(lows[p] - level) <= near and min(lows[p + 1:f], default=lows[p]) >= lows[p] - near:
            double = True
    ihs = False
    for a in piv:
        for h in piv:
            if h - a < PIVOT or lows[h] >= lows[a] - near:
                continue
            # head clearly below the left shoulder, left shoulder level with the entry,
            # and nothing since the head under it: the touch is the right shoulder
            if abs(lows[a] - level) <= near * 1.5 and lows[h] < level - near and min(lows[h + 1:f], default=lows[h]) >= lows[h]:
                ihs = True
    return {"Double bottom / top": double, "Inverse H&S / H&S": ihs}


# ----------------------------------------------------------------- replay

def candle_closed_at(times, j, tf):
    return times[j + 1] if j + 1 < len(times) else times[j] + fbt.TF_SECONDS[tf]


def confirm_trade(t, bars, times, f, evalc, eval_ts, names, now):
    """Enter at the close of the first candle in f..f+CONFIRM_BARS-1 that shows one of `names`."""
    plan, long = t["plan"], t["plan"]["side"] == "long"
    sl = plan["sl"]
    for j in range(f, min(f + CONFIRM_BARS, len(bars))):
        close_ts = candle_closed_at(times, j, t["tf"])
        if close_ts > now:
            return None
        o, h, l, c = bars[j]
        if (l <= sl) if long else (h >= sl):
            return None                         # stopped before any confirmation
        if (c <= sl) if long else (c >= sl):
            return None
        if not set(candle_hits(bars, j, long)) & names:
            continue
        new = dict(plan, entry=c)
        k = bisect.bisect_left(eval_ts, close_ts)
        res = trades.simulate(new, t["market"], t["tf"], close_ts - 1, evalc[k:])
        return {**t, "plan": new, "result": res}
    return None


def run_chart(market, symbol, tf, base, evalc, now):
    if base and not fbt.candle_is_closed(market, base[-1][0], tf, now):
        base = base[:-1]
    alerts = [a for a in fbt.replay(market, symbol, tf, base, evalc, now) if a["kind"] in ("fib", "trendline")]
    if not alerts:
        return []
    times = [c[0] for c in base]
    bars = [(c[1], c[2], c[3], c[4]) for c in base]
    eval_ts = [c[0] for c in evalc]
    for a in alerts:
        a["confirm"] = {}
        a["flags"] = {}
        res = a["result"]
        if not res["filled"]:
            continue
        f = bisect.bisect_right(times, res["fill_ts"]) - 1
        if f < 0:
            continue
        long = a["plan"]["side"] == "long"
        a["flags"] = chart_flags(bars, f, a["plan"]["entry"], long)
        for name in list(CANDLES) + ["Any candle pattern"]:
            names = set(CANDLES) if name == "Any candle pattern" else {name}
            a["confirm"][name] = confirm_trade(a, bars, times, f, evalc, eval_ts, names, now)
    return alerts


def collect(now, nse=True):
    got = []
    for symbol in scanner.active_watchlist():
        try:
            data = fbt.crypto_data(symbol, now)
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            continue
        if not data:
            continue
        base, evals = data
        for tf in fbt.TIMEFRAMES:
            got += run_chart(CRYPTO, symbol, tf, base.get(tf, []),
                             evals.get(trades.EVAL_RESOLUTION[CRYPTO][tf], []), now)
        print(f"crypto {symbol}: {len(got)} so far", flush=True)
    if nse:
        import nse_scanner
        for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
            for tf in fbt.TIMEFRAMES:
                got += run_chart(NSE, symbol, tf, base.get(tf, []),
                                 evals.get(trades.EVAL_RESOLUTION[NSE][tf], []), now)
    return got


def keep(t):
    return t is not None and not news(t["result"].get("fill_ts"))


def table(got):
    rows = []
    for market in (CRYPTO, NSE):
        for kind, kname in (("fib", "Fib"), ("trendline", "TL")):
            for group, tfs in GROUPS:
                items = [t for t in got if t["market"] == market and t["kind"] == kind and t["tf"] in tfs]
                live = [t for t in items if keep(t) or not t["result"]["filled"]]
                if not live:
                    continue
                rows.append({"market": market, "alert": kname, "tf": group, **row("live (all alerts)", live)})
                for name in list(CANDLES) + ["Any candle pattern"]:
                    pick = [t["confirm"].get(name) for t in items]
                    pick = [t for t in pick if keep(t)]
                    if pick:
                        rows.append({"market": market, "alert": kname, "tf": group,
                                     **row(f"{name} (confirm entry)", pick)})
                for name in ("Double bottom / top", "Inverse H&S / H&S"):
                    flt = [t for t in live if t["result"]["filled"] and t["flags"].get(name)]
                    if flt:
                        rows.append({"market": market, "alert": kname, "tf": group, **row(f"{name} (filter)", flt)})
                    both = [t["confirm"].get("Any candle pattern") for t in items if t["flags"].get(name)]
                    both = [t for t in both if keep(t)]
                    if both:
                        rows.append({"market": market, "alert": kname, "tf": group,
                                     **row(f"{name} + candle (confirm entry)", both)})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--no-nse", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    fbt.FIB_LEVELS = dict(config.FIB_ALERT_LEVELS)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    got = [t for t in collect(now, not args.no_nse) if t["alert_ts"] >= since]
    df = table(got)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Chart patterns as confirmation for fib / TL alerts ({args.since} to now)", "",
            "live = today's alerts (limit at entry). confirm entry = after the fill, the pattern on one of the "
            f"first {CONFIRM_BARS} candles of the alert's timeframe; enter at its close, same stop, fib 2R + BE / TL 1R. "
            "filter = double bottom / H&S already formed at the entry before the touch, live trade kept. "
            "Net after fees, R and % per trade. Crypto on Delta candles, NSE on Yahoo. "
            "Entries filled within 15 min of US CPI/PPI/FOMC left out.", "",
            df.to_markdown(index=False), ""]
    (OUT / "CHART_PATTERNS.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()

"""Research (lakky, 2026-10-27): dump candles + the live fib's levels and stops for a few charts,
so per-level SL rules can be checked against his hand-drawn SLs offline.

    python research/fib_sl_trace.py HYPEUSD:1d ENAUSD:4h
"""
from __future__ import annotations

import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bitunix_data  # noqa: E402
import fib_engine  # noqa: E402
import fib_trendline_scanner as fts  # noqa: E402
from config import FIB_SWING_LENGTH  # noqa: E402
from fib_trendline_data import crypto_charts  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_sl_trace"


def main(args):
    OUT.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for spec in args:
        symbol, tf = spec.split(":")
        pair = bitunix_data.pair_for(symbol, symbol)
        candles = crypto_charts(pair, [tf], now, source="bitunix")[tf]
        with open(OUT / f"{symbol}_{tf}.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["time", "open", "high", "low", "close"])
            w.writerows(c[:5] for c in candles)
        closed = [c for c in candles if c[0] + {"4h": 14400, "1d": 86400}.get(tf, 86400) <= now]
        highs = [c[2] for c in closed]
        lows = [c[3] for c in closed]
        stamp = [datetime.fromtimestamp(c[0], timezone.utc).strftime("%Y-%m-%d %H:%M") for c in closed]
        snaps, _ = fib_engine.run(stamp, highs, lows, N=FIB_SWING_LENGTH)
        s = snaps[-1]
        d, base, top = s["d"], s["O"], s["E"]
        print(f"{symbol} {tf}: d={d} base={base} ({stamp[s['Ot']]}) top={top} ({stamp[s['Et']]})")
        print("  snap:", {k: v for k, v in s.items() if not isinstance(v, (list, dict))})
        lv = fts.fib_levels(d, base, top)
        for rule in ("shared", "next"):
            st = fts.fib_level_stops(d, base, top, rule)
            print(f"  {rule}: " + ", ".join(f"{k} {lv[k]:.5g} -> {st[k]:.5g}" for k in lv))


if __name__ == "__main__":
    main(sys.argv[1:] or ["HYPEUSD:1d", "ENAUSD:4h"])

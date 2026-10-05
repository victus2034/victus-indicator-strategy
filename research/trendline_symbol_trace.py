"""Replay one NSE symbol's 30m/4h candles through trendlines.py (Pine 6b) and
list every swing low/high since --since, with why a nearby bar is or is not a
swing, plus every support/resistance line the chart would hold now.

Research only. Lakky, 2026-10-05: KARURVYSYA 30m, a support line he expected
(Sep 30 low -> Oct 5 low) is not drawn on the indicator.

    python research/trendline_symbol_trace.py KARURVYSYA.NS --tf 30m --since 2026-09-22
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from fib_trendline_data import IST, nse_charts  # noqa: E402
from trendlines import SUPPORT, _is_pivot, build_trendlines  # noqa: E402

L = config.TRENDLINE_SWING_LENGTH


def main():
    p = argparse.ArgumentParser()
    p.add_argument("symbol")
    p.add_argument("--tf", default="30m")
    p.add_argument("--since", default="2026-09-22")
    a = p.parse_args()
    rows = nse_charts([a.symbol], [a.tf])[a.symbol][a.tf]
    t = [datetime.fromtimestamp(r[0], IST).strftime("%m-%d %H:%M") for r in rows]
    H = [r[2] for r in rows]; Lo = [r[3] for r in rows]; C = [r[4] for r in rows]
    start = next(i for i, r in enumerate(rows) if t[i] >= a.since[5:])
    print(f"{a.symbol} {a.tf}: {len(rows)} bars {t[0]} -> {t[-1]} (last bar may be forming)")
    print("\nbar  time         high     low     close  | swing-low? swing-high?")
    for i in range(start, len(rows)):
        def why(vals, high):
            if i < L or i + L >= len(rows):
                return f"wait ({len(rows) - 1 - i}/{L} bars after)" if i + L >= len(rows) else "-"
            if _is_pivot(vals, i, L, high):
                return "SWING"
            w = vals[i - L:i + L + 1]
            best = max(w) if high else min(w)
            if best == vals[i]:
                return "tie"
            return ""
        print(f"{i:4d} {t[i]}  {H[i]:8.2f} {Lo[i]:8.2f} {C[i]:8.2f} | {why(Lo, False):10s} {why(H, True)}")
    for label, data in (("all bars", (H, Lo, C)),):
        lines = build_trendlines(*data, L, config.TRENDLINES_KEEP)
        print(f"\nLines the chart holds now ({label}):")
        for ln in lines:
            kind = "SUP" if ln.kind == SUPPORT else "RES"
            state = "live" if ln.alive else f"broken {t[ln.broken_at]}"
            print(f"  {kind} {ln.y1:.2f} ({t[ln.x1]}) -> {ln.y2:.2f} ({t[ln.x2]})  {state}"
                  f"  now @ {ln.price_at(len(rows)):.2f}")


if __name__ == "__main__":
    main()
